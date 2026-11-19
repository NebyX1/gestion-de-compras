"""Identidad sintética para el modo de pruebas local."""
import secrets
from app.extensions import db
from app.infrastructure import audit
from app.infrastructure.models import Area, User, UserRole
from app.shared.contracts import utcnow

LOCAL_TEST_USERNAME = 'local-test-compras'
LOCAL_TEST_EMAIL = 'local-test-compras@local.invalid'
LOCAL_TEST_AREA_CODE = 'LOCAL-TEST'


def ensure_local_test_user():
    area = db.session.scalar(db.select(Area).where(Area.code == LOCAL_TEST_AREA_CODE))
    if area and (area.name != 'Pruebas locales' or not area.active):
        raise RuntimeError('El área local de pruebas colisiona con una configuración existente.')
    if not area:
        area = Area(code=LOCAL_TEST_AREA_CODE, name='Pruebas locales')
        db.session.add(area)
        db.session.flush()

    user_by_name = db.session.scalar(db.select(User).where(User.username == LOCAL_TEST_USERNAME))
    user_by_email = db.session.scalar(db.select(User).where(User.email == LOCAL_TEST_EMAIL))
    if user_by_name and user_by_name is not user_by_email:
        raise RuntimeError('El usuario local de pruebas colisiona con una cuenta existente.')
    if user_by_email and user_by_email is not user_by_name:
        raise RuntimeError('El correo local de pruebas colisiona con una cuenta existente.')

    user = user_by_name
    created = user is None
    if created:
        user = User(
            username=LOCAL_TEST_USERNAME,
            email=LOCAL_TEST_EMAIL,
            full_name='Usuario de prueba local (Compras)',
            area_id=area.id,
            is_demo=True,
        )
        user.set_password(secrets.token_urlsafe(48))
        db.session.add(user)
        db.session.flush()
    elif not user.is_demo or user.full_name != 'Usuario de prueba local (Compras)':
        raise RuntimeError('El usuario local de pruebas colisiona con una cuenta existente.')
    else:
        user.area_id = area.id

    assignment = db.session.scalar(
        db.select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_code == 'compras',
            UserRole.revoked_at.is_(None),
        )
    )
    if not assignment:
        db.session.add(UserRole(
            user_id=user.id,
            role_code='compras',
            area_id=area.id,
            valid_from=utcnow(),
            legal_basis='Perfil sintético de testing local.',
        ))
    else:
        assignment.area_id = area.id

    if created:
        audit.record(None, 'testing.local_user_created', 'user', user.id, reason=LOCAL_TEST_USERNAME, role_code='compras')
    db.session.commit()
    return user


def get_local_test_user():
    user = db.session.scalar(db.select(User).where(User.username == LOCAL_TEST_USERNAME))
    if not user or not user.is_active or not user.area_id or not db.session.scalar(
        db.select(Area.id).where(Area.id == user.area_id, Area.active.is_(True))
    ) or not db.session.scalar(
        db.select(UserRole.id).where(
            UserRole.user_id == user.id,
            UserRole.role_code == 'compras',
            UserRole.revoked_at.is_(None),
            UserRole.area_id == user.area_id,
        )
    ):
        raise RuntimeError('Falta el usuario local de pruebas; reiniciá el stack para ejecutar la inicialización.')
    return user
