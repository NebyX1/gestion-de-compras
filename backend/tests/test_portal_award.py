"""Dos presentaciones públicas, recomendación explicada y adjudicación fundada a otra oferta."""
import re
import json
import pytest

from app.ai.client import _payload
from app.ai.recommendation import readable_reason
from tests.conftest import Api
from tests.flow import Journey, LIGHT_SPEC, key


def test_structured_format_is_only_sent_to_native_local_models():
    schema = {'type': 'object', 'properties': {'oferta': {'enum': ['OF123', None]}}}
    for host, model, native in [('http://127.0.0.1:11434', 'phi4-mini:3.8b', True),
                                ('http://host.docker.internal:11434', 'ejemplo:cloud', False),
                                ('http://host.docker.internal:11434', 'ejemplo-cloud', False),
                                ('https://ollama.com', 'ejemplo', False)]:
        payload = _payload({'host': host, 'model': model}, [], False, {'temperature': 0}, schema)
        assert payload.get('format') == (schema if native else None)


def test_ai_reason_uses_readable_references_without_supplier_names():
    aliases = {'OF0123456789AB': 17, 'OF8888AABBCCDD': 22}
    reason = 'La oferta OF0123456789AB cumple. El proveedor OF8888AABBCCDD entrega más tarde que OF0123456789AB.'
    assert readable_reason(reason, aliases, 17) == 'La oferta recomendada cumple. El proveedor alternativo entrega más tarde que la propuesta recomendada.'


def submit_bid(app, route, spec_id, line_id, name, tax_id, price, days, warranty):
    bidder = Api(app)
    bidder._refresh()
    email = f'{tax_id}@tests.invalid'
    challenge = bidder.post(route + '/verification', json={'tax_id': tax_id, 'email': email})
    assert challenge.status_code == 202, challenge.get_json()
    code = re.search(r'es (\d{6})', app.config['MAIL_CAPTURE'][-1].body).group(1)
    response = bidder.post(route + '/offers', headers={'Idempotency-Key': key()}, json={
        'supplier_name': name, 'tax_id': tax_id, 'email': email, 'spec_id': spec_id, 'verification_code': code,
        'lines': [{'request_line_id': line_id, 'unit_price': price, 'tax_rate': '22'}],
        'prices_include_tax': False, 'freight': '0', 'delivery_days': days, 'warranty_months': warranty,
        'technical_description': 'Se suministran luminarias conformes al pliego y con la garantía indicada.',
        'accepted_terms': True,
    })
    assert response.status_code == 201, response.get_json()


