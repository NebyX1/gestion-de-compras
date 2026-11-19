"""Explicación calculada por reglas (determinista) de un resultado de evaluación. No usa el modelo de lenguaje."""
from decimal import Decimal
from app.shared.contracts import display2

MODE_TEXT = {'weighted': 'factores ponderados con las escalas publicadas en el pliego', 'min_price': 'cumplimiento de mínimos y comparación exclusiva del precio total',
             'framework': 'selección autorizada en convenio marco'}


def _money(value, ccy):
    amount = f'{Decimal(display2(value)):,.2f}'.translate(str.maketrans(',.', '.,'))
    return f'{ccy} {amount}'


def _points(value):
    shown = display2(value).replace('.', ',')
    return 'menos de 0,01' if value and shown == '0,00' else shown


def _rank_value(offer, weighted):
    return Decimal(offer['score'] if weighted else offer['totals']['comparable'])


def offer_decisions(result):
    """Compara con la primera oferta admisible según el resultado exacto del motor."""
    offers = result['offers']
    winner_id = result['recommended_offer_id']
    leader = next((offer for offer in offers if offer['id'] == winner_id), None)
    if leader is None:
        leader = next((offer for offer in offers if offer['rank'] == 1), None)
    runner_up = next((offer for offer in offers if offer['rank'] == 2), None)
    weighted = result['mode'] == 'weighted'
    ccy = result['currency']
    decisions = []
    for offer in offers:
        items = []
        if offer['status'] == 'excluded':
            title = 'Fuera de la comparación'
            items = list(offer['reasons'])
            if winner_id is not None and leader is not None and offer['totals']['comparable'] is not None:
                difference = Decimal(leader['totals']['comparable']) - Decimal(offer['totals']['comparable'])
                if difference > 0:
                    items.append(f'Costaba {_money(difference, ccy)} menos que la recomendada, pero una oferta excluida no compite.')
        elif offer['status'] == 'pending':
            title = 'Falta verificar'
            items = offer['pending']
        elif leader is None:
            title = 'Sin posición calculada'
        elif result.get('tie') and _rank_value(offer, weighted) == _rank_value(leader, weighted):
            title = 'Empata en el primer lugar'
            value = (f'{_points(Decimal(leader["score"]))} puntos' if weighted
                     else _money(leader['totals']['comparable'], ccy))
            items = [f'Comparte el mejor resultado ({value}). El cálculo no desempata.']
        elif offer is leader:
            title = 'Por qué se recomienda' if winner_id is not None else 'Primera, sin recomendación'
            if result['mode'] == 'framework':
                items = ['Es la selección registrada del convenio marco; no se comparó contra otros proveedores.']
            elif weighted:
                items = [f'Cumple los requisitos excluyentes y obtuvo el mayor puntaje: {_points(Decimal(offer["score"]))} puntos.']
            else:
                items = [f'Cumple los requisitos excluyentes y tiene el menor importe comparable: {_money(offer["totals"]["comparable"], ccy)}.']
            if winner_id is None:
                items.append('Está primera entre las ofertas evaluadas, pero el resultado sigue bloqueado.')
            elif runner_up is not None:
                second = runner_up['name'].removesuffix(' · demo')
                if weighted:
                    gap = Decimal(offer['score']) - Decimal(runner_up['score'])
                    scores = {c['code']: Decimal(c['points']) for c in runner_up['criteria']}
                    gains = [c['name'] for c in offer['criteria'] if c['code'] in scores and Decimal(c['points']) > scores[c['code']]]
                    items.append(f'Superó a {second} por {_points(gap)} puntos. Sus ventajas fueron: {", ".join(gains)}.' if gains
                                 else f'Superó a {second} por {_points(gap)} puntos.')
                else:
                    saving = Decimal(runner_up['totals']['comparable']) - Decimal(offer['totals']['comparable'])
                    items.append(f'Cuesta {_money(saving, ccy)} menos que {second}, la siguiente oferta admisible.')
        else:
            title = 'Por qué quedó detrás'
            reference = leader['name'].removesuffix(' · demo')
            if weighted:
                gap = Decimal(leader['score']) - Decimal(offer['score'])
                items.append(f'Quedó {_points(gap)} puntos por debajo de {reference}.')
                by_code = {criterion['code']: criterion for criterion in offer['criteria']}
                for criterion in leader['criteria']:
                    other = by_code.get(criterion['code'])
                    if other is None:
                        continue
                    delta = Decimal(other['points']) - Decimal(criterion['points'])
                    if delta:
                        direction = 'más' if delta > 0 else 'menos'
                        items.append(f'{criterion["name"]}: obtuvo {_points(abs(delta))} puntos {direction} que {reference}.')
            else:
                current, first = offer['totals'], leader['totals']
                saving = Decimal(current['comparable']) - Decimal(first['comparable'])
                items.append(f'Su importe comparable supera al de {reference} en {_money(saving, ccy)}.')
                if current['currency'] == first['currency'] and Decimal(current['freight']) > Decimal(first['freight']):
                    if Decimal(current['commercial']) - Decimal(current['freight']) < Decimal(first['commercial']) - Decimal(first['freight']):
                        freight_gap = Decimal(current['freight']) - Decimal(first['freight'])
                        items.append(f'Sin flete era más barata, pero su flete cuesta {_money(freight_gap, current["currency"])} más.')
        decisions.append({'offer_id': offer['id'], 'title': title, 'items': items})
    return decisions


