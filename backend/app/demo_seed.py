"""Semilla demo: usuarios de prueba por rol y expedientes ficticios, cargados solo con servicios y acciones reales.

La invoca únicamente la CLI `seed-demo` con ALLOW_DEMO_SEED=true. Todo lo creado lleva is_demo=True y códigos DEMO-;
volver a ejecutarla no duplica usuarios, proveedores ni expedientes.
"""
import secrets
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.infrastructure import audit
from app.infrastructure.models import (Area, Envelope, Evaluation, Offer, PortalSubmission, ProcurementCase, RequestLine, RequirementReview,
                                       SpecRequirement, SpecVersion, Supplier, SupplierStatus, User, UserRole)
from app.modules.identity.permissions import ROLE_NAMES
from app.modules.identity.service import validate_password
from app.modules.procurement import framework
from app.modules.procurement.service import create_case, spec_hash
from app.bootstrap import ensure_base_config
from app.shared.contracts import canonical_hash, utcnow
from app.shared.errors import ApiError

PASSWORD_ALPHABET = string.ascii_letters + string.digits + '!@#$%^&*-_'
DEMO_LEGAL_BASIS = 'Delegación ficticia para datos de demostración'

AREAS = {'Alumbrado público': 'DEMO-ALUM', 'Servicios generales': 'DEMO-SERV', 'Administración': 'DEMO-ADM', 'Vialidad': 'DEMO-VIAL',
         'Pruebas locales': 'LOCAL-TEST'}

SUPPLIERS = [
    ('Serrana Iluminación · demo', 'DEMO-PRV-01', 'DEMO-100001'),
    ('Luz del Este · demo', 'DEMO-PRV-02', 'DEMO-100002'),
    ('Faro Económico · demo', 'DEMO-PRV-03', 'DEMO-100003'),
    ('Textil de la Sierra · demo', 'DEMO-PRV-04', 'DEMO-100004'),
    ('Vestir Trabajo · demo', 'DEMO-PRV-05', 'DEMO-100005'),
    ('Papel y Punto · demo', 'DEMO-PRV-06', 'DEMO-100006'),
    ('Áridos Serranos · demo', 'DEMO-PRV-07', 'DEMO-100007'),
    ('Cantera del Este · demo', 'DEMO-PRV-08', 'DEMO-100008'),
    ('Red Serrana · demo', 'DEMO-PRV-09', 'DEMO-100009'),
    ('Nexo Digital · demo', 'DEMO-PRV-10', 'DEMO-100010'),
    ('Equipos del Este · demo', 'DEMO-PRV-11', 'DEMO-100011'),
    ('Aula Técnica · demo', 'DEMO-PRV-12', 'DEMO-100012'),
    ('Horizonte Informático · demo', 'DEMO-PRV-13', 'DEMO-100013'),
    ('Señal Vial Serrana · demo', 'DEMO-PRV-14', 'DEMO-100014'),
    ('Camino Seguro · demo', 'DEMO-PRV-15', 'DEMO-100015'),
    ('Reflectiva del Este · demo', 'DEMO-PRV-16', 'DEMO-100016'),
    ('Taller de Minas · demo', 'DEMO-PRV-17', 'DEMO-100017'),
    ('Mecánica del Parque · demo', 'DEMO-PRV-18', 'DEMO-100018'),
    ('Motores del Valle · demo', 'DEMO-PRV-19', 'DEMO-100019'),
    ('Servicio Móvil Serrano · demo', 'DEMO-PRV-20', 'DEMO-100020'),
]

IP66_MINIMUM = 'IP66, al menos 14.000 lm, garantía mínima de 24 meses y entrega en hasta 30 días corridos.'

