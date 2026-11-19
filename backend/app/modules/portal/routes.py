import json
from io import BytesIO
from flask import Blueprint, current_app, jsonify, request, send_file
from app.infrastructure.storage import get_document_storage
from app.modules.procurement import inputs as inp
from app.shared.errors import ApiError, require
from . import catalog, submission
from .pliego import published_version

bp = Blueprint('portal', __name__, url_prefix='/api/v1/public/tenders')


@bp.get('')
def index():
    args = request.args
    page = inp.integer(args, 'page', 'Página', required=False, minimum=1, maximum=1000000, default=1)
    size = inp.integer(args, 'per_page', 'Tamaño de página', required=False, minimum=1, maximum=100, default=12)
    status = inp.choice(args, 'status', 'Estado', ('open', 'closed', 'awarded'), required=False)
    search = inp.text(args, 'q', 'Búsqueda', required=False, max_len=200)
    return jsonify(catalog.list_tenders(search, status, page, size))


@bp.get('/<code>')
def show(code):
    return jsonify(catalog.detail(code))


@bp.get('/<code>/spec-files/<int:version_id>')
def download_pliego(code, version_id):
    case, spec = catalog.published_tender(code)[:2]
    file = published_version(case.id, spec.id)
    require(file and file.id == version_id, 'not_found', 'Archivo no disponible en esta convocatoria.', 404)
    response = send_file(BytesIO(get_document_storage().read(file.storage_key)), mimetype=file.mime,
                         as_attachment=True, download_name=file.original_name, conditional=False)
    response.headers['Content-Security-Policy'] = "sandbox; default-src 'none'; frame-ancestors 'none'"
    response.headers['Cache-Control'] = 'no-store'
    return response


def json_object():
    data = request.get_json(silent=True)
    require(isinstance(data, dict), 'invalid_json', 'Los datos del formulario son inválidos.', 422)
    return data


@bp.post('/<code>/verification')
def verification(code):
    return jsonify(submission.send_code(code, json_object())), 202


@bp.post('/<code>/offers')
def submit(code):
    attachment = None
    if request.mimetype == 'multipart/form-data':
        try:
            data = json.loads(request.form.get('offer', ''))
        except ValueError as exc:
            raise ApiError('invalid_json', 'Los datos del formulario son inválidos.', 422) from exc
        require(isinstance(data, dict), 'invalid_json', 'Los datos del formulario son inválidos.', 422)
        files = request.files.getlist('file')
        require(len(files) <= 1, 'validation', 'Seleccioná un único archivo.', 422)
        if files:
            upload = files[0]
            limit = current_app.config['MAX_UPLOAD_MB'] * 1024 * 1024
            content = upload.stream.read(limit + 1)
            require(len(content) <= limit, 'file_size', 'El archivo supera el tamaño permitido.', 413)
            require(upload.filename, 'validation', 'Falta el nombre del archivo adjunto.', 422)
            attachment = (upload.filename, content)
    else:
        data = json_object()
    receipt, status = submission.receive(code, data, request.headers.get('Idempotency-Key'), attachment)
    return jsonify(receipt), status
