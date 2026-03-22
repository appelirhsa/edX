import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.UTC))

    files = db.relationship('UploadedFile', backref='owner', lazy=True, cascade='all, delete-orphan')
    chat_sessions = db.relationship('ChatSession', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class UploadedFile(db.Model):
    __tablename__ = 'uploaded_files'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    original_name = db.Column(db.String(256), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    extracted_text = db.Column(db.Text, default='')
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f'<File {self.original_name}>'


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='New Chat')
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    messages = db.relationship('ChatMessage', backref='session', lazy=True,
                                cascade='all, delete-orphan', order_by='ChatMessage.created_at')

    def __repr__(self):
        return f'<ChatSession {self.title}>'


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)

    def __repr__(self):
        return f'<ChatMessage {self.role}: {self.content[:30]}>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