# Datos tomados de model\Compra_Clara_Lavalleja.html (seed()). "stage" es el paso del modelo hasta el que el backend permite llegar.
CASES = [
    {'html_id': 'SC-2026-0042', 'title': '120 luminarias LED para barrios', 'area': 'Alumbrado público', 'quantity': 120, 'unit': 'unidades',
     'budget': 220000000, 'procedure': 'licitacion_abreviada', 'mode': 'weighted', 'minimum': IP66_MINIMUM, 'min_warranty': 24, 'max_days': 30,
     'credit_ref': 'PRE-DEMO-2042', 'stage': 3, 'offers': [], 'num': '42',
     'omitted': 'Pliego publicado, convocatoria, sobres, ofertas, verificación técnica, apertura y pasos posteriores: el paso 3 del modelo no los incluye (la apertura además exige plazo vencido, que la semilla no fuerza).'},
    {'html_id': 'SC-2026-0043', 'title': 'Ropa de trabajo para cuadrillas', 'area': 'Servicios generales', 'quantity': 300, 'unit': 'unidades',
     'budget': 345000000, 'procedure': 'licitacion_abreviada', 'mode': 'min_price', 'minimum': 'Tela y talles solicitados; garantía mínima de 24 meses y entrega en hasta 30 días.',
     'credit_ref': 'PRE-DEMO-2043', 'stage': 2, 'offers': [], 'num': '43',
     'omitted': 'Clasificación, disponibilidad, pliego, convocatoria, sobres y ofertas: el paso 2 del modelo solo llega a solicitud recibida.'},
    {'html_id': 'SC-2026-0044', 'title': 'Insumos de oficina', 'area': 'Administración', 'quantity': 100, 'unit': 'unidades',
     'budget': 18400000, 'procedure': 'convenio_marco', 'mode': 'framework', 'minimum': IP66_MINIMUM,
     'credit_ref': 'PRE-DEMO-2044', 'stage': 5, 'num': '44', 'offers': [('Papel y Punto · demo', 140000)],
     'omitted': 'Adjudicación (17.080.000, RES-DEMO-44), control, comunicación, contrato, orden, recepciones y facturas: no hay acción de adjudicación ni de ejecución en el backend para convenio marco.'},
    {'html_id': 'SC-2026-0045', 'title': 'Reparación de motoniveladora', 'area': 'Vialidad', 'quantity': 1, 'unit': 'servicio',
     'budget': 76000000, 'procedure': 'compra_directa', 'mode': 'min_price', 'minimum': 'Diagnóstico, reparación documentada y garantía de 24 meses.',
     'credit_ref': None, 'stage': 1, 'offers': [], 'num': '45',
     'omitted': 'Todo lo posterior al borrador: el modelo lo marca como borrador sin ofertas.'},
    {'html_id': 'SC-2026-0046', 'title': 'Gravilla para caminería rural', 'area': 'Vialidad', 'quantity': 1000, 'unit': 'toneladas',
     'budget': 880000000, 'procedure': 'licitacion_abreviada', 'mode': 'min_price', 'minimum': 'Granulometría conforme; entrega en hasta 30 días y garantía de conformidad contractual.',
     'credit_ref': 'PRE-DEMO-2046', 'stage': 4, 'num': '46', 'offers': [('Áridos Serranos · demo', 630000), ('Cantera del Este · demo', 650000)],
     'omitted': 'Apertura, precios de ofertas, evaluación, dictamen, control observado (OBS-DEMO-46), adjudicación y pasos posteriores: la apertura exige plazo vencido, que la semilla no fuerza.'},
    {'html_id': 'DEMO-OFERTAS', 'title': 'Luminarias LED para el área de pruebas', 'area': 'Pruebas locales', 'quantity': 120, 'unit': 'unidades',
     'budget': 2200000, 'procedure': 'licitacion_abreviada', 'mode': 'weighted', 'minimum': IP66_MINIMUM, 'min_warranty': 24, 'max_days': 30,
     'credit_ref': 'PRE-DEMO-OFERTAS', 'stage': 4, 'num': '47',
     'offers': [('Serrana Iluminación · demo', 12500), ('Luz del Este · demo', 11500), ('Faro Económico · demo', 10000)],
     'offer_comparison': [
         {'supplier': 'Serrana Iluminación · demo', 'unit_price': '12500', 'freight': '0', 'delivery_days': 10, 'warranty_months': 60, 'technical': 'met'},
         {'supplier': 'Luz del Este · demo', 'unit_price': '11500', 'freight': '20400', 'delivery_days': 20, 'warranty_months': 36, 'technical': 'met'},
         {'supplier': 'Faro Económico · demo', 'unit_price': '10000', 'freight': '36000', 'delivery_days': 15, 'warranty_months': 12, 'technical': 'not_met'}],
     'omitted': 'Evaluación calculada con tres ofertas ficticias; la adjudicación queda pendiente para probar el flujo.'},
    {'html_id': 'DEMO-VESTUARIO', 'title': 'Uniformes para cuadrillas municipales', 'area': 'Pruebas locales',
     'quantity': 300, 'unit': 'conjuntos', 'budget': 1200000, 'procedure': 'compra_directa', 'mode': 'min_price',
     'minimum': 'Tela de trabajo reforzada y disponibilidad de los talles solicitados.',
     'credit_ref': 'PRE-DEMO-48', 'stage': 4, 'num': '48',
     'offers': [('Textil de la Sierra · demo', 2250), ('Vestir Trabajo · demo', 2400), ('Papel y Punto · demo', 2100)],
     'offer_comparison': [
         {'supplier': 'Textil de la Sierra · demo', 'unit_price': '2250', 'freight': '60000', 'delivery_days': 12, 'warranty_months': 12, 'technical': 'met'},
         {'supplier': 'Vestir Trabajo · demo', 'unit_price': '2400', 'freight': '0', 'delivery_days': 18, 'warranty_months': 18, 'technical': 'met'},
         {'supplier': 'Papel y Punto · demo', 'unit_price': '2100', 'freight': '0', 'delivery_days': 20, 'warranty_months': 12,
          'technical': 'not_met', 'note': 'La muestra ficticia no acredita la tela reforzada solicitada.'}],
     'omitted': 'Comparación por importe total: el flete cambia el orden de las ofertas admisibles.'},
    {'html_id': 'DEMO-CAMINERIA', 'title': 'Gravilla para caminos vecinales', 'area': 'Pruebas locales',
     'quantity': 240, 'unit': 'toneladas', 'budget': 850000, 'procedure': 'compra_directa', 'mode': 'min_price',
     'minimum': 'La granulometría debe acreditarse con una ficha técnica.',
     'credit_ref': 'PRE-DEMO-49', 'stage': 4, 'num': '49',
     'offers': [('Áridos Serranos · demo', 2150), ('Cantera del Este · demo', 2030)],
     'offer_comparison': [
         {'supplier': 'Áridos Serranos · demo', 'unit_price': '2150', 'freight': '0', 'delivery_days': 8, 'warranty_months': 6, 'technical': 'met'},
         {'supplier': 'Cantera del Este · demo', 'unit_price': '2030', 'freight': '0', 'delivery_days': 14, 'warranty_months': 6, 'technical': 'pending'}],
     'omitted': 'Sin recomendación porque falta revisar la ficha técnica de una oferta.'},
    {'html_id': 'DEMO-PAPEL', 'title': 'Resmas de papel para oficinas', 'area': 'Pruebas locales',
     'quantity': 500, 'unit': 'resmas', 'budget': 300000, 'procedure': 'compra_directa', 'mode': 'min_price',
     'minimum': 'Papel A4 de 80 g/m², en resmas de 500 hojas.',
     'credit_ref': 'PRE-DEMO-50', 'stage': 4, 'num': '50',
     'offers': [('Papel y Punto · demo', 320), ('Textil de la Sierra · demo', 300)],
     'offer_comparison': [
         {'supplier': 'Papel y Punto · demo', 'unit_price': '320', 'freight': '0', 'delivery_days': 5, 'warranty_months': 3, 'technical': 'met'},
         {'supplier': 'Textil de la Sierra · demo', 'unit_price': '300', 'freight': '12200', 'delivery_days': 9, 'warranty_months': 3, 'technical': 'met'}],
     'omitted': 'Empate exacto en el importe comparable; los plazos no son criterio de desempate.'},
]


