# edX Engineering Learning System

An AI-powered learning platform for **Electrical & Electronic Engineering** students.  
Upload your lecture notes and study materials, then chat with an AI tutor that references your own notes to give personalised answers.

---

## Features

| Feature | Description |
|---|---|
| 🔐 User Accounts | Secure registration & login (hashed passwords) |
| 📁 Note Storage | Upload PDF, TXT, and DOCX study files |
| 🤖 AI Tutor | Chat powered by [Ollama](https://ollama.com/) (open-source LLM) |
| 📚 RAG | Answers grounded in *your* uploaded notes |
| 💬 Chat History | Persistent sessions with full message history |
| 📱 Responsive UI | Bootstrap 5 – works on desktop & mobile |

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone https://github.com/appelirhsa/edX.git
cd edX
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Install & start Ollama (open-source AI)

```bash
# Install Ollama from https://ollama.com/
ollama pull llama3.2      # or any other model
ollama serve              # starts the local AI server
```

### 3. Run the application

```bash
python run.py
```

Then open **http://localhost:5000** in your browser.

### 4. Optional configuration via environment variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Flask secret (change in production!) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Model name to use |

---

## Running tests

```bash
python -m pytest tests/ -v
```

---

## Project Structure

```
edX/
├── app/
│   ├── __init__.py        # App factory
│   ├── auth.py            # Registration & login
│   ├── chat.py            # AI chat API (Ollama + RAG)
│   ├── files.py           # File upload & text extraction
│   ├── main.py            # Dashboard & page routes
│   ├── models.py          # SQLAlchemy models
│   ├── extensions.py      # Flask extensions
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js      # File manager & chat UI
│   └── templates/
│       ├── base.html
│       ├── auth/          # Login & register pages
│       └── main/          # Dashboard, files, learn pages
├── tests/
│   └── test_app.py        # Pytest test suite (16 tests)
├── config.py
├── run.py
└── requirements.txt
```
