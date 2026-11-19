"""Proyección pública. Solo las convocatorias publicadas en este portal salen de esta consulta."""
from flask import url_for
from sqlalchemy import and_, case as sql_case, func, or_
from app.extensions import db
from app.infrastructure.models import Area, DeadlineExtension, ProcurementCase, PublicityRecord, RequestLine, SpecVersion
from app.modules.procurement.states import STATUS_LABEL
from app.modules.rules.service import PROCEDURE_LABELS
from app.shared.contracts import dstr, iso_utc, utcnow
from app.shared.errors import require
from .pliego import published_version


def catalog_query(now):
    case, spec = ProcurementCase, SpecVersion
    publications = (db.select(PublicityRecord.case_id, PublicityRecord.spec_version_id,
                              func.max(PublicityRecord.published_at).label('published_at'))
                    .where(PublicityRecord.state == 'portal', PublicityRecord.kind == 'convocatoria',
                           PublicityRecord.published_at.is_not(None))
                    .group_by(PublicityRecord.case_id, PublicityRecord.spec_version_id).subquery())
    extension = (db.select(DeadlineExtension.new_deadline)
                 .where(DeadlineExtension.case_id == case.id, DeadlineExtension.created_at >= spec.approved_at)
                 .order_by(DeadlineExtension.id.desc()).limit(1).correlate(case, spec).scalar_subquery())
    deadline = func.coalesce(extension, spec.offer_deadline)
    awarded = func.json_extract(case.flags, '$.public_award.supplier').is_not(None)
    status = sql_case((awarded, 'awarded'), (and_(case.status == 'receiving_offers', deadline > now), 'open'), else_='closed')
    query = (db.select(case, spec, Area.name, publications.c.published_at, deadline, status).select_from(case)
             .join(publications, publications.c.case_id == case.id)
             .join(spec, and_(spec.id == publications.c.spec_version_id, spec.case_id == case.id))
             .join(Area, Area.id == case.area_id)
             .where(spec.status == 'approved', case.status.not_in(('draft', 'submitted', 'preparation'))))
    return query, status


def summary(row):
    case, spec, area, published, deadline, status = row
    label = {'open': 'Abierta', 'awarded': 'Adjudicada'}.get(status, 'Recepción cerrada')
    if status == 'closed' and case.status in ('cancelled', 'deserted', 'offers_rejected'):
        label = STATUS_LABEL[case.status]
    return {'code': case.code, 'title': case.title, 'area': area, 'procedure_type': case.procedure_type,
            'procedure_label': PROCEDURE_LABELS.get(case.procedure_type), 'status': status, 'status_label': label,
            'published_at': iso_utc(published), 'deadline': iso_utc(deadline), 'currency': spec.currency,
            'can_submit': status == 'open' and spec.reception_channel == 'portal', 'is_demo': case.is_demo}


def list_tenders(search, status_filter, page, per_page):
    query, status = catalog_query(utcnow())
    if search:
        query = query.where(or_(ProcurementCase.title.contains(search, autoescape=True),
                                ProcurementCase.code.contains(search, autoescape=True), Area.name.contains(search, autoescape=True)))
    if status_filter:
        query = query.where(status == status_filter)
    total = db.session.scalar(db.select(func.count()).select_from(query.subquery()))
    rows = db.session.execute(query.order_by((status == 'open').desc(), query.selected_columns.published_at.desc(), ProcurementCase.id.desc())
                              .limit(per_page).offset((page - 1) * per_page))
    return {'items': [summary(row) for row in rows], 'total': total, 'page': page, 'per_page': per_page}


def published_tender(code):
    query, _ = catalog_query(utcnow())
    row = db.session.execute(query.where(ProcurementCase.code == code)).first()
    require(row is not None, 'not_found', 'No se encontró la convocatoria publicada.', 404)
    return row


def detail(code):
    row = published_tender(code)
    case, spec = row[:2]
    file = published_version(case.id, spec.id)
    lines = db.session.scalars(db.select(RequestLine).where(RequestLine.case_id == case.id).order_by(RequestLine.position))
    return {**summary(row), 'need_text': case.need_text, 'delivery_place': case.delivery_place,
            'lines': [{'id': line.id, 'position': line.position, 'description': line.description,
                       'quantity': dstr(line.quantity), 'unit': line.unit} for line in lines],
            'spec': {'id': spec.id, 'version': spec.version, 'minimum_text': spec.minimum_text, 'mode': spec.mode,
                     'attachment': {'filename': file.original_name, 'version': file.version, 'size': file.size,
                                    'url': url_for('portal.download_pliego', code=case.code, version_id=file.id)} if file else None,
                     'reception_channel': spec.reception_channel, 'reception_place': spec.reception_place, 'delivery_terms': spec.delivery_terms,
                     'requirements': [{'code': r.code, 'text': r.text, 'essential': r.essential, 'kind': r.kind,
                                       'attribute': r.attribute, 'operator': r.operator, 'threshold': dstr(r.threshold), 'unit': r.unit}
                                      for r in spec.requirements],
                     'criteria': [{'name': c.name, 'weight': dstr(c.weight), 'type': c.type, 'attribute': c.attribute,
                                   'scale': c.scale or [], 'description': c.description} for c in spec.criteria]},
            'award': (case.flags or {}).get('public_award')}