def _comparison_case(num, key, title, quantity, unit, budget, minimum, quotes, *, weighted=False):
    return {
        'html_id': f'DEMO-{key}', 'title': title, 'area': 'Pruebas locales', 'quantity': quantity, 'unit': unit,
        'budget': budget, 'procedure': 'compra_directa', 'mode': 'weighted' if weighted else 'min_price',
        'minimum': minimum, 'min_warranty': 24, 'max_days': 30,
        'credit_ref': f'PRE-DEMO-{num}', 'stage': 4, 'num': str(num),
        'offers': [(f'{name} · demo', price) for name, price, *_ in quotes],
        'offer_comparison': [
            {'supplier': f'{name} · demo', 'unit_price': str(price), 'freight': str(freight),
             'delivery_days': days, 'warranty_months': warranty, 'technical': status, 'note': note}
            for name, price, freight, days, warranty, status, note in quotes
        ],
        'omitted': 'Sin adjudicación ni documentos adjuntos.',
    }


CASES += [
    _comparison_case(51, 'INFORMATICA', 'Equipos informáticos para atención ciudadana', 18, 'equipos', 1000000,
                     'SSD de al menos 512 GB y memoria RAM de al menos 16 GB.', [
        ('Red Serrana', 36000, 0, 10, 60, 'met', None),
        ('Nexo Digital', 33500, 0, 20, 36, 'met', None),
        ('Equipos del Este', 38000, 15000, 8, 24, 'met', None),
        ('Aula Técnica', 36500, 0, 24, 60, 'met', None),
        ('Horizonte Informático', 31500, 0, 12, 36, 'not_met', 'La ficha cotizada indica 8 GB de memoria RAM.'),
    ], weighted=True),
    _comparison_case(52, 'SENALIZACION', 'Señales reflectivas para cruces escolares', 60, 'señales', 450000,
                     'Lámina retrorreflectiva clase II y chapa galvanizada.', [
        ('Señal Vial Serrana', 4900, 8000, 12, 24, 'met', None),
        ('Camino Seguro', 4700, 28000, 10, 24, 'met', None),
        ('Reflectiva del Este', 5100, 0, 8, 36, 'met', None),
        ('Áridos Serranos', 5200, 12000, 19, 24, 'met', None),
        ('Cantera del Este', 4200, 0, 21, 12, 'not_met', 'La lámina indicada es de clase I.'),
    ]),
    _comparison_case(53, 'TALLER', 'Mantenimiento de camiones recolectores', 4, 'servicios', 700000,
                     'El mantenimiento debe incluir diagnóstico, repuestos y prueba de frenos.', [
        ('Taller de Minas', 98000, 0, 14, 12, 'not_met', 'La cotización excluye los repuestos.'),
        ('Mecánica del Parque', 105000, 0, 10, 18, 'not_met', 'No incluye prueba de frenos.'),
        ('Motores del Valle', 110000, 0, 20, 24, 'not_met', 'El diagnóstico se cobra aparte.'),
        ('Servicio Móvil Serrano', 90000, 12000, 9, 6, 'not_met', 'Solo cotiza el diagnóstico.'),
    ]),
]


