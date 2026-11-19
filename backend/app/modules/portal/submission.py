"""Recepción digital. Compras abre el sobre con la misma actuación que los demás canales."""
import hashlib
import hmac
import re
import secrets
import time
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from flask import current_app, session
from sqlalchemy.exc import IntegrityError

from app.config import APP_NAME
from app.extensions import db
from app.infrastructure import audit
from app.infrastructure.models import Envelope, PortalSubmission, Supplier
from app.modules.documents.service import create_document
from app.modules.identity import mailer
from app.modules.identity.service import csrf_token, rate_limit
from app.modules.organization.contact import TAX_ID, contact_email
from app.modules.procurement import inputs as inp
from app.modules.procurement.actions.common import current_round
from app.modules.procurement.framework import Ctx, lock_case
from app.shared.contracts import canonical_hash, canonical_json, dstr, iso_utc, MAX_MONEY, utcnow
from app.shared.errors import ApiError, require
from .catalog import published_tender, summary


def _digest(parts):
    return hmac.new(current_app.secret_key.encode(), canonical_json(parts).encode(), hashlib.sha256).hexdigest()


def identity(data):
    tax = inp.text(data, 'tax_id', 'Identificador fiscal', 5, 30)
    email = contact_email(data, 'email')
    canonical = tax.upper().replace('.', '').replace('-', '')
    require(TAX_ID.fullmatch(tax) and len(canonical) >= 5, 'validation', 'Revisá el identificador fiscal.', 422,
            {'tax_id': 'Usá al menos cinco letras o números.'})
    return canonical, email


def _suppliers(tax, lock=False):
    # Expedientes anteriores pueden guardar el RUT con puntos o guiones.
    normalized = db.func.upper(db.func.replace(db.func.replace(Supplier.tax_id, '.', ''), '-', ''))
    query = db.select(Supplier).where(normalized == tax).limit(2)
    return db.session.scalars(query.with_for_update() if lock else query).all()


def _same_contact(suppliers, email):
    return len(suppliers) == 1 and suppliers[0].active and (suppliers[0].contact_email or '').strip().lower() == email


def _require_open(row):
    require(summary(row)['can_submit'], 'reception_closed', 'Esta convocatoria no está recibiendo ofertas por el portal.', 409)


def send_code(code, data):
    rate_limit('portal_verification', 6)
    tax, email = identity(data)
    rate_limit('portal_recipient', 3, ip=email)
    row = published_tender(code)
    _require_open(row)
    suppliers = _suppliers(tax)
    allowed = not suppliers or _same_contact(suppliers, email)
    spec_id = row[1].id
    db.session.remove()  # No retener una conexión mientras responde el servidor de correo.
    session.pop('portal_challenge', None)
    if allowed:
        answer = f'{secrets.randbelow(1000000):06d}'
        nonce = secrets.token_hex(16)
        proof = _digest([csrf_token(), spec_id, tax, email, nonce, answer])
        try:
            mailer.send_email(f'[{APP_NAME}] Código para presentar una oferta · {code}', [email],
                              f'<p>Tu código para presentar una oferta en {code} es <strong>{answer}</strong>. Vence en 10 minutos.</p>',
                              f'Tu código para presentar una oferta en {code} es {answer}. Vence en 10 minutos.')
        except Exception as exc:
            current_app.logger.warning('portal_mail_failed type=%s', type(exc).__name__)
            raise ApiError('mail_unavailable', 'No se pudo enviar el código. Intentá nuevamente.', 503) from exc
        session['portal_challenge'] = {'proof': proof, 'nonce': nonce, 'expires': int(time.time()) + 600}
    return {'message': 'Si los datos coinciden, recibirás un código por correo. Si tu empresa ya está registrada, usá su correo de contacto.'}


def _verify(spec_id, tax, email, raw_code):
    challenge = session.get('portal_challenge') or {}
    code = raw_code if isinstance(raw_code, str) else ''
    valid = (bool(re.fullmatch('[0-9]{6}', code)) and challenge.get('expires', 0) > time.time()
             and hmac.compare_digest(challenge.get('proof', ''), _digest([csrf_token(), spec_id, tax, email, challenge.get('nonce'), code])))
    require(valid, 'verification_invalid', 'El código es inválido o venció. Revisá el correo o solicitá uno nuevo.', 422,
            {'verification_code': 'Ingresá un código vigente para estos datos.'})