def explain(result, spec_info=None):
    ccy = result['currency']
    sections = []
    head = f'Modo de evaluación: {MODE_TEXT.get(result["mode"], result["mode"])}. Moneda de comparación: {ccy}. Motor v{result["engine_version"]}.'
    sections.append({'heading': 'Resultado', 'items': [head] + (
        [f'Recomendación calculada: {next(o["name"] for o in result["offers"] if o["id"] == result["recommended_offer_id"])}.']
        if result['recommended_offer_id'] else ['No hay recomendación: ' + ' '.join(result['blocked_reasons'])])})
    calc = []
    ref = result.get('reference_price')
    for o in result['offers']:
        t = o['totals']
        base = f'{o["name"]}: importe comercial {_money(t["commercial"], t["currency"])}; comparable {_money(t["comparable"], ccy) if t["comparable"] else "no calculable"}.'
        if o['status'] == 'admissible' and o['score'] is not None:
            parts = '; '.join(f'{c["name"]} {display2(Decimal(c["points"]))} de {display2(Decimal(c["max"]))}' for c in o['criteria'])
            base += f' Puntaje {o["score_display"]} (exacto {o["score"]}): {parts}.'
        calc.append(base)
    if result['mode'] == 'weighted' and ref:
        calc.append(f'Precio de referencia: el menor importe comparable entre ofertas admisibles ({_money(ref, ccy)}); las ofertas excluidas no integran esa base.')
    sections.append({'heading': 'La cuenta se puede repetir', 'items': calc})
    excl = [f'{o["name"]}: ' + '; '.join(o['reasons']) for o in result['offers'] if o['status'] == 'excluded']
    pend = [f'{o["name"]}: ' + '; '.join(o['pending']) for o in result['offers'] if o['status'] == 'pending']
    sections.append({'heading': 'Qué quedó fuera y por qué', 'items': excl or ['No se excluyeron ofertas.']})
    if pend:
        sections.append({'heading': 'Pendiente de verificar', 'items': pend})
    notes = ['Los importes usan aritmética decimal y redondeo de mitad hacia arriba a dos decimales por renglón; la clasificación usa el valor exacto, no el redondeado para mostrar.',
             'La verificación de requisitos es atribuida a personas; la ausencia de evidencia no se trata como incumplimiento.']
    if result.get('similar'):
        notes.append('Hay ofertas similares dentro del margen del pliego: corresponde dejar constancia de la vía elegida (art. 66); el sistema no negocia ni sortea.')
    notes += result.get('warnings', [])
    sections.append({'heading': 'Supuestos y límites', 'items': notes})
    return {'title': 'Explicación calculada por reglas', 'source': 'rules', 'sections': sections}
