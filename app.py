import os
import uuid
from datetime import datetime

from flask import (Flask, render_template, redirect, url_for, request,
                   flash, jsonify)
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db, login_manager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-electrical-engineering-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///edx.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx'}
MAX_CONTEXT_CHUNK_SIZE = 1000
MAX_CHAT_TITLE_LENGTH = 60
MAX_FALLBACK_CONTEXT_SIZE = 500

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

from models import User, File, ChatSession, ChatMessage  # noqa: E402


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def allowed_file(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS)


def extract_text(filepath, file_type):
    try:
        if file_type == 'pdf':
            import PyPDF2
            text_parts = []
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text_parts.append(page.extract_text() or '')
            return '\n'.join(text_parts)
        elif file_type == 'docx':
            import docx
            doc = docx.Document(filepath)
            return '\n'.join(p.text for p in doc.paragraphs)
        elif file_type == 'txt':
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return f.read()
            except UnicodeDecodeError:
                with open(filepath, 'r', encoding='latin-1') as f:
                    return f.read()
    except Exception:
        return ''
    return ''


def get_rag_context(message, user_files):
    if not user_files:
        return ''
    message_words = set(message.lower().split())
    scored = []
    for f in user_files:
        if not f.extracted_text:
            continue
        file_words = set(f.extracted_text.lower().split())
        overlap = len(message_words & file_words)
        if overlap > 0:
            scored.append((overlap, f))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:3]
    chunks = []
    for _, f in top:
        chunks.append(f'--- {f.original_filename} ---\n{f.extracted_text[:MAX_CONTEXT_CHUNK_SIZE]}')
    return '\n\n'.join(chunks)


def query_ollama(prompt):
    import requests as req
    try:
        resp = req.post(
            'http://localhost:11434/api/generate',
            json={'model': 'mistral', 'prompt': prompt, 'stream': False},
            timeout=30
        )
        resp.raise_for_status()
        return resp.json().get('response', '').strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    recent_files = (File.query
                    .filter_by(user_id=current_user.id)
                    .order_by(File.uploaded_at.desc())
                    .limit(5).all())
    recent_sessions = (ChatSession.query
                       .filter_by(user_id=current_user.id)
                       .order_by(ChatSession.updated_at.desc())
                       .limit(5).all())
    total_files = File.query.filter_by(user_id=current_user.id).count()
    total_sessions = ChatSession.query.filter_by(user_id=current_user.id).count()
    return render_template('dashboard.html',
                           recent_files=recent_files,
                           recent_sessions=recent_sessions,
                           total_files=total_files,
                           total_sessions=total_sessions)


@app.route('/files')
@login_required
def files():
    user_files = (File.query
                  .filter_by(user_id=current_user.id)
                  .order_by(File.uploaded_at.desc())
                  .all())
    return render_template('files.html', files=user_files)


@app.route('/files/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('files'))
    f = request.files['file']
    if f.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('files'))
    if not allowed_file(f.filename):
        flash('File type not allowed. Use PDF, TXT, or DOCX.', 'danger')
        return redirect(url_for('files'))

    ext = f.filename.rsplit('.', 1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    f.save(save_path)

    text = extract_text(save_path, ext)

    file_record = File(
        filename=unique_name,
        original_filename=f.filename,
        file_type=ext,
        extracted_text=text,
        user_id=current_user.id
    )
    db.session.add(file_record)
    db.session.commit()
    flash(f'"{f.filename}" uploaded successfully.', 'success')
    return redirect(url_for('files'))


@app.route('/files/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    file_record = File.query.filter_by(id=file_id, user_id=current_user.id).first_or_404()
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_record.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(file_record)
    db.session.commit()
    flash('File deleted.', 'success')
    return redirect(url_for('files'))


@app.route('/chat')
@login_required
def chat():
    sessions = (ChatSession.query
                .filter_by(user_id=current_user.id)
                .order_by(ChatSession.updated_at.desc())
                .all())
    return render_template('chat.html', sessions=sessions, active_session=None, messages=[])


@app.route('/chat/<int:session_id>')
@login_required
def chat_session(session_id):
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    sessions = (ChatSession.query
                .filter_by(user_id=current_user.id)
                .order_by(ChatSession.updated_at.desc())
                .all())
    return render_template('chat.html',
                           sessions=sessions,
                           active_session=session,
                           messages=session.messages)


@app.route('/chat/new', methods=['POST'])
@login_required
def new_chat():
    session = ChatSession(title='New Chat', user_id=current_user.id)
    db.session.add(session)
    db.session.commit()
    return redirect(url_for('chat_session', session_id=session.id))


@app.route('/chat/send/<int:session_id>', methods=['POST'])
@login_required
def send_message(session_id):
    chat_sess = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    message = (data.get('message', '') if data else '').strip()
    if not message:
        return jsonify({'error': 'Empty message'}), 400

    # Save user message
    user_msg = ChatMessage(role='user', content=message, session_id=session_id)
    db.session.add(user_msg)

    # Update session title from first message
    if not chat_sess.messages:
        chat_sess.title = message[:MAX_CHAT_TITLE_LENGTH]

    # RAG context
    user_files = File.query.filter_by(user_id=current_user.id).all()
    context = get_rag_context(message, user_files)

    if context:
        prompt = (
            'You are an expert electrical engineering tutor. '
            'Use the following notes to help answer the question.\n\n'
            f'Context:\n{context}\n\nQuestion: {message}\n\nAnswer:'
        )
    else:
        prompt = (
            'You are an expert electrical engineering tutor.\n\n'
            f'Question: {message}\n\nAnswer:'
        )

    answer = query_ollama(prompt)
    if answer is None:
        if context:
            answer = (
                '⚠️ Ollama (local AI) is not running. '
                'However, here is what was found in your notes:\n\n'
                + context[:MAX_FALLBACK_CONTEXT_SIZE]
            )
        else:
            answer = (
                '⚠️ Ollama (local AI) is not running and no relevant notes were found. '
                'Please start Ollama with `ollama serve` and ensure the mistral model is pulled.'
            )

    assistant_msg = ChatMessage(role='assistant', content=answer, session_id=session_id)
    db.session.add(assistant_msg)
    chat_sess.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'response': answer, 'title': chat_sess.title})


@app.route('/chat/delete/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    db.session.delete(session)
    db.session.commit()
    flash('Chat session deleted.', 'success')
    return redirect(url_for('chat'))


# ---------------------------------------------------------------------------
# Bootstrap DB
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, port=5000)
