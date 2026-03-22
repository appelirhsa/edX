import os
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
import requests

from app.extensions import db
from app.models import UploadedFile, ChatSession, ChatMessage

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


def _get_relevant_context(user_id: int, question: str, max_chars: int = 3000) -> str:
    """Return text from the user's files that may be relevant to the question."""
    files = UploadedFile.query.filter_by(user_id=user_id).all()
    if not files:
        return ''

    question_lower = question.lower()
    scored = []
    for f in files:
        if not f.extracted_text:
            continue
        text_lower = f.extracted_text.lower()
        # Simple keyword scoring
        score = sum(text_lower.count(word) for word in question_lower.split() if len(word) > 3)
        scored.append((score, f.extracted_text))

    scored.sort(key=lambda x: x[0], reverse=True)

    context_parts = []
    total = 0
    for score, text in scored:
        if total >= max_chars:
            break
        chunk = text[:max_chars - total]
        context_parts.append(chunk)
        total += len(chunk)

    return '\n\n---\n\n'.join(context_parts)


def _query_ollama(model: str, messages: list, base_url: str) -> str:
    """Send a chat request to Ollama and return the assistant reply."""
    try:
        response = requests.post(
            f'{base_url}/api/chat',
            json={'model': model, 'messages': messages, 'stream': False},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return data.get('message', {}).get('content', 'No response from model.')
    except requests.exceptions.ConnectionError:
        return (
            '⚠️ Could not connect to the Ollama service. '
            'Please make sure Ollama is running (`ollama serve`) and the model is pulled '
            f'(`ollama pull {model}`).'
        )
    except requests.exceptions.Timeout:
        return '⚠️ The AI model took too long to respond. Please try again.'
    except Exception as exc:  # noqa: BLE001
        return f'⚠️ AI error: {exc}'


@chat_bp.route('/sessions', methods=['GET'])
@login_required
def list_sessions():
    sessions = (
        ChatSession.query.filter_by(user_id=current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return jsonify([
        {'id': s.id, 'title': s.title, 'created_at': s.created_at.isoformat()}
        for s in sessions
    ])


@chat_bp.route('/sessions', methods=['POST'])
@login_required
def create_session():
    title = request.json.get('title', 'New Chat') if request.is_json else 'New Chat'
    session = ChatSession(title=title, user_id=current_user.id)
    db.session.add(session)
    db.session.commit()
    return jsonify({'id': session.id, 'title': session.title}), 201


@chat_bp.route('/sessions/<int:session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id):
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    db.session.delete(session)
    db.session.commit()
    return jsonify({'message': 'Session deleted'}), 200


@chat_bp.route('/sessions/<int:session_id>/messages', methods=['GET'])
@login_required
def get_messages(session_id):
    session = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    return jsonify([
        {'id': m.id, 'role': m.role, 'content': m.content,
         'created_at': m.created_at.isoformat()}
        for m in session.messages
    ])


@chat_bp.route('/sessions/<int:session_id>/messages', methods=['POST'])
@login_required
def send_message(session_id):
    chat_session = ChatSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first_or_404()

    data = request.get_json(silent=True) or {}
    user_text = (data.get('message') or '').strip()
    if not user_text:
        return jsonify({'error': 'Message cannot be empty.'}), 400

    # Save user message
    user_msg = ChatMessage(role='user', content=user_text, session_id=chat_session.id)
    db.session.add(user_msg)

    # Update session title from first message
    if not chat_session.messages:
        chat_session.title = user_text[:80]

    db.session.commit()

    # Build context from notes
    context = _get_relevant_context(current_user.id, user_text)

    system_prompt = (
        'You are an expert electrical and electronic engineering tutor. '
        'Help the student understand concepts clearly and thoroughly. '
        'Use examples, analogies, and step-by-step explanations where appropriate. '
        'If relevant notes are provided, refer to them in your answers.'
    )
    if context:
        system_prompt += f'\n\nRelevant notes from the student\'s uploaded files:\n\n{context}'

    # Build message history for Ollama
    history = [{'role': 'system', 'content': system_prompt}]
    for m in chat_session.messages[:-1]:  # exclude the message we just added
        history.append({'role': m.role, 'content': m.content})
    history.append({'role': 'user', 'content': user_text})

    model = current_app.config['OLLAMA_MODEL']
    base_url = current_app.config['OLLAMA_BASE_URL']
    reply = _query_ollama(model, history, base_url)

    # Save assistant message
    assistant_msg = ChatMessage(role='assistant', content=reply, session_id=chat_session.id)
    db.session.add(assistant_msg)
    db.session.commit()

    return jsonify({
        'user_message': {'id': user_msg.id, 'role': 'user', 'content': user_text},
        'assistant_message': {'id': assistant_msg.id, 'role': 'assistant', 'content': reply},
    })
