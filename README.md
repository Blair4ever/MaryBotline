# AURA: Autonomous Group AI Agent

> **Autonomous Group AI Agent for LINE Messaging API**  
> Empowering LINE groups with shared context, conversational intelligence, proactive coordination, expense splitting, scheduled reminders, and developer utilities.

---

## 🌟 Overview

AURA is not a simple question-and-answer chatbot. It acts as an autonomous collaborative group member operating with three levels of autonomy:
- **L1 (Observe):** Monitors incoming conversations, extracts context, and stores long-term factual group memory.
- **L2 (Assist):** Proactively drafts suggestions, expense splits, travel itineraries, and asks clarifying questions.
- **L3 (Execute):** Safely invokes registered tools and actions (e.g. reminders, repayments, GitHub management), enforcing multi-tenant isolation and strict permission gates.

---

## 🏗️ Architecture

```
LINE Members -> LINE Official Account -> LINE Webhook -> FastAPI Backend
                                                                │
                                                                ▼
                                                        Agent Orchestrator
                                                   ┌────────────┴────────────┐
                                                   ▼                         ▼
                                           LLM Reasoning Engine        Tool Registry
                                           (Gemini / LiteLLM)          (Expense, Task, Reminder)
                                                   │                         │
                                                   └────────────┬────────────┘
                                                                ▼
                                                        PostgreSQL / SQLite
```

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.12+ (or 3.14)
- PostgreSQL (or SQLite for local development)
- A LINE Messaging API Channel

### 2. Environment Setup
```bash
# Clone and enter directory
cd MaryBotline

# Create virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your LINE Messaging API and LLM credentials:
- `LINE_CHANNEL_SECRET`: Secret key from LINE Developers Console
- `LINE_CHANNEL_ACCESS_TOKEN`: Long-lived channel access token
- `LLM_API_KEY`: API key (Google Gemini, OpenAI, etc.)
- `DATABASE_URL`: PostgreSQL connection string (defaults to SQLite fallback `sqlite+aiosqlite:///./aura.db`)

### 4. Run Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
Visit `http://localhost:8000/health` to verify that the service is running.

---

## 🧪 Testing

Run automated tests:
```bash
pytest -v
```

---

## 🛡️ Security & Privacy
- **Webhook Verification:** Cryptographic HMAC-SHA256 signature verification (`X-Line-Signature`) on every incoming request.
- **Idempotency:** Webhook event deduplication via unique `webhookEventId`.
- **Tenant Isolation:** Multi-tenant scoping on all database entities via `group_id`.
- **Untrusted Input Policy:** All user input and messages are treated as data, preventing prompt injection attacks.

