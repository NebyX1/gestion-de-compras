"""Publicación de la resolución humana y de la comparación que la precedió."""
from app.ai import recommendation
from app.extensions import db
from app.infrastructure.models import AiDraft, Communication, Evaluation, PublicityRecord
from app.modules.procurement import forms as F
from app.modules.procurement.actions.execution import active_award
from app.modules.procurement.framework import action
from app.shared.contracts import display2, dstr, iso_utc
from app.shared.errors import require


def _award(ctx):
    return ctx.memo('transparency.award', lambda: active_award(ctx.case.id))


def _publication_blockers(ctx):
    if (ctx.case.flags or {}).get('public_award'):
        return ['La adjudicación ya está publicada en el portal.']
    award = _award(ctx)
    if not award:
        return ['Falta la resolución de adjudicación.']
    ev = db.session.get(Evaluation, award.evaluation_id)
    published = db.session.scalar(db.select(PublicityRecord.id).where(
        PublicityRecord.case_id == ctx.case.id, PublicityRecord.spec_version_id == ev.spec_version_id,
        PublicityRecord.kind == 'convocatoria', PublicityRecord.state == 'portal').limit(1))
    return [] if published else ['La convocatoria de este pliego debe haberse publicado en el portal.']


def _award_draft(ctx, award):
    draft_id = (ctx.case.flags or {}).get('award_ai_draft_id')
    if not draft_id:
        return None
    return db.session.scalar(db.select(AiDraft).where(AiDraft.id == draft_id, AiDraft.case_id == ctx.case.id,
                                                      AiDraft.evaluation_id == award.evaluation_id, AiDraft.kind.in_(('explicacion_comparativa', recommendation.KIND))))


def _recommendation_reason(evaluation, row):
    if evaluation.mode == 'min_price':
        total = display2(row['totals']['comparable'])
        return f"Cumple los requisitos y presenta el menor importe comparable ({evaluation.result['currency']} {total})."
    scores = ', '.join(f"{c['name']} ({display2(c['points'])} de {display2(c['max'])})" for c in row['criteria'])
    return f"Cumple los requisitos y obtiene el mayor puntaje del pliego ({row['score_display']} puntos). Puntajes por criterio: {scores}."


def _publication_form(ctx):
    award = _award(ctx)
    if not award:
        return []
    ev = db.session.get(Evaluation, award.evaluation_id)
    offers = {o['id']: o for o in ev.result['offers']}
    recommended = offers[ev.recommended_offer_id]
    preview = [f"{award.reference} · {offers[award.offer_id]['name']} · {award.currency} {display2(award.amount)}.",
               f"Recomendación del pliego: {recommended['name']}. {_recommendation_reason(ev, recommended)}",
               f"Fundamento humano: {award.grounds}"]
    if award.departure_reason:
        preview.append(f'Motivo de apartamiento: {award.departure_reason}')
    fields = []
    draft = _award_draft(ctx, award)
    if draft:
        advice = recommendation.serialize(draft, ev) if draft.kind == recommendation.KIND else None
        choice = (advice['supplier'] or 'Abstención') if advice else 'Explicación del cálculo'
        text = advice['reason'] if advice else draft.content
        details = [f'{draft.model} · {choice}. {text}', *(draft.warnings or [])]
        fields.append(F.field('include_ai', 'Revisé el aporte inicial de IA y autorizo incluirlo en la publicación', 'checkbox',
                              default=False, required=bool(advice), help=' '.join(details)))
    fields.append(F.field('confirmed', 'Revisé la resolución y autorizo su publicación junto a los renglones adjudicados',
                          'checkbox', help=' '.join(preview)))
    return fields


@action('award.publish', 'Publicar resultado en el portal', 'communication.register', {'awarded', 'ordered', 'invoicing', 'closed'},
        form=_publication_form, blockers=_publication_blockers,
        done=lambda ctx: bool((ctx.case.flags or {}).get('public_award')),
        description='Publica la oferta adjudicada, los criterios aplicados y el fundamento de la decisión de la autoridad.')
def publish_award(ctx, data):
    require(data.get('confirmed') is True, 'validation', 'Confirmá la revisión del resultado público.', 422, {'confirmed': 'Obligatorio.'})
    award = _award(ctx)
    evaluation = db.session.get(Evaluation, award.evaluation_id)
    offers = {row['id']: row for row in evaluation.result['offers']}
    winner, recommended = offers[award.offer_id], offers[evaluation.recommended_offer_id]
    initial = _award_draft(ctx, award)
    require(not initial or initial.kind != recommendation.KIND or data.get('include_ai') is True, 'validation',
            'Revisá la recomendación inicial de IA para publicarla junto a la decisión humana.', 422, {'include_ai': 'Revisión requerida.'})
    draft = initial if data.get('include_ai') is True else None
    require(data.get('include_ai') is not True or draft, 'validation',
            'Esta adjudicación no tiene una explicación inicial de IA asociada.', 422, {'include_ai': 'Sin explicación previa a la decisión.'})
    request_lines = {line.id: line for line in ctx.lines}
    advice = recommendation.serialize(draft, evaluation) if draft and draft.kind == recommendation.KIND else None
    lines = [{'description': request_lines[line.request_line_id].description, 'unit': request_lines[line.request_line_id].unit,
              'quantity': dstr(line.quantity), 'unit_price': dstr(line.unit_price), 'tax_rate': dstr(line.tax_rate), 'amount': dstr(line.amount)}
             for line in sorted(award.lines, key=lambda item: request_lines[item.request_line_id].position)]
    # La proyección contiene exclusivamente campos públicos, fijados a la versión usada para adjudicar.
    snapshot = {
        'supplier': winner['name'], 'amount': dstr(award.amount), 'currency': award.currency, 'reference': award.reference,
        'awarded_at': iso_utc(award.created_at), 'published_at': iso_utc(ctx.now), 'grounds': award.grounds,
        'departure_reason': award.departure_reason, 'followed_recommendation': award.offer_id == evaluation.recommended_offer_id,
        'recommended_supplier': recommended['name'], 'recommendation_reason': _recommendation_reason(evaluation, recommended),
        'ai_explanation': advice['reason'] if advice else (draft.content if draft else None), 'ai_model': draft.model if draft else None,
        'ai_recommended_supplier': advice['supplier'] if advice else None, 'ai_abstained': bool(advice and advice['abstained']),
        'followed_ai_recommendation': (award.offer_id == advice['offer_id']) if advice and advice['offer_id'] is not None else None,
        'evaluation_version': evaluation.version, 'lines': lines,
        'freight': winner['totals']['freight'], 'discount': winner['totals']['discount'],
    }
    ctx.case.flags = {**(ctx.case.flags or {}), 'public_award': snapshot}
    publication = Communication(case_id=ctx.case.id, award_id=award.id, kind='publicacion', state='portal',
                                reference=award.reference, created_by=ctx.user.id)
    db.session.add(publication)
    db.session.flush()
    return {'type': 'communication', 'id': publication.id, 'reference': award.reference, 'reason': 'Adjudicación publicada en el portal.',
            'details': {'award_id': award.id, 'evaluation_id': evaluation.id, 'ai_draft_id': draft.id if draft else None}}
