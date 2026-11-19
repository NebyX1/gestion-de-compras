import re
from app.modules.procurement import inputs as inp
from app.shared.errors import require

TAX_ID = re.compile(r'^[A-Za-z0-9.\-]{5,30}$')


def contact_email(data, key='contact_email', required=True):
    email = inp.text(data, key, 'Correo de contacto', 3, 120, required=required)
    if email is None:
        return None
    require(re.fullmatch(r'[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+', email), 'validation', 'Revisá el correo de contacto.', 422,
            {key: 'Ingresá una dirección de correo válida.'})
    return email.lower()
