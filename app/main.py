from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from app.models import UploadedFile, ChatSession

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    file_count = UploadedFile.query.filter_by(user_id=current_user.id).count()
    session_count = ChatSession.query.filter_by(user_id=current_user.id).count()
    recent_files = (
        UploadedFile.query.filter_by(user_id=current_user.id)
        .order_by(UploadedFile.uploaded_at.desc())
        .limit(5)
        .all()
    )
    recent_sessions = (
        ChatSession.query.filter_by(user_id=current_user.id)
        .order_by(ChatSession.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        'main/dashboard.html',
        file_count=file_count,
        session_count=session_count,
        recent_files=recent_files,
        recent_sessions=recent_sessions,
    )


@main_bp.route('/files')
@login_required
def files():
    return render_template('main/files.html')


@main_bp.route('/learn')
@login_required
def learn():
    sessions = (
        ChatSession.query.filter_by(user_id=current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return render_template('main/learn.html', sessions=sessions)