def _public_call(num, title, area, quantity, unit, budget, procedure, minimum, need, days, weighted=False):
    return {'html_id': f'PORTAL-DEMO-{num}', 'num': str(num), 'title': title, 'area': area, 'quantity': quantity,
            'unit': unit, 'budget': budget, 'procedure': procedure, 'minimum': minimum, 'need': need,
            'mode': 'weighted' if weighted else 'min_price', 'min_warranty': 24, 'max_days': 30, 'deadline_days': days,
            'credit_ref': f'PRE-PORTAL-DEMO-{num}', 'stage': 4, 'offers': [], 'portal': True,
            'omitted': 'Convocatoria ficticia publicada en el portal departamental.'}


CASES += [
    _public_call(54, 'Luminarias LED para espacios públicos', 'Alumbrado público', 120, 'luminarias', 2200000,
                 'licitacion_abreviada', IP66_MINIMUM,
                 'Renovar los puntos de luz en plazas y avenidas de Minas para mejorar la visibilidad nocturna.', 18, True),
    _public_call(55, 'Gravilla para caminos rurales', 'Vialidad', 600, 'toneladas', 1300000,
                 'concurso_precios', 'Gravilla de entre 6 y 12 mm, con ficha de granulometría y transporte incluido.',
                 'Abastecer a las cuadrillas que reparan el firme de los caminos vecinales del departamento.', 24),
    _public_call(56, 'Equipos informáticos para atención ciudadana', 'Administración', 20, 'equipos', 950000,
                 'compra_directa', 'Cada equipo incluye monitor, teclado, 16 GB de memoria RAM y disco SSD de 512 GB.',
                 'Sustituir los equipos de las oficinas de atención al público y de las mesas de entrada.', 12, True),
    {**_public_call(57, 'Señalización para cruces escolares', 'Vialidad', 60, 'señales', 450000,
                    'compra_directa', 'Señales de chapa galvanizada y lámina retrorreflectiva clase II.',
                    'Instalar señales verticales en los cruces próximos a centros educativos de Minas.', 21, True),
     'offer_comparison': [
         {'supplier': 'Señal Vial Serrana · demo', 'unit_price': '4900', 'freight': '0',
          'delivery_days': 10, 'warranty_months': 60, 'technical': 'met'},
         {'supplier': 'Camino Seguro · demo', 'unit_price': '4600', 'freight': '0',
          'delivery_days': 15, 'warranty_months': 36, 'technical': 'met'}],
     'award_supplier': 'Camino Seguro · demo', 'omitted': 'Adjudicación ficticia publicada. La semilla no consulta un modelo de IA.'},
]

