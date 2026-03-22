/* =====================================================
   edX Engineering – File Manager
   ===================================================== */
class FileManager {
  constructor() {
    this.files = [];
  }

  init() {
    this.container = document.getElementById('file-list-container');
    this.dropZone = document.getElementById('drop-zone');
    this.fileInput = document.getElementById('file-input');
    this.progress = document.getElementById('upload-progress');

    this.dropZone.addEventListener('click', () => this.fileInput.click());
    this.fileInput.addEventListener('change', (e) => this.handleFiles(e.target.files));

    this.dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      this.dropZone.classList.add('drag-over');
    });
    this.dropZone.addEventListener('dragleave', () => this.dropZone.classList.remove('drag-over'));
    this.dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      this.dropZone.classList.remove('drag-over');
      this.handleFiles(e.dataTransfer.files);
    });

    this.loadFiles();
  }

  async loadFiles() {
    try {
      const resp = await fetch('/files/');
      this.files = await resp.json();
      this.render();
    } catch {
      this.container.innerHTML = '<p class="text-danger">Failed to load files.</p>';
    }
  }

  render() {
    if (!this.files.length) {
      this.container.innerHTML =
        '<p class="text-muted text-center py-4">' +
        '<i class="bi bi-folder2 me-2"></i>No files uploaded yet. Drop some notes above!</p>';
      return;
    }

    const icon = (type) => {
      if (type === 'pdf') return 'bi-file-earmark-pdf text-danger';
      if (type === 'docx') return 'bi-file-earmark-word text-primary';
      return 'bi-file-earmark-text text-secondary';
    };

    const rows = this.files.map(f => `
      <tr>
        <td><i class="bi ${icon(f.file_type)} me-2"></i>${this._esc(f.original_name)}</td>
        <td><span class="badge bg-secondary">${f.file_type.toUpperCase()}</span></td>
        <td class="text-muted small">${new Date(f.uploaded_at).toLocaleDateString()}</td>
        <td>
          <button class="btn btn-sm btn-outline-secondary me-1" onclick="fileManager.preview(${f.id}, '${this._esc(f.original_name)}')">
            <i class="bi bi-eye"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger" onclick="fileManager.deleteFile(${f.id})">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>`).join('');

    this.container.innerHTML = `
      <div class="card border-0 shadow-sm">
        <div class="card-body p-0">
          <table class="table table-hover mb-0">
            <thead class="table-light">
              <tr>
                <th>File Name</th>
                <th>Type</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  }

  async handleFiles(fileList) {
    for (const file of fileList) {
      await this.uploadFile(file);
    }
  }

  async uploadFile(file) {
    this.progress.classList.remove('d-none');
    const fd = new FormData();
    fd.append('file', file);
    try {
      const resp = await fetch('/files/upload', { method: 'POST', body: fd });
      const data = await resp.json();
      if (!resp.ok) {
        alert(data.error || 'Upload failed.');
      } else {
        this.files.unshift(data);
        this.render();
      }
    } catch {
      alert('Upload failed. Check your connection.');
    } finally {
      this.progress.classList.add('d-none');
      this.fileInput.value = '';
    }
  }

  async deleteFile(id) {
    if (!confirm('Delete this file?')) return;
    const resp = await fetch(`/files/${id}`, { method: 'DELETE' });
    if (resp.ok) {
      this.files = this.files.filter(f => f.id !== id);
      this.render();
    }
  }

  async preview(id, name) {
    const resp = await fetch(`/files/${id}/preview`);
    const data = await resp.json();
    document.getElementById('previewTitle').textContent = name;
    document.getElementById('previewText').textContent = data.extracted_text;
    new bootstrap.Modal(document.getElementById('previewModal')).show();
  }

  _esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
}

/* =====================================================
   edX Engineering – AI Chat
   ===================================================== */
class AIChat {
  constructor() {
    this.sessions = [];
    this.activeSessionId = null;
  }

  init() {
    this.sessionList = document.getElementById('session-list');
    this.chatArea = document.getElementById('chat-area');
    this.chatPlaceholder = document.getElementById('chat-placeholder');
    this.messagesEl = document.getElementById('messages');
    this.chatTitle = document.getElementById('chat-title');
    this.chatForm = document.getElementById('chat-form');
    this.chatInput = document.getElementById('chat-input');
    this.btnSend = document.getElementById('btn-send');

    document.getElementById('btn-new-chat').addEventListener('click', () => this.newSession());
    document.getElementById('btn-new-chat-main').addEventListener('click', () => this.newSession());
    document.getElementById('btn-delete-session').addEventListener('click', () => this.deleteActiveSession());
    this.chatForm.addEventListener('submit', (e) => { e.preventDefault(); this.sendMessage(); });

    this.loadSessions();
  }

  setSessions(sessions) {
    // pre-populated from server
    this.sessions = sessions;
  }

  async loadSessions() {
    try {
      const resp = await fetch('/chat/sessions');
      this.sessions = await resp.json();
    } catch { /* ignore */ }
    this.renderSessions();
  }

  renderSessions() {
    if (!this.sessions.length) {
      this.sessionList.innerHTML =
        '<p class="text-muted small px-2 mt-2">No chats yet.</p>';
      return;
    }
    this.sessionList.innerHTML = this.sessions.map(s => `
      <div class="session-item ${s.id === this.activeSessionId ? 'active' : ''}"
           data-id="${s.id}" onclick="aiChat.openSession(${s.id})">
        <i class="bi bi-chat-left me-2"></i>${this._esc(s.title)}
      </div>`).join('');
  }

  async newSession() {
    const resp = await fetch('/chat/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'New Chat' }),
    });
    const s = await resp.json();
    this.sessions.unshift(s);
    this.renderSessions();
    this.openSession(s.id);
  }

  async openSession(id) {
    this.activeSessionId = id;
    const s = this.sessions.find(x => x.id === id);
    this.chatTitle.textContent = s ? s.title : 'Chat';
    this.chatArea.classList.remove('d-none');
    this.chatPlaceholder.classList.add('d-none');
    this.messagesEl.innerHTML = '';
    this.renderSessions();

    try {
      const resp = await fetch(`/chat/sessions/${id}/messages`);
      const msgs = await resp.json();
      msgs.forEach(m => this.appendMessage(m.role, m.content, false));
      this.scrollToBottom();
    } catch { /* ignore */ }

    this.chatInput.focus();
  }

  async deleteActiveSession() {
    if (!this.activeSessionId) return;
    if (!confirm('Delete this chat session?')) return;
    await fetch(`/chat/sessions/${this.activeSessionId}`, { method: 'DELETE' });
    this.sessions = this.sessions.filter(s => s.id !== this.activeSessionId);
    this.activeSessionId = null;
    this.chatArea.classList.add('d-none');
    this.chatPlaceholder.classList.remove('d-none');
    this.renderSessions();
  }

  async sendMessage() {
    const text = this.chatInput.value.trim();
    if (!text || !this.activeSessionId) return;

    this.chatInput.value = '';
    this.btnSend.disabled = true;
    this.appendMessage('user', text);
    const typingId = this.appendTyping();

    try {
      const resp = await fetch(`/chat/sessions/${this.activeSessionId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const data = await resp.json();
      this.removeTyping(typingId);
      if (resp.ok) {
        this.appendMessage('assistant', data.assistant_message.content);
        // Update session title if it changed
        const s = this.sessions.find(x => x.id === this.activeSessionId);
        if (s && s.title === 'New Chat') {
          s.title = text.substring(0, 80);
          this.chatTitle.textContent = s.title;
          this.renderSessions();
        }
      } else {
        this.appendMessage('assistant', '⚠️ ' + (data.error || 'Error sending message.'));
      }
    } catch {
      this.removeTyping(typingId);
      this.appendMessage('assistant', '⚠️ Could not reach the server.');
    } finally {
      this.btnSend.disabled = false;
      this.chatInput.focus();
    }
  }

  appendMessage(role, content, scroll = true) {
    const wrapper = document.createElement('div');
    wrapper.className = `msg-wrapper ${role}`;
    wrapper.innerHTML = `
      <div class="msg-bubble msg-${role}">${this._esc(content)}</div>
      <div class="msg-meta">${role === 'user' ? 'You' : 'AI Tutor'}</div>`;
    this.messagesEl.appendChild(wrapper);
    if (scroll) this.scrollToBottom();
  }

  appendTyping() {
    const id = 'typing-' + Date.now();
    const wrapper = document.createElement('div');
    wrapper.className = 'msg-wrapper assistant';
    wrapper.id = id;
    wrapper.innerHTML = `
      <div class="msg-bubble msg-assistant">
        <span class="typing-indicator">
          <span></span><span></span><span></span>
        </span>
      </div>`;
    this.messagesEl.appendChild(wrapper);
    this.scrollToBottom();
    return id;
  }

  removeTyping(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  scrollToBottom() {
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  _esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;')
      .replace(/\n/g,'<br>');
  }
}
