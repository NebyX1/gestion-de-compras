import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from tests.conftest import Api
from tests.flow import Journey, LIGHT_SPEC


def portal_journey(app, api, world, publish=True):
    j = Journey(app, api, world, spec={**LIGHT_SPEC, 'reception_channel': 'portal'})
    j.create(title='Materiales para el portal')
    j.prepare()
    if publish:
        j.act('compras', 'publicity.register', {'state': 'portal', 'kind': 'convocatoria'})
    visitor = Api(app)
    visitor._refresh()
    return j, visitor, f'/api/v1/public/tenders/{j.code}'


def offer_form(app, visitor, url):
    detail = visitor.get(url).get_json()
    tax = uuid4().hex[:12].upper()
    contact = {'tax_id': tax, 'email': tax.lower() + '@tests.invalid'}
    response = visitor.post(url + '/verification', json=contact)
    assert response.status_code == 202, response.get_json()
    message = app.config['MAIL_CAPTURE'][-1]
    code = re.search(r'es ([0-9]{6})', message.body)[1]
    assert message.recipients == [contact['email']] and code not in str(response.get_json())
    return {**contact, 'supplier_name': 'Proveedor del portal', 'verification_code': code, 'spec_id': detail['spec']['id'],
            'lines': [{'request_line_id': detail['lines'][0]['id'], 'unit_price': '1023.49', 'tax_rate': '22'}],
            'prices_include_tax': False, 'freight': '12.10', 'delivery_days': 15, 'warranty_months': 30,
            'technical_description': 'Acredita los requisitos mediante ficha de ensayo IP66.', 'accepted_terms': True}


def test_publication_requires_current_explicit_call(app, api, world):
    j, visitor, url = portal_journey(app, api, world, publish=False)
    assert visitor.get(url).status_code == 404
    j.act('compras', 'publicity.register', {'state': 'pending', 'kind': 'convocatoria'})
    assert visitor.get(url).status_code == 404
    j.act('compras', 'publicity.register', {'state': 'portal', 'kind': 'convocatoria'})
    detail = visitor.get(url).get_json()
    listing = visitor.get('/api/v1/public/tenders', query_string={'q': j.code, 'status': 'open', 'per_page': 1}).get_json()
    assert listing['total'] == 1 and listing['items'][0]['code'] == j.code
    assert detail['can_submit'] and detail['award'] is None and detail['spec']['criteria'][0]['weight']
    assert not {'flags', 'requester', 'authorizations', 'estimated_total', 'offers', 'events'} & detail.keys()
    assert 'estimated_unit_price' not in detail['lines'][0]
    j.act('ordenador', 'case.cancel', {'reason': 'Se suspende la necesidad del llamado.', 'reference': 'Resolución'})
    assert visitor.get(url).get_json()['status_label'] == 'Cancelada'
    assert visitor.post(url + '/verification', json={'tax_id': '12345', 'email': 'a@b.uy'}).status_code == 409


def test_digital_offer_is_sealed_idempotent_and_opens_in_comparator(app, api, world):
    j, visitor, url = portal_journey(app, api, world)
    form = offer_form(app, visitor, url)
    headers = {'Idempotency-Key': str(uuid4())}
    evidence = b'Informe de ensayo integrado en el anexo.'

    def send(offer, file=evidence):
        return visitor.client.post(url + '/offers', data={'offer': json.dumps(offer), 'file': (io.BytesIO(file), 'anexo.txt')},
                                   headers={'X-CSRF-Token': visitor.csrf, **headers})

    assert send(form, b'\x00\xff').status_code == 422
    assert j.detail()['envelopes'] == []
    receipt = send(form)
    assert receipt.status_code == 201, receipt.get_json()
    assert send(form).get_json() == receipt.get_json()
    assert send({**form, 'delivery_days': 16}).status_code == 409
    assert send(form, b'Otro contenido').status_code == 409
    closed = j.detail('tecnica')
    assert closed['offers'] == [] and len(closed['envelopes']) == 1 and closed['documents'][0]['sealed']
    assert form['technical_description'] not in str(closed) and form['email'] not in str(visitor.get(url).get_json())
    download = f'/api/v1/documents/{closed["documents"][0]["id"]}/versions/1/download'
    assert api['tecnica'].get(download).status_code == 404
    extra = api['recepcion'].upload(f'/api/v1/cases/{j.code}/documents',
                                    {'kind': 'oferta', 'title': 'Presentación extra', 'envelope_id': str(closed['envelopes'][0]['id'])},
                                    'anexo.txt', b'Agregado por un funcionario')
    assert extra.status_code == 409
    j.open()
    offer = j.detail('tecnica')['offers'][0]
    assert offer['status'] == 'data_recorded' and offer['data_version'] == 1
    assert offer['data']['lines'][0]['unit_price'] == '1023.4900'
    assert offer['data']['delivery_days'] == 15 and offer['technical_description'] == form['technical_description']
    assert api['tecnica'].get(download).data == evidence
    assert visitor.get(url).get_json()['status'] == 'closed' and visitor.get(download).status_code == 401
    assert send(form).get_json() == receipt.get_json()