def _quotation(data, ctx, spec):
    require(data.get('accepted_terms') is True, 'validation', 'Confirmá que aceptás el pliego.', 422, {'accepted_terms': 'Obligatorio.'})
    include_tax = data.get('prices_include_tax')
    require(type(include_tax) is bool, 'validation', 'Indicá si los precios incluyen IVA.', 422, {'prices_include_tax': 'Obligatorio.'})
    requested = {line.id: line for line in ctx.lines}
    prices, seen = [], set()
    freight = inp.decimal(data, 'freight', 'Flete', required=False, positive=False, places=2, default=Decimal(0))
    total = freight
    for row in inp.items(data, 'lines', 'Renglones', maximum=100):
        line_id = inp.integer(row, 'request_line_id', 'Renglón', minimum=1)
        require(line_id in requested and line_id not in seen, 'validation', 'Hay un renglón inválido o repetido.', 422, {'lines': 'Revisá los renglones.'})
        seen.add(line_id)
        amount = inp.decimal(row, 'unit_price', 'Precio unitario', places=4)
        tax = inp.decimal(row, 'tax_rate', 'IVA (%)', positive=False, maximum=100, places=3)
        total += requested[line_id].quantity * amount * (1 if include_tax else 1 + tax / 100)
        prices.append({'request_line_id': line_id, 'unit_price': dstr(amount), 'tax_rate': dstr(tax)})
    require(len(seen) == len(requested), 'validation', 'Ingresá un precio para cada renglón.', 422, {'lines': 'Faltan renglones.'})
    require(total <= MAX_MONEY, 'validation', 'El importe total supera el máximo admitido.', 422, {'lines': 'Revisá los importes.'})
    return {'lines': prices, 'currency': spec.currency, 'prices_include_tax': include_tax, 'freight': dstr(freight),
            'freight_includes_tax': True, 'delivery_days': inp.integer(data, 'delivery_days', 'Plazo de entrega', maximum=3650),
            'warranty_months': inp.integer(data, 'warranty_months', 'Garantía', maximum=1200, required=False, default=0),
            'delivery_terms': spec.delivery_terms}


def _supplier(tax, email, name):
    rows = _suppliers(tax, lock=True)
    if rows:
        require(_same_contact(rows, email), 'supplier_contact', 'Consultá con Compras para verificar el contacto registrado.', 409)
        return rows[0]
    supplier = Supplier(code='WEB-' + uuid4().hex[:16], tax_id=tax, name=name, contact_email=email)
    db.session.add(supplier)
    db.session.flush()
    return supplier


def _receipt(env, code):
    return {'receipt_code': env.receipt_code, 'received_at': iso_utc(env.received_at), 'tender_code': code}


def receive(code, data, retry_token, attachment=None):
    rate_limit('portal_offers', 20)
    tax, email = identity(data)
    rate_limit('portal_proof', 8, ip=tax + '|' + email)
    try:
        token = UUID(retry_token or '')
    except ValueError as exc:
        raise ApiError('idempotency_required', 'Falta el identificador de presentación. Recargá el formulario.', 422) from exc
    retry_key = _digest([csrf_token(), code, str(token)])
    payload_hash = canonical_hash({'form': {k: v for k, v in data.items() if k != 'verification_code'},
                                   'attachment': [attachment[0], hashlib.sha256(attachment[1]).hexdigest()] if attachment else None})
    case = lock_case(code)
    require(case is not None, 'not_found', 'No se encontró la convocatoria publicada.', 404)
    prior = db.session.scalar(db.select(PortalSubmission).where(PortalSubmission.retry_key == retry_key))
    if prior:
        require(prior.payload_hash == payload_hash, 'idempotency_conflict', 'Ese envío ya fue confirmado con otros datos.', 409)
        return _receipt(prior.envelope, code), 200
    row = published_tender(code)
    _require_open(row)
    spec, deadline = row[1], row[4]
    require(inp.integer(data, 'spec_id', 'Versión del pliego', minimum=1) == spec.id, 'spec_changed',
            'El pliego cambió. Volvé a abrir la convocatoria para revisar la versión vigente.', 409)
    _verify(spec.id, tax, email, data.get('verification_code'))
    ctx = Ctx(case, None)
    offer = _quotation(data, ctx, spec)
    name = inp.text(data, 'supplier_name', 'Razón social', 3, 200)
    description = inp.text(data, 'technical_description', 'Propuesta técnica', 10, 4000)
    original = {'offer': offer, 'technical_description': description, 'supplier_name': name, 'tax_id': tax,
                'email': email, 'accepted_terms': True, 'spec_hash': spec.content_hash}
    try:
        supplier = _supplier(tax, email, name)
        rnd = current_round(case)
        existing = db.session.scalar(db.select(Envelope.id).where(Envelope.case_id == case.id, Envelope.supplier_id == supplier.id, Envelope.round == rnd))
        require(existing is None, 'already_submitted', 'Ya se recibió una oferta de este proveedor en esta ronda.', 409)
        received_at = utcnow()
        require(received_at < deadline, 'reception_closed', 'Venció el plazo de recepción de ofertas.', 409)
        env = Envelope(case_id=case.id, spec_version_id=spec.id, supplier_id=supplier.id, receipt_code='WEB-' + secrets.token_hex(10).upper(),
                       round=rnd, channel='portal', received_at=received_at, deadline_at=deadline, on_time=True, status='received',
                       custody_note='Formulario digital recibido por el portal. Correo del presentante verificado.')
        db.session.add(env)
        db.session.flush()
        db.session.add(PortalSubmission(envelope_id=env.id, retry_key=retry_key, payload_hash=payload_hash, original=original))
        if attachment:
            filename, content = attachment
            create_document(case, None, content, 'anexo' + Path(filename).suffix.lower(), 'oferta',
                            'Anexo de la oferta ' + env.receipt_code, 'internal', envelope=env)
        case.version += 1
        case.updated_at = received_at
        audit.record(None, 'portal.offer.submit', 'envelope', env.id, case=case, reference=env.receipt_code,
                     reason='Presentación por el proveedor con correo verificado.',
                     details={'supplier_id': supplier.id, 'spec_version': spec.version, 'round': rnd, 'original_hash': canonical_hash(original)})
        receipt = _receipt(env, code)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError('submission_conflict', 'Coincidió con otra presentación del proveedor. Reintentá el envío.', 409) from exc
    session.pop('portal_challenge', None)
    return receipt, 201