GENERAL_OMISSIONS = [
    'Documentos adjuntos del modelo (solicitud, pliego, actas): requieren almacenamiento de archivos.',
    'Los ejemplos del área Pruebas locales incluyen apertura y evaluación ficticias, sin adjudicación.',
]


def _new_password(username):
    while True:
        candidate = ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(18))
        try:
            validate_password(candidate, username)
            return candidate
        except ApiError:
            continue


def _ensure_users():
    users, credentials = {}, []
    for role, label in ROLE_NAMES.items():
        username = f'demo-{role}'
        user = db.session.scalar(db.select(User).filter_by(username=username))
        if user is None:
            password = _new_password(username)
            user = User(username=username, email=f'{username}@demo.invalid', full_name=f'Demo {label}', is_demo=True, must_change_password=True)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            db.session.add(UserRole(user_id=user.id, role_code=role, valid_from=utcnow(), legal_basis=DEMO_LEGAL_BASIS))
            audit.record(None, 'demo.user_created', 'user', user.id, reason=username, role_code=role)
            db.session.commit()
            credentials.append((username, password))
        users[role] = user
    return users, credentials


def _ensure_areas():
    areas = {}
    for html_name, code in AREAS.items():
        area = db.session.scalar(db.select(Area).filter_by(code=code))
        if area is None:
            area = Area(code=code, name=html_name if code == 'LOCAL-TEST' else f'{html_name} (demo)', active=True)
            db.session.add(area)
            db.session.commit()
        areas[html_name] = area
    return areas


def _ensure_suppliers(compras):
    suppliers, created = {}, 0
    for name, code, tax_id in SUPPLIERS:
        supplier = db.session.scalar(db.select(Supplier).filter_by(code=code))
        if supplier is None:
            supplier = Supplier(code=code, name=name, tax_id=tax_id, is_demo=True, created_by=compras.id)
            db.session.add(supplier)
            db.session.flush()
            db.session.add(SupplierStatus(supplier_id=supplier.id, kind='rupe', state='activo', valid_from=utcnow().date(),
                                          evidence_ref='RUPE-DEMO-CONSTANCIA', verified_by=compras.id))
            audit.record(None, 'demo.supplier_created', 'supplier', supplier.id, reason=code)
            db.session.commit()
            created += 1
        suppliers[name] = supplier
    return suppliers, created


def _spec(c, deadline=None):
    spec = {'mode': c['mode'], 'currency': 'UYU', 'minimum_text': c['minimum'], 'reception_channel': 'presencial', 'reception_place': 'Mesa de entradas',
            'requirements': [{'code': 'R1', 'text': c['minimum'], 'essential': True, 'kind': 'review'}]}
    if c.get('portal'):
        spec.update(reception_channel='portal', reception_place='Portal de compras de Lavalleja')
    if c['mode'] == 'weighted':
        spec['requirements'] += [
            {'code': 'R2', 'text': f"Garantía mínima de {c['min_warranty']} meses", 'essential': True, 'kind': 'numeric',
             'attribute': 'warranty_months', 'operator': 'gte', 'threshold': str(c['min_warranty'])},
            {'code': 'R3', 'text': f"Entrega hasta {c['max_days']} días", 'essential': True, 'kind': 'numeric',
             'attribute': 'delivery_days', 'operator': 'lte', 'threshold': str(c['max_days'])}]
        spec['criteria'] = [
            {'code': 'price', 'name': 'Precio', 'weight': '70', 'type': 'price_ratio'},
            {'code': 'delivery', 'name': 'Entrega', 'weight': '20', 'type': 'scale', 'attribute': 'delivery_days',
             'scale': [{'min': '0', 'max': '10', 'points': '20'}, {'min': '11', 'max': '20', 'points': '10'}, {'min': '21', 'max': '30', 'points': '0'}]},
            {'code': 'warranty', 'name': 'Garantía', 'weight': '10', 'type': 'scale', 'attribute': 'warranty_months',
             'scale': [{'min': '60', 'max': None, 'points': '10'}, {'min': '36', 'max': '59', 'points': '6'}, {'min': '24', 'max': '35', 'points': '3'}]}]
    if deadline:
        spec['offer_deadline'] = deadline
    return spec