def test_validation_contact_deadline_and_atomicity(app, api, world):
    j, visitor, url = portal_journey(app, api, world)
    form = offer_form(app, visitor, url)

    def send(changes):
        return visitor.post(url + '/offers', json={**form, **changes}, headers={'Idempotency-Key': str(uuid4())})

    assert send({'verification_code': 'bad'}).status_code == 422
    assert send({'email': 'otro@tests.invalid'}).status_code == 422
    assert send({'spec_id': form['spec_id'] + 10}).status_code == 409
    assert send({'lines': []}).status_code == 422
    assert send({'lines': [*form['lines'], *form['lines']]}).status_code == 422
    assert send({'accepted_terms': False}).status_code == 422
    assert send({'freight': '-1'}).status_code == 422
    assert not j.detail()['envelopes']
    assert send({}).status_code == 201
    # Otro correo no puede apropiarse de un identificador existente ni recibir su código.
    emails = len(app.config['MAIL_CAPTURE'])
    resp = visitor.post(url + '/verification', json={'email': 'impostor@tests.invalid', 'tax_id': form['tax_id']})
    assert resp.status_code == 202 and len(app.config['MAIL_CAPTURE']) == emails
    visitor.post(url + '/verification', json={'email': form['email'], 'tax_id': form['tax_id']})
    new_code = re.search(r'es ([0-9]{6})', app.config['MAIL_CAPTURE'][-1].body)[1]
    assert send({'verification_code': new_code}).get_json()['code'] == 'already_submitted'
    second = offer_form(app, visitor, url)
    j.expire_deadline()
    assert not visitor.get(url).get_json()['can_submit']
    assert send(second).status_code == 409
    assert len(j.detail()['envelopes']) == 1


def test_simultaneous_retry_creates_one_envelope(app, api, world):
    j, visitor, url = portal_journey(app, api, world)
    form = offer_form(app, visitor, url)
    token = str(uuid4())
    cookie_name = app.config['SESSION_COOKIE_NAME']
    cookie = visitor.client.get_cookie(cookie_name).value

    def submit(_):
        client = app.test_client()
        client.set_cookie(cookie_name, cookie)
        return client.post(url + '/offers', json=form, headers={'X-CSRF-Token': visitor.csrf, 'Idempotency-Key': token})

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(submit, range(2)))
    assert sorted(r.status_code for r in responses) == [200, 201]
    assert responses[0].get_json() == responses[1].get_json()
    assert len(j.detail()['envelopes']) == 1


def test_legacy_supplier_contact_updated_by_staff_then_verified(app, api, world):
    j, visitor, url = portal_journey(app, api, world)
    supplier = j.supplier('Empresa sin contacto registrado', rupe=False)
    address = 'gestion@tests.invalid'
    credentials = {'email': address, 'tax_id': supplier['tax_id']}
    count = len(app.config['MAIL_CAPTURE'])
    visitor.post(url + '/verification', json=credentials)
    assert len(app.config['MAIL_CAPTURE']) == count
    endpoint = f'/api/v1/suppliers/{supplier["id"]}/contact'
    patch = {'contact_email': address, 'expected_email': None, 'evidence_ref': 'Autorización del representante 2026'}
    assert api['tecnica'].patch(endpoint, json=patch).status_code == 403
    assert api['compras'].patch(endpoint, json=patch).status_code == 200
    assert api['compras'].patch(endpoint, json={**patch, 'contact_email': 'otro@tests.invalid'}).status_code == 409
    visitor.post(url + '/verification', json=credentials)
    assert len(app.config['MAIL_CAPTURE']) == count + 1 and app.config['MAIL_CAPTURE'][-1].recipients == [address]


def test_public_pliego_download_is_pinned_to_an_explicit_eligible_version(app, api, world):
    from app.extensions import db
    from app.infrastructure.models import DocumentVersion
    j, visitor, url = portal_journey(app, api, world, publish=False)

    def upload(title, classification):
        resp = api['compras'].upload(f'/api/v1/cases/{j.code}/documents',
                                     {'kind': 'pliego', 'title': title, 'classification': classification},
                                     'condiciones.txt', title.encode())
        assert resp.status_code == 201
        doc_id = resp.get_json()['id']
        with app.app_context():
            return doc_id, db.session.scalar(db.select(DocumentVersion.id).where(DocumentVersion.document_id == doc_id))

    _, private_id = upload('Borrador interno', 'internal')
    doc, public_id = upload('Condiciones publicadas', 'public')
    data = {'state': 'portal', 'kind': 'convocatoria'}
    assert visitor.get(f'{url}/spec-files/{public_id}').status_code == 404
    j.act('compras', 'publicity.register', {**data, 'portal_version_id': private_id}, expect=422)
    j.act('compras', 'publicity.register', {**data, 'portal_version_id': public_id})
    attached = visitor.get(url).get_json()['spec']['attachment']
    assert attached['version'] == 1 and attached['filename'] == 'condiciones.txt'
    assert api['compras'].upload(f'/api/v1/documents/{doc}/versions', {}, 'condiciones.txt', b'Propuesta de cambio').status_code == 201
    download = visitor.get(attached['url'])
    assert download.status_code == 200 and download.data == b'Condiciones publicadas'
    assert 'attachment' in download.headers['Content-Disposition']
    with app.app_context():
        newer = db.session.scalar(db.select(DocumentVersion.id).where(DocumentVersion.document_id == doc, DocumentVersion.version == 2))
    assert visitor.get(f'{url}/spec-files/{newer}').status_code == 404
    assert visitor.get(f'{url}/spec-files/{private_id}').status_code == 404