@pytest.mark.parametrize('choice', ['reglas', 'modelo', 'abstencion'])
def test_public_award_keeps_initial_advice_and_human_departure(app, api, world, monkeypatch, choice):
    j = Journey(app, api, world, spec={**LIGHT_SPEC, 'reception_channel': 'portal'})
    j.create()
    j.prepare()
    route = f'/api/v1/public/tenders/{j.code}'
    public = app.test_client()
    assert public.get(route).status_code == 404
    j.act('compras', 'publicity.register', {'kind': 'convocatoria', 'state': 'portal'})
    spec = j.detail()['spec']
    line = j.detail()['lines'][0]['id']
    bidders = [('Serrana', '219991230011', '12500', 10, 60), ('Este', '219991230022', '11500', 20, 36)]
    for name, tax, price, days, warranty in bidders:
        submit_bid(app, route, spec['id'], line, name, tax, price, days, warranty)
    assert j.detail()['offers'] == []
    j.act('compras', 'spec.save', {'spec': spec, 'change_reason': 'Cambiar las reglas luego de recibir ofertas.'}, expect=422)
    detail = j.open()
    offers = {offer['supplier']: offer for offer in detail['offers']}
    requirement = next(r for r in spec['requirements'] if r['kind'] == 'review')
    for offer in offers.values():
        assert offer['data_version'] == 1
        j.act('tecnica', 'requirement.review', {'offer_id': offer['id'], 'requirement_id': requirement['id'], 'result': 'met',
                                                'note': 'Verificación técnica de los bienes.'})
    ev = j.evaluate()
    assert ev['recommended_offer_id'] == offers['Serrana']['id']
    ai_path = f'/api/v1/ai/cases/{j.code}/explain'
    # El proveedor puede no estar configurado. El motor preserva y atribuye su resultado.
    assert api['tecnica'].post(ai_path, json={'confirm_egress': True}).status_code == 503
    assert j.detail()['evaluation']['ai_explanation'] is None
    initial = 'La oferta recomendada obtiene una ventaja en la escala de garantía y en la de entrega.'

    def model(messages, options):
        prompt = messages[-1]['content']
        assert 'ventaja_frente_a_segunda_en_plazo_entrega' in prompt
        assert 'ventaja_frente_a_segunda_en_garantia' in prompt
        assert 'desventaja_frente_a_segunda_en_precio' in prompt
        assert all(name not in prompt and price not in prompt for name, _, price, _, _ in bidders)
        return initial, {'model': 'modelo-de-prueba', 'latency_ms': 1}

    monkeypatch.setattr('app.ai.client.chat', model)
    ai = api['tecnica'].post(ai_path, json={'confirm_egress': True})
    assert ai.status_code == 201, ai.get_json()
    assert j.detail()['evaluation']['ai_explanation']['content'] == initial
    recommend_path = f'/api/v1/ai/cases/{j.code}/recommend'
    assert api['tecnica'].post(recommend_path, json={}).status_code == 422
    assert api['solicitante'].post(recommend_path, json={'confirm_egress': True}).status_code == 403
    monkeypatch.setattr('app.ai.client.chat', lambda *_: (json.dumps({'oferta': 'fuera-del-llamado', 'fundamento': initial}),
                                                         {'model': 'modelo-de-prueba', 'latency_ms': 1}))
    assert api['tecnica'].post(recommend_path, json={'confirm_egress': True}).status_code == 502
    assert j.detail()['evaluation']['ai_advice'] is None
    reason = ('El alcance documentado no permite preferir una alternativa.' if choice == 'abstencion' else
              'La alternativa admisible de menor costo cubre el plazo de entrega y la garantía requeridos.')

    def choose(messages, options, schema):
        payload = json.loads(messages[-1]['content'])
        assert len(payload['ofertas']) == 2 and len(payload['criterios']) == 3
        assert options['temperature'] == 0 and set(schema['properties']['oferta']['anyOf'][0]['enum']) == {o['alias'] for o in payload['ofertas']}
        assert all(name not in messages[-1]['content'] and price not in messages[-1]['content'] for name, _, price, _, _ in bidders)
        lowest = min(payload['ofertas'], key=lambda row: float(row['indice_precio']))
        raw = json.dumps({'oferta': lowest['alias'] if choice != 'abstencion' else None, 'fundamento': reason})
        return f'```json\n{raw}\n```', {'model': 'modelo-de-prueba', 'latency_ms': 1}

    if choice == 'reglas':
        def recalculate(messages, options, schema):
            j.act('tecnica', 'evaluation.run')
            return choose(messages, options, schema)

        monkeypatch.setattr('app.ai.client.chat', recalculate)
        assert api['tecnica'].post(recommend_path, json={'confirm_egress': True}).status_code == 409
        ev = j.detail()['evaluation']
        assert ev['version'] == 2 and ev['ai_advice'] is None

    monkeypatch.setattr('app.ai.client.chat', choose)
    response = api['tecnica'].post(recommend_path, json={'confirm_egress': True})
    assert response.status_code == 201, response.get_json()
    ai_choice = response.get_json()
    assert ai_choice['supplier'] == ('Este' if choice != 'abstencion' else None) and ai_choice['abstained'] == (choice == 'abstencion')
    monkeypatch.setattr('app.ai.client.chat', lambda *_: pytest.fail('La recomendación inicial ya está fijada'))
    assert api['tecnica'].post(recommend_path + '?force=1', json={'confirm_egress': True}).get_json() == ai_choice
    assert j.detail()['evaluation']['ai_advice'] == ai_choice
    j.act('tecnica', 'evaluation.send', {'reference': 'ENV-PRUEBA', 'reason': 'Comparación revisada.'})
    selected = 'Serrana' if choice == 'reglas' else 'Este'
    other = offers[selected]
    j.act('comision', 'opinion.register', {'offer_id': ev['recommended_offer_id'], 'reference': 'DICT-PRUEBA',
                                           'reason': 'La mayor garantía y el plazo de entrega respaldan la recomendación.'})
    j.act('control', 'control.register', {'offer_id': other['id'], 'result': 'sin_observacion', 'reference': 'CTRL-PRUEBA',
                                          'reason': 'Control del gasto sobre la alternativa propuesta.'})
    rupe = api['compras'].post(f"/api/v1/suppliers/{other['supplier_id']}/status",
                               json={'kind': 'rupe', 'state': 'activo', 'evidence_ref': 'RUPE-PRUEBA'})
    assert rupe.status_code == 201
    decision = {'offer_id': other['id'], 'reference': 'RES-PORTAL', 'reason': 'Los plazos acreditados satisfacen la necesidad del área.',
                'verified': True}
    j.act('ordenador', 'award.register', decision, expect=422)
    departure = ('La autoridad mantiene la ponderación y elige la mayor garantía y entrega más rápida.' if choice == 'reglas' else
                 'Se prioriza el menor gasto documentado; ambas ofertas satisfacen el plazo necesario.')
    j.act('ordenador', 'award.register', {**decision, 'departure_reason': departure})
    assert public.get(route).get_json()['award'] is None
    j.act('tecnica', 'award.publish', {'confirmed': True}, expect=403)
    j.act('compras', 'award.publish', {}, expect=422)
    # Otro borrador posterior no sustituye a la explicación disponible al resolver.
    monkeypatch.setattr('app.ai.client.chat', lambda *_: ('Explicación nueva, posterior a la decisión.', {'model': 'nuevo', 'latency_ms': 1}))
    assert api['compras'].post(ai_path + '?force=1', json={'confirm_egress': True}).status_code == 201
    j.act('compras', 'award.publish', {'include_ai': True, 'confirmed': True})
    award = public.get(route).get_json()['award']
    assert award['supplier'] == selected and award['recommended_supplier'] == 'Serrana'
    assert award['followed_recommendation'] == (choice == 'reglas')
    assert award['grounds'] == decision['reason'] and award['departure_reason'] == departure
    assert award['ai_explanation'] == reason and award['ai_model'] == 'modelo-de-prueba'
    assert award['ai_recommended_supplier'] == ai_choice['supplier'] and award['ai_abstained'] == ai_choice['abstained']
    assert award['followed_ai_recommendation'] == (None if choice == 'abstencion' else choice == 'modelo')
    assert award['evaluation_version'] == ev['version'] and 'Garantía' in award['recommendation_reason']
    assert award['amount'] == ('1830000.00' if selected == 'Serrana' else '1683600.00') and award['lines'][0]['description'] == 'Luminaria LED 150 W'
    assert 'authority_snapshot' not in award and '@tests.invalid' not in str(award)
    j.act('compras', 'award.publish', {'confirmed': True}, expect=422)