def _steps(c, suppliers, line_id, now):
    convenio = c['procedure'] == 'convenio_marco'
    deadline = (now + timedelta(days=c.get('deadline_days', 20))).isoformat()
    published = (now - timedelta(days=30)).date().isoformat()
    steps = []
    if c['stage'] >= 2:
        steps += [('solicitante', 'request.submit', {}), ('compras', 'request.receive', {})]
    if c['stage'] >= 3:
        steps += [
            ('compras', 'procedure.classify', {'procedure_type': c['procedure'], 'reason': 'Encuadre según monto y tipo de compra (datos de demostración).'}),
            ('contaduria', 'availability.register', {
                'fiscal_year': 2026, 'item': c['credit_ref'] if c.get('portal') else c['title'], 'funding_source': 'Rentas generales', 'total_amount': str(c['budget']),
                'credit_support_ref': c['credit_ref'], 'amount': str(c['budget']), 'availability_date': '2026-10-01', 'support_ref': f"DISP-DEMO-{c['num']}"})]
    if c['stage'] >= 4:
        if not convenio:
            steps.append(('compras', 'spec.save', {'spec': _spec(c, deadline)}))
        steps += [
            ('compras', 'spec.approve', {}),
            ('ordenador', 'call.authorize', {'reference': f"RES-DEMO-{c['num']}", 'reason': 'Llamado autorizado con datos ficticios de demostración.'})]
        if c.get('portal'):
            steps.append(('compras', 'publicity.register', {'kind': 'convocatoria', 'state': 'portal'}))
        elif not convenio:
            steps.append(('compras', 'publicity.register', {'kind': 'convocatoria', 'state': 'external_constancia',
                                                            'reference': f"ARCE-DEMO-{c['num']}", 'published_on': published}))
            for name, _net in c['offers']:
                steps.append(('recepcion', 'envelope.register', {'supplier_id': suppliers[name].id, 'channel': 'presencial',
                                                                 'custody_note': 'Sobre recibido en mesa de entradas (datos demo).'}))
    if c['stage'] >= 5 and convenio:
        name, net = c['offers'][0]
        unit_price = (Decimal(net) / Decimal(c['quantity'])).quantize(Decimal('0.01'))
        steps.append(('compras', 'framework.select', {
            'supplier_id': suppliers[name].id, 'agreement_ref': 'CM-DEMO-01', 'evidence_note': 'Constancia ficticia de selección en convenio marco.',
            'lines': [{'request_line_id': line_id, 'unit_price': str(unit_price), 'tax_rate': '22'}]}))
    return steps


