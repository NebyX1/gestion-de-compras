from app.extensions import db
from app.infrastructure.models import Document, DocumentVersion, PublicityRecord


def eligible_versions(case_id):
    """Una constancia interna o un original de un sobre nunca puede pasar a ser pliego público."""
    return (db.select(DocumentVersion).join(Document, Document.id == DocumentVersion.document_id)
            .where(Document.case_id == case_id, Document.kind == 'pliego', Document.classification == 'public',
                   Document.envelope_id.is_(None), Document.status == 'active'))


def published_version(case_id, spec_id):
    pinned_id = (db.select(PublicityRecord.portal_version_id)
                 .where(PublicityRecord.case_id == case_id, PublicityRecord.spec_version_id == spec_id,
                        PublicityRecord.kind == 'convocatoria', PublicityRecord.state == 'portal', PublicityRecord.published_at.is_not(None))
                 .order_by(PublicityRecord.published_at.desc(), PublicityRecord.id.desc()).limit(1).scalar_subquery())
    return db.session.scalar(eligible_versions(case_id).where(DocumentVersion.id == pinned_id))
