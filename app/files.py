import os
import uuid

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import UploadedFile

files_bp = Blueprint('files', __name__, url_prefix='/files')


def _allowed_file(filename: str) -> bool:
    allowed = current_app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def _extract_text(filepath: str, ext: str) -> str:
    """Extract plain text from a PDF, DOCX, or TXT file."""
    try:
        if ext == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()

        if ext == 'pdf':
            import PyPDF2
            text_parts = []
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text() or ''
                    text_parts.append(page_text)
            return '\n'.join(text_parts)

        if ext == 'docx':
            import docx
            doc = docx.Document(filepath)
            return '\n'.join(p.text for p in doc.paragraphs)

    except Exception as exc:  # noqa: BLE001
        return f'[Text extraction failed: {exc}]'

    return ''


@files_bp.route('/', methods=['GET'])
@login_required
def list_files():
    user_files = (
        UploadedFile.query.filter_by(user_id=current_user.id)
        .order_by(UploadedFile.uploaded_at.desc())
        .all()
    )
    return jsonify([
        {
            'id': f.id,
            'original_name': f.original_name,
            'file_type': f.file_type,
            'uploaded_at': f.uploaded_at.isoformat(),
            'has_text': bool(f.extracted_text),
        }
        for f in user_files
    ])


@files_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request.'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected.'}), 400

    if not _allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Supported: PDF, TXT, DOCX.'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    safe_name = secure_filename(file.filename)
    unique_name = f'{uuid.uuid4().hex}_{safe_name}'
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, unique_name)
    file.save(filepath)

    extracted = _extract_text(filepath, ext)

    db_file = UploadedFile(
        filename=unique_name,
        original_name=safe_name,
        file_type=ext,
        extracted_text=extracted,
        user_id=current_user.id,
    )
    db.session.add(db_file)
    db.session.commit()

    return jsonify({
        'id': db_file.id,
        'original_name': db_file.original_name,
        'file_type': db_file.file_type,
        'uploaded_at': db_file.uploaded_at.isoformat(),
    }), 201


@files_bp.route('/<int:file_id>', methods=['DELETE'])
@login_required
def delete_file(file_id):
    db_file = UploadedFile.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    upload_folder = current_app.config['UPLOAD_FOLDER']
    filepath = os.path.join(upload_folder, db_file.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(db_file)
    db.session.commit()
    return jsonify({'message': 'File deleted'}), 200


@files_bp.route('/<int:file_id>/preview', methods=['GET'])
@login_required
def preview_file(file_id):
    db_file = UploadedFile.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    return jsonify({
        'id': db_file.id,
        'original_name': db_file.original_name,
        'extracted_text': db_file.extracted_text or '(no text extracted)',
    })