def _ensure_demo_comparison(case, users, suppliers, line_id, quotes):
    spec = db.session.scalar(db.select(SpecVersion).where(
        SpecVersion.case_id == case.id, SpecVersion.status == 'approved'))
    if spec is None:
        raise RuntimeError(f'El expediente demo {case.code} no tiene un pliego aprobado.')

    if case.status == 'receiving_offers':
        if spec.reception_channel == 'portal':
            _demo_submissions(case, spec, suppliers, line_id, quotes)
        if spec.offer_deadline and spec.offer_deadline > utcnow():
            previous = spec.offer_deadline
            spec.offer_deadline = utcnow() - timedelta(seconds=1)
            spec.content_hash = spec_hash(spec)
            audit.record(None, 'demo.deadline_simulated', 'case', case.id, case=case,
                         reason='Avance de reloj exclusivo de la semilla local para abrir ofertas ficticias.',
                         reference=case.code, details={'previous_deadline': previous.isoformat(),
                                                       'simulated_deadline': spec.offer_deadline.isoformat()})
            db.session.commit()
        framework.execute(case.code, 'opening.perform', {
            'reference': f'ACTA-DEMO-{case.code}',
            'participants': 'Compras · usuario demo\nRecepción · usuario demo',
            'notes': 'Apertura ficticia preparada para probar la evaluación local.'}, users['compras'])

    if case.status not in ('offers_opened', 'evaluation'):
        return

    offers = db.session.scalars(db.select(Offer).where(Offer.case_id == case.id)).all()
    requirement = db.session.scalar(db.select(SpecRequirement).where(
        SpecRequirement.spec_version_id == spec.id, SpecRequirement.kind == 'review').order_by(SpecRequirement.position))
    if requirement is None:
        raise RuntimeError(f'El expediente demo {case.code} no tiene un requisito revisable.')

    for quote in quotes:
        supplier = suppliers[quote['supplier']]
        offer = next((row for row in offers if row.supplier_id == supplier.id), None)
        if offer is None:
            raise RuntimeError(f'Falta el sobre ficticio de {quote["supplier"]} en {case.code}.')
        if offer.data_version == 0:
            framework.execute(case.code, 'offer.record', {
                'offer_id': offer.id,
                'currency': case.currency,
                'prices_include_tax': False,
                'lines': [{'request_line_id': line_id, 'unit_price': quote['unit_price'], 'tax_rate': '22'}],
                'freight': quote['freight'],
                'freight_includes_tax': True,
                'delivery_days': quote['delivery_days'],
                'warranty_months': quote['warranty_months'],
                'delivery_terms': 'Entregado en depósito departamental',
                'reason': 'Cotización ficticia de demostración; valores preparados para testing.'}, users['tecnica'])
        if quote['technical'] != 'pending' and not db.session.scalar(db.select(RequirementReview.id).where(
            RequirementReview.offer_id == offer.id, RequirementReview.requirement_id == requirement.id)):
            note = quote.get('note') or ('Ficha técnica ficticia: acredita los requisitos publicados.' if quote['technical'] == 'met'
                                        else 'Ficha técnica ficticia: no acredita la garantía mínima de 24 meses.')
            framework.execute(case.code, 'requirement.review', {
                'offer_id': offer.id, 'requirement_id': requirement.id, 'result': quote['technical'],
                'treatment': 'no_subsanable' if quote['technical'] == 'not_met' else None,
                'note': note}, users['tecnica'])

    if not db.session.scalar(db.select(Evaluation.id).where(
        Evaluation.case_id == case.id, Evaluation.status == 'current')):
        framework.execute(case.code, 'evaluation.run', {}, users['tecnica'])


def _demo_submissions(case, spec, suppliers, line_id, quotes):
    """Sobres de ejemplo, sin usar direcciones reales ni atribuirles una verificación de identidad."""
    for quote in quotes:
        supplier = suppliers[quote['supplier']]
        if db.session.scalar(db.select(Envelope.id).where(Envelope.case_id == case.id, Envelope.supplier_id == supplier.id)):
            continue
        env = Envelope(case_id=case.id, spec_version_id=spec.id, supplier_id=supplier.id, receipt_code=f'DEMO-{case.code}-{supplier.code}',
                       channel='portal', deadline_at=spec.offer_deadline, on_time=True, custody_note='Sobre ficticio de la semilla de demostración.')
        db.session.add(env)
        db.session.flush()
        offer = {'currency': case.currency, 'prices_include_tax': False, 'lines': [{'request_line_id': line_id, 'unit_price': quote['unit_price'], 'tax_rate': '22'}],
                 'delivery_days': quote['delivery_days'], 'warranty_months': quote['warranty_months'], 'freight': quote['freight'], 'freight_includes_tax': True}
        original = {'supplier_name': supplier.name, 'tax_id': supplier.tax_id, 'email': None, 'accepted_terms': True, 'spec_hash': spec.content_hash,
                    'technical_description': 'Ficha de demostración de señales galvanizadas con lámina clase II.', 'offer': offer}
        db.session.add(PortalSubmission(envelope_id=env.id, retry_key=canonical_hash(env.receipt_code), payload_hash=canonical_hash(original), original=original))
        audit.record(None, 'demo.portal_submission', 'envelope', env.id, case=case, reference=env.receipt_code, reason=env.custody_note)
    db.session.commit()


