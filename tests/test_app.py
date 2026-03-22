"""Basic smoke tests for the edX Engineering learning system."""
import io
import pytest


@pytest.fixture
def app():
    """Create application for testing."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    from config import Config

    class TestConfig(Config):
        TESTING = True
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SECRET_KEY = 'test-secret'

    from app import create_app
    application = create_app(TestConfig)
    with application.app_context():
        yield application


@pytest.fixture
def client(app):
    return app.test_client()


def _register(client, username='testuser', email='test@example.com', password='password123'):
    return client.post('/auth/register', data={
        'username': username,
        'email': email,
        'password': password,
        'confirm': password,
    }, follow_redirects=True)


def _login(client, email='test@example.com', password='password123'):
    return client.post('/auth/login', data={
        'email': email,
        'password': password,
    }, follow_redirects=True)


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------

def test_register_page_loads(client):
    resp = client.get('/auth/register')
    assert resp.status_code == 200
    assert b'Create Account' in resp.data


def test_login_page_loads(client):
    resp = client.get('/auth/login')
    assert resp.status_code == 200
    assert b'Log In' in resp.data


def test_register_creates_user(client):
    resp = _register(client)
    assert resp.status_code == 200
    # After registration we are redirected to login
    assert b'log in' in resp.data.lower() or b'Account created' in resp.data


def test_login_with_valid_credentials(client):
    _register(client)
    resp = _login(client)
    assert resp.status_code == 200
    assert b'Dashboard' in resp.data or b'Welcome' in resp.data


def test_login_with_invalid_credentials(client):
    _register(client)
    resp = _login(client, password='wrongpass')
    assert b'Invalid email or password' in resp.data


def test_dashboard_requires_login(client):
    resp = client.get('/dashboard', follow_redirects=False)
    assert resp.status_code == 302
    assert '/auth/login' in resp.headers['Location']


# ---------------------------------------------------------------------------
# File upload tests
# ---------------------------------------------------------------------------

def test_file_list_requires_login(client):
    resp = client.get('/files/', follow_redirects=False)
    assert resp.status_code == 302


def test_file_upload_txt(client):
    _register(client)
    _login(client)
    data = {'file': (io.BytesIO(b'Ohms law: V = I * R'), 'notes.txt')}
    resp = client.post('/files/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['original_name'] == 'notes.txt'
    assert body['file_type'] == 'txt'


def test_file_upload_invalid_type(client):
    _register(client)
    _login(client)
    data = {'file': (io.BytesIO(b'bad file'), 'script.exe')}
    resp = client.post('/files/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 400


def test_file_list_returns_uploaded_files(client):
    _register(client)
    _login(client)
    # Upload a file
    data = {'file': (io.BytesIO(b'Kirchhoff voltage law'), 'kvl.txt')}
    client.post('/files/upload', data=data, content_type='multipart/form-data')
    # List files
    resp = client.get('/files/')
    assert resp.status_code == 200
    files = resp.get_json()
    assert any(f['original_name'] == 'kvl.txt' for f in files)


def test_file_preview(client):
    _register(client)
    _login(client)
    data = {'file': (io.BytesIO(b'Capacitors store charge'), 'cap.txt')}
    upload = client.post('/files/upload', data=data, content_type='multipart/form-data')
    file_id = upload.get_json()['id']
    resp = client.get(f'/files/{file_id}/preview')
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'Capacitors store charge' in body['extracted_text']


def test_file_delete(client):
    _register(client)
    _login(client)
    data = {'file': (io.BytesIO(b'Temporary note'), 'temp.txt')}
    upload = client.post('/files/upload', data=data, content_type='multipart/form-data')
    file_id = upload.get_json()['id']
    resp = client.delete(f'/files/{file_id}')
    assert resp.status_code == 200
    # Verify it's gone
    files = client.get('/files/').get_json()
    assert not any(f['id'] == file_id for f in files)


# ---------------------------------------------------------------------------
# Chat session tests
# ---------------------------------------------------------------------------

def test_chat_session_create(client):
    _register(client)
    _login(client)
    resp = client.post('/chat/sessions',
                       json={'title': 'Circuits 101'},
                       content_type='application/json')
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['title'] == 'Circuits 101'


def test_chat_session_list(client):
    _register(client)
    _login(client)
    client.post('/chat/sessions', json={'title': 'Session A'}, content_type='application/json')
    resp = client.get('/chat/sessions')
    assert resp.status_code == 200
    sessions = resp.get_json()
    assert any(s['title'] == 'Session A' for s in sessions)


def test_chat_message_stored(client):
    _register(client)
    _login(client)
    sess = client.post('/chat/sessions', json={'title': 'Q&A'},
                       content_type='application/json').get_json()
    sid = sess['id']
    # Send a message (Ollama won't be available in test but we still verify DB storage)
    resp = client.post(f'/chat/sessions/{sid}/messages',
                       json={'message': 'What is a resistor?'},
                       content_type='application/json')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['user_message']['content'] == 'What is a resistor?'
    assert body['assistant_message']['role'] == 'assistant'


def test_chat_session_delete(client):
    _register(client)
    _login(client)
    sess = client.post('/chat/sessions', json={'title': 'To Delete'},
                       content_type='application/json').get_json()
    sid = sess['id']
    resp = client.delete(f'/chat/sessions/{sid}')
    assert resp.status_code == 200
    sessions = client.get('/chat/sessions').get_json()
    assert not any(s['id'] == sid for s in sessions)
