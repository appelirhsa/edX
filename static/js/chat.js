(function () {
  'use strict';

  const chatContainer = document.getElementById('chat-messages');
  const sessionId = chatContainer ? chatContainer.dataset.sessionId : null;
  const sendBtn = document.getElementById('send-btn');
  const inputEl = document.getElementById('message-input');
  const loadingEl = document.getElementById('loading-indicator');

  function scrollToBottom() {
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }

  function appendMessage(role, content) {
    // Remove empty-chat hint if present
    const hint = document.getElementById('empty-chat-hint');
    if (hint) hint.remove();

    const row = document.createElement('div');
    row.className = `message-row d-flex ${role === 'user' ? 'justify-content-end' : 'justify-content-start'} mb-3`;

    if (role === 'assistant') {
      const avatar = document.createElement('div');
      avatar.className = 'avatar assistant-avatar me-2 flex-shrink-0';
      avatar.innerHTML = '<i class="fa fa-robot"></i>';
      row.appendChild(avatar);
    }

    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${role === 'user' ? 'user-bubble' : 'assistant-bubble'}`;
    bubble.textContent = content;
    row.appendChild(bubble);

    if (role === 'user') {
      const avatar = document.createElement('div');
      avatar.className = 'avatar user-avatar ms-2 flex-shrink-0';
      avatar.innerHTML = '<i class="fa fa-user"></i>';
      row.appendChild(avatar);
    }

    chatContainer.appendChild(row);
    scrollToBottom();
  }

  async function sendMessage() {
    if (!sessionId) return;

    const message = inputEl.value.trim();
    if (!message) return;

    inputEl.value = '';
    inputEl.style.height = 'auto';
    sendBtn.disabled = true;
    loadingEl.classList.remove('d-none');

    appendMessage('user', message);
    scrollToBottom();

    try {
      const resp = await fetch(`/chat/send/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      });

      if (!resp.ok) {
        throw new Error(`Server error: ${resp.status}`);
      }

      const data = await resp.json();
      appendMessage('assistant', data.response);

      // Update session title in sidebar if it changed
      if (data.title) {
        const sidebarLinks = document.querySelectorAll('.session-title');
        sidebarLinks.forEach(link => {
          if (link.dataset.sessionId === String(sessionId)) {
            const spanEl = link.querySelector('span');
            if (spanEl) spanEl.textContent = data.title;
          }
        });
      }
    } catch (err) {
      appendMessage('assistant', '⚠️ Error: ' + err.message);
    } finally {
      sendBtn.disabled = false;
      loadingEl.classList.add('d-none');
      inputEl.focus();
    }
  }

  // Expose globally for onclick attribute
  window.sendMessage = sendMessage;

  // Enter to send, Shift+Enter for newline
  if (inputEl) {
    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Auto-resize textarea
    inputEl.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 150) + 'px';
    });
  }

  // Initial scroll to bottom on load
  scrollToBottom();
})();