def _publish_demo_award(case, users, supplier):
    """Continúa desde el último paso confirmado si la semilla ya creó parte del resultado."""
    if case.status == 'evaluation':
        framework.execute(case.code, 'evaluation.send', {'reference': 'ENV-DEMO-57', 'reason': 'Comparación de las dos propuestas ficticias.'}, users['tecnica'])
    if case.status == 'decision':
        from app.infrastructure.models import Intervention
        offer = db.session.scalar(db.select(Offer).where(Offer.case_id == case.id, Offer.supplier_id == supplier.id))
        if not db.session.scalar(db.select(Intervention.id).where(Intervention.case_id == case.id, Intervention.offer_id == offer.id,
                                                                  Intervention.kind == 'control_gasto', Intervention.status == 'active')):
            framework.execute(case.code, 'control.register', {'offer_id': offer.id, 'result': 'sin_observacion', 'reference': 'CTRL-DEMO-57',
                                                              'reason': 'Control ficticio del monto y de la disponibilidad para la oferta seleccionada.'}, users['control'])
        framework.execute(case.code, 'award.register', {
            'offer_id': offer.id, 'reference': 'RES-DEMO-57', 'verified': True,
            'reason': 'La oferta incluye las 60 señales con la lámina requerida, las entrega antes de la instalación y reduce el gasto total.',
            'departure_reason': 'La otra propuesta obtuvo más puntos por entrega y garantía. La autoridad consideró suficiente la garantía de 36 meses y el plazo de 15 días e hizo constar el ahorro.'},
            users['ordenador'])
    if case.status == 'awarded' and not (case.flags or {}).get('public_award'):
        framework.execute(case.code, 'award.publish', {'confirmed': True}, users['compras'])


def _ensure_cases(users, areas, suppliers):
    reports = []
    now = datetime.now(timezone.utc)
    for c in CASES:
        need_text = f"Expediente de demostración {c['html_id']} (datos ficticios): {c['title']}."
        if c.get('portal'):
            need_text = f"{c['need']} Ejemplo ficticio {c['html_id']}."
        existing = db.session.scalar(db.select(ProcurementCase).filter_by(is_demo=True, need_text=need_text))
        if existing is not None:
            line_id = db.session.scalar(db.select(RequestLine.id).where(RequestLine.case_id == existing.id))
            if c.get('offer_comparison'):
                _ensure_demo_comparison(existing, users, suppliers, line_id, c['offer_comparison'])
                if c.get('award_supplier'):
                    _publish_demo_award(existing, users, suppliers[c['award_supplier']])
            reports.append({'html_id': c['html_id'], 'code': existing.code, 'title': c['title'], 'status': 'ya existía', 'omitted': c['omitted']})
            continue
        try:
            case = create_case(users['solicitante'], {
                'title': c['title'], 'area_id': areas[c['area']].id, 'need_text': need_text, 'delivery_place': 'Depósito departamental, Minas',
                'estimated_total': str(c['budget']), 'currency': 'UYU',
                'lines': [{'description': c['title'], 'quantity': str(c['quantity']), 'unit': c['unit']}], 'spec': _spec(c)})
            case.is_demo = True
            db.session.commit()
        except ApiError as exc:
            db.session.rollback()
            reports.append({'html_id': c['html_id'], 'code': None, 'title': c['title'], 'status': f'no creado ({exc.code})', 'omitted': c['omitted']})
            continue
        code = case.code
        line_id = db.session.scalar(db.select(RequestLine.id).filter_by(case_id=case.id))
        done, failure = 0, None
        for role, action, payload in _steps(c, suppliers, line_id, now):
            try:
                framework.execute(code, action, payload, users[role])
                done += 1
            except ApiError as exc:
                db.session.rollback()
                failure = f'{action}: {exc.code}'
                break
        if failure is None and c.get('offer_comparison'):
            try:
                _ensure_demo_comparison(case, users, suppliers, line_id, c['offer_comparison'])
                done += len(c['offer_comparison']) * 2 + 2
                if c.get('award_supplier'):
                    _publish_demo_award(case, users, suppliers[c['award_supplier']])
            except ApiError as exc:
                db.session.rollback()
                failure = f'evaluation.run: {exc.code}'
        reports.append({'html_id': c['html_id'], 'code': code, 'title': c['title'], 'status': f'pasos ejecutados: {done}', 'failure': failure, 'omitted': c['omitted']})
    return reports


def seed():
    ensure_base_config()
    users, credentials = _ensure_users()
    areas = _ensure_areas()
    suppliers, suppliers_created = _ensure_suppliers(users['compras'])
    cases = _ensure_cases(users, areas, suppliers)
    return {'credentials': credentials, 'suppliers_created': suppliers_created, 'cases': cases, 'general_omissions': GENERAL_OMISSIONS}
