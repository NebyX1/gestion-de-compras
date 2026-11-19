"""Semilla demo: idempotencia, compuerta de la CLI y usuarios por rol."""
import json
import pytest
from app.ai.assist import anonymous_comparison_json
from app.demo_seed import seed, CASES, SUPPLIERS
from app.extensions import db
from app.infrastructure.models import Evaluation, Offer, ProcurementCase, Supplier, User, UserRole
from app.modules.evaluation.explain import offer_decisions
from app.modules.identity.permissions import ROLE_NAMES


@pytest.fixture(scope='module')
def seeded(app):
    with app.app_context():
        first = seed()
        second = seed()
    return first, second


def test_seed_is_idempotent(app, seeded):
    first, second = seeded
    assert len(first['credentials']) == len(ROLE_NAMES)
    assert second['credentials'] == []
    assert second['suppliers_created'] == 0
    with app.app_context():
        assert db.session.query(User).filter(User.username.like('demo-%')).count() == len(ROLE_NAMES)
        assert db.session.query(Supplier).filter(Supplier.code.like('DEMO-PRV-%')).count() == len(SUPPLIERS)
        assert db.session.query(ProcurementCase).filter_by(is_demo=True).count() == len(CASES)
        demo_case = db.session.query(ProcurementCase).filter(
            ProcurementCase.need_text.like('%DEMO-OFERTAS%')).one()
        evaluation = db.session.query(Evaluation).filter_by(case_id=demo_case.id, status='current').one()
        assert demo_case.area.name == 'Pruebas locales'
        assert demo_case.status == 'evaluation'
        assert db.session.query(Offer).filter_by(case_id=demo_case.id, status='data_recorded').count() == 3
        assert evaluation.recommended_offer_id is not None
        assert any(row['status'] != 'admissible' for row in evaluation.result['offers'])
    assert [c['code'] for c in first['cases']] == [c['code'] for c in second['cases']]


def test_every_role_gets_a_demo_user(app, seeded):
    with app.app_context():
        for role in ROLE_NAMES:
            user = db.session.query(User).filter_by(username=f'demo-{role}').one()
            assert user.is_demo and user.must_change_password and user.is_active
            assert db.session.query(UserRole).filter_by(user_id=user.id, role_code=role, revoked_at=None).count() == 1


def test_seed_publishes_three_open_examples_and_one_human_award(app, seeded):
    assert not [(r['html_id'], r['failure']) for r in seeded[0]['cases'] if r['html_id'].startswith('PORTAL-') and r.get('failure')]
    public = app.test_client()
    listing = public.get('/api/v1/public/tenders?per_page=100').get_json()['items']
    examples = [item for item in listing if item['is_demo']]
    assert [item['status'] for item in examples] == ['open', 'open', 'open', 'awarded']
    example = next(row for row in examples if row['status'] == 'awarded')
    detail = public.get('/api/v1/public/tenders/' + example['code']).get_json()
    award = detail['award']
    assert award['supplier'] == 'Camino Seguro · demo' and award['recommended_supplier'] == 'Señal Vial Serrana · demo'
    assert award['evaluation_version'] == 1 and award['lines'][0]['amount'] == '336720.00'
    assert award['followed_recommendation'] is False and award['departure_reason'] and award['ai_explanation'] is None


def test_comparison_examples_show_freight_pending_review_and_tie(app, seeded):
    with app.app_context():
        def result(key):
            case = db.session.query(ProcurementCase).filter(ProcurementCase.need_text.like(f'%{key}%')).one()
            assert case.area.name == 'Pruebas locales'
            return db.session.query(Evaluation).filter_by(case_id=case.id).one().result

        uniforms = result('DEMO-VESTUARIO')
        winner = next(row for row in uniforms['offers'] if row['id'] == uniforms['recommended_offer_id'])
        assert winner['name'] == 'Vestir Trabajo · demo'
        assert any(row['status'] == 'excluded' for row in uniforms['offers'])
        gravel = result('DEMO-CAMINERIA')
        assert gravel['recommended_offer_id'] is None
        assert any(row['status'] == 'pending' for row in gravel['offers'])
        paper = result('DEMO-PAPEL')
        assert paper['recommended_offer_id'] is None
        assert paper['tie']
        paper['offers'][1]['totals']['comparable'] += '0'

        def by_name(data):
            names = {row['id']: row['name'] for row in data['offers']}
            return {names[row['offer_id']]: row for row in offer_decisions(data)}

        assert 'Sin flete era más barata' in ' '.join(by_name(uniforms)['Textil de la Sierra · demo']['items'])
        assert by_name(gravel)['Cantera del Este · demo']['title'] == 'Falta verificar'
        assert [row['title'] for row in offer_decisions(paper)] == ['Empata en el primer lugar'] * 2

        computers = result('DEMO-INFORMATICA')
        decisions = by_name(computers)
        assert len(decisions) == 5
        assert 'Entrega, Garantía' in ' '.join(decisions['Red Serrana · demo']['items'])
        assert 'Precio:' in ' '.join(decisions['Nexo Digital · demo']['items'])
        assert 'puntos más' in ' '.join(decisions['Nexo Digital · demo']['items'])
        assert len(by_name(result('DEMO-SENALIZACION'))) == 5

        truck = result('DEMO-TALLER')
        assert truck['recommended_offer_id'] is None
        decisions = offer_decisions(truck)
        assert len(decisions) == 4
        assert all(row['title'] == 'Fuera de la comparación' and row['items'] for row in decisions)


def test_ai_comparison_uses_only_anonymous_signals(app, seeded):
    with app.app_context():
        case = db.session.query(ProcurementCase).filter(ProcurementCase.need_text.like('%DEMO-VESTUARIO%')).one()
        evaluation = db.session.query(Evaluation).filter_by(case_id=case.id).one()
        payload = anonymous_comparison_json(evaluation)
        signals = json.loads(payload)
        assert signals['metodo'] == 'min_price'
        assert signals['hay_recomendacion']
        assert signals['hay_excluida_mas_barata_que_la_recomendada']
        assert all(isinstance(value, bool) for key, value in signals.items() if key != 'metodo')
        assert case.code not in payload
        for offer in evaluation.result['offers']:
            assert offer['name'] not in payload
            assert offer['totals']['comparable'] not in payload


def test_seed_passwords_are_random_and_not_stored_in_clear(seeded):
    first, _ = seeded
    passwords = [pw for _, pw in first['credentials']]
    assert len(set(passwords)) == len(passwords)
    assert all(len(pw) == 18 for pw in passwords)


def test_cli_rejects_without_allow_demo_seed(app):
    runner = app.test_cli_runner()
    previous = app.config['ALLOW_DEMO_SEED']
    app.config['ALLOW_DEMO_SEED'] = False
    try:
        result = runner.invoke(args=['seed-demo', '--confirm'])
    finally:
        app.config['ALLOW_DEMO_SEED'] = previous
    assert result.exit_code != 0
    assert 'ALLOW_DEMO_SEED' in result.output


def test_cli_requires_confirm(app):
    result = app.test_cli_runner().invoke(args=['seed-demo'])
    assert result.exit_code != 0
    assert '--confirm' in result.output
