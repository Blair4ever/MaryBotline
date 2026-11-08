# MARY: Autonomous Multi-Model Group AI Agent for LINE

[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-50%20passed-brightgreen.svg)]()

> **Intelligent, multi-provider conversational group agent with runtime model switching, deterministic tool safety, and persistent memory for the LINE Messaging platform.**

---

## 1. Project Title & Overview

**MARY** (Messaging AI Runtime) is an enterprise-grade autonomous conversational agent designed specifically for LINE messaging groups. Built on FastAPI and Python's asynchronous ecosystem, MARY bridges commercial frontier models (Google Gemini) and local or self-hosted open-weight language models (e.g., Qwen 3.5 9B GGUF) behind a unified, capability-aware routing engine. 

Rather than acting as a simple single-turn chatbot, MARY functions as an active group collaborator that listens contextually, preserves long-term structured memory, enforces strict multi-tenant isolation, and safely executes registered tools (expense splitting, reminder scheduling, task tracking, and GitHub interactions) with role-based permission checks.

* **Category:** Conversational AI, Multi-Agent Systems, Group Productivity, LLM Orchestration
* **Current Status:** v0.3.0 (Active Development, Production-Ready Core Architecture)

---

## 2. Why This Project Exists

Most messaging platform bots are locked into a single commercial LLM vendor or require full service redeployments and server restarts whenever model parameters, endpoints, or providers need to be changed. Furthermore:

- **Vendor Lock-in & Cost Spikes:** High-volume group chats quickly incur heavy API costs if every trivial conversational greeting is processed by a high-tier commercial API.
- **Privacy & Self-Hosting Demands:** Communities and engineering teams often require open-weight models (such as Qwen 3.5 fine-tunes) running on private infrastructure for conversational privacy, brainstorming, and uncensored creativity.
- **Tool Calling Heterogeneity:** Not all local or fine-tuned open-weight models reliably support function/tool calling. Routing tool-heavy operations to unsupported models causes runtime failures, corrupted responses, or infinite loops.

MARY was created to solve this architectural gap by introducing **Runtime Model Selection** and **Capability-Aware Routing**, enabling administrators to dynamically toggle between frontier APIs and local GGUF endpoints in real-time via LINE chat commands while deterministically safeguarding tool execution.

---

## 3. Problem Statement

Group communication environments present distinct architectural challenges:
1. **Unstructured Group Context:** Group chats involve overlapping conversations, multiple human participants, implicit intent, and background noise. Traditional bots trigger indiscriminately on every message or fail to maintain continuous conversational context.
2. **Inflexible Model Topologies:** Developers are forced to choose either cloud-only (Gemini/OpenAI) or local-only (Ollama/llama.cpp). Existing frameworks lack dynamic, capability-based fallback mechanisms that prevent duplicate tool execution during provider downtime.
3. **Security & State Safety:** Direct LLM execution without deterministic policy gates exposes systems to prompt injections, unauthorized state mutations, and accidental financial/reminder data corruption.

MARY provides a structured runtime that solves these problems through three levels of autonomy (L1 Observe, L2 Assist, L3 Execute), verified capability profiles, and cryptographically verified webhook ingestion.

---

## 4. Key Features

| Feature | Description | How It Works | Implementation Status |
|---|---|---|---|
| **Multi-Provider LLM Engine** | Unified interface for Google Gemini and custom OpenAI-compatible endpoints. | Uses an adapter abstraction layer (`GeminiLLMClient`, `OpenAICompatibleClient`) normalizing outputs into standardized `LLMResponse` objects. | **Implemented** |
| **Qwen 3.5 GGUF Support** | Native profile for `CapitalSTEEZ47/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF` (`...IQ3_M.gguf`). | Registered in `ModelRegistry` with exact context (32k), quantization parameters, and deployment metadata. | **Implemented** |
| **Runtime Model Selection** | Dynamic per-group model switching via chat commands without downtime or server restarts. | Authorized admins issue `/model qwen` or `/model gemini`; settings are validated against active health checks and stored in database settings. | **Implemented** |
| **Capability-Based Routing** | Strict workload routing based on verified model capabilities. | Workloads are categorized into `CONVERSATION`, `REASONING`, `TOOL_EXECUTION`, and `SUMMARIZATION`. Tool workloads are only routed to models with verified `SUPPORTED` status (Gemini). | **Implemented** |
| **Zero-Duplicate Fallback** | Automatic fallback to secondary provider on connection or authentication failure without repeating completed side-effects. | `ModelRouter` inspects execution context; if tool actions have already executed, it synthesizes responses without re-invoking the external tool. | **Implemented** |
| **Real-Time Health Diagnostics** | Differentiates between offline connection refusal and authentication rejection. | Dedicated `/model status` admin command tests HTTP endpoints directly using asynchronous probes. | **Implemented** |
| **Three-Tier Autonomy** | L1 Observe, L2 Assist, and L3 Execute autonomy architecture. | Passive background memory extraction, proactive conversational suggestions, and permission-gated tool executions. | **Implemented** |
| **Multi-Tenant Isolation** | Strict scoping by LINE `group_id`. | `GroupScopedMixin` ensures all memories, expenses, reminders, and settings are partitioned by group identifier. | **Implemented** |
| **LINE Webhook Security** | HMAC-SHA256 signature verification and idempotency check. | Verifies `X-Line-Signature` and deduplicates incoming payloads using `webhookEventId`. | **Implemented** |
| **Web-Based Management Dashboard** | Browser UI for cross-group telemetry and model configuration. | Planned management interface for auditing and administration. | **Planned** |

---

## 5. How It Works

### Architectural Data Flow

1. **Webhook Ingestion:** LINE sends an event payload to `/api/webhooks/line`. MARY validates the `X-Line-Signature` using HMAC-SHA256.
2. **Deduplication & Ingestion:** The `webhookEventId` is checked to prevent duplicate processing. The request is immediately acknowledged (HTTP 200).
3. **Dispatch & Orchestration:** The background pipeline resolves the group configuration and determines whether the bot is addressed (mention, 1-on-1, or active discussion).
4. **Model Selection & Capability Check:** `ModelRouter` identifies the active model for the specific group and workload. If the task requires tools, only models with verified tool support are scheduled.
5. **Execution & Fallback:** If the selected endpoint is unreachable, `ModelRouter` triggers an automatic fallback while preserving the session state.
6. **Dispatch Response:** The standardized response is formatted as text or interactive LINE Flex Messages and returned via the LINE Messaging API.

```mermaid
flowchart TD
    subgraph Client Layer
        User[LINE Group Member] -->|Chat Message| LINEPlatform[LINE Messaging API]
    end

    subgraph Ingestion & Edge Security
        LINEPlatform -->|POST /api/webhooks/line| WebhookRoute[FastAPI Webhook Controller]
        WebhookRoute --> SigCheck{HMAC-SHA256 Valid?}
        SigCheck -->|No| HTTP403[403 Forbidden]
        SigCheck -->|Yes| IdempotencyCheck{Seen webhookEventId?}
        IdempotencyCheck -->|Duplicate| HTTP200Ack[200 OK Fast Ack - No-op]
        IdempotencyCheck -->|New| HTTP200[200 OK Fast Ack]
    end

    subgraph Agent Orchestrator & Logic
        HTTP200 --> TaskWorker[Async Event Ingestion]
        TaskWorker --> GroupCheck[Load Group Settings & Memory]
        GroupCheck --> CommandFilter{Admin /model Command?}
        CommandFilter -->|Yes| AdminHandler[commands.py: Process /model]
        CommandFilter -->|No| Router[ModelRouter: Evaluate Workload]
    end

    subgraph Model Routing & Fallback
        Router --> WorkloadGate{Requires Tools?}
        WorkloadGate -->|Yes| Gemini[Gemini 3.5 Flash\n(Tool Supported)]
        WorkloadGate -->|No| SelectedModel{Configured Model}
        SelectedModel -->|qwen| QwenEndpoint[OpenAI-Compatible Local Endpoint\nQwen3.5-9B GGUF]
        SelectedModel -->|gemini| Gemini
        QwenEndpoint -.->|Connection / Auth Fail| Fallback[Fallback to Gemini\n(Preserve Context & No Dup Tools)]
    end

    subgraph Action Execution & Dispatch
        Gemini --> ToolGate{Tool Call Requested?}
        ToolGate -->|Yes| ToolRegistry[Tool Execution: Expense, Reminder, Task]
        ToolRegistry --> DB[(PostgreSQL / SQLite)]
        ToolGate -->|No| FormatReply[Format Text / Flex Message]
        Fallback --> FormatReply
        QwenEndpoint --> FormatReply
        ToolRegistry --> FormatReply
        AdminHandler --> FormatReply
        FormatReply --> LINEClient[LINE Messaging API Client]
        LINEClient --> User
    end
```

---

## 6. Technology Stack

| Category | Technology / Library | Purpose |
|---|---|---|
| **Core Runtime** | Python 3.12 / 3.14 | Modern async/await execution environment |
| **Web Framework** | FastAPI (0.110+) | High-performance asynchronous HTTP REST endpoints |
| **ASGI Server** | Uvicorn (Standard) | Non-blocking async event loop and server runtime |
| **Messaging Integration** | `line-bot-sdk` (v3+) | LINE Messaging API client, webhook parsing, Flex messaging |
| **Relational Database** | PostgreSQL 16+ / SQLite | Multi-tenant operational state, conversation history, and memories |
| **Async ORM** | SQLAlchemy 2.0 (Async) + `aiosqlite` / `asyncpg` | Asynchronous entity persistence and migrations |
| **Data Validation** | Pydantic v2 & Pydantic-Settings | Strict request/response schema modeling and environment parsing |
| **AI Frontier Provider** | Google GenAI SDK (`google-genai`) | Official Gemini 3.5 Flash client for tool execution & reasoning |
| **AI Open-Weight Provider** | Custom HTTP Client (`httpx`) | OpenAI-compatible adapter for local self-hosted GGUF inference engines |
| **Target Open-Weight Model** | `Qwen3.5-9B-The-Defiant-Fable-...-IQ3_M.gguf` | 32k context, IQ3_M quantized GGUF inference model |
| **Job Scheduling** | APScheduler 3.x / 4.x | Persistent background reminder processing |
| **Testing & Mocking** | Pytest, `pytest-asyncio`, `respx` / `httpx.MockTransport` | Mocked unit and integration testing without external API credit usage |

---

## 7. Architecture Overview

MARY follows a **Hexagonal / Clean Architecture** pattern ensuring decoupled business logic:

1. **Ingestion & Edge Security Layer:** Receives incoming JSON webhooks, verifies signatures, strips unauthorized payloads, and applies idempotency tracking.
2. **Agent Orchestration Layer:** Analyzes conversation triggers, constructs system prompts with multi-tier memories, and determines intent.
3. **Model Abstraction & Routing Layer (`app/services/llm/`):**
   - `registry.py`: Central model capability registry cataloging context length, vision, tool support, and pricing.
   - `router.py`: Workload-based model selector with intelligent fallback.
   - `commands.py`: Live administrative chat interface for model management.
   - `adapters/`: Provider-specific clients that handle payload normalization, error wrapping, and token usage accounting.
4. **Safety & Tool Execution Layer (`app/tools/`):** Decorator-based tool registry with JSON Schema generation and permission enforcement (Automatic, Confirm Ambiguous, Require Approval).
5. **Persistence Layer (`app/database/`):** Isolated tenant tables scoped to `group_id`.

---

## 8. Project Structure

```
MaryBotline/
├── app/
│   ├── agent/                      # Core agent logic and orchestration
│   │   ├── autonomy.py             # L1/L2/L3 autonomy logic
│   │   ├── context.py              # Context window manager
│   │   ├── orchestrator.py         # Main conversation coordinator
│   │   ├── permissions.py          # Action permission validation
│   │   ├── prompts.py              # System prompts and instructions
│   │   └── tools/                  # Internal agent tools (memory, summary)
│   ├── api/                        # HTTP endpoints and routing
│   │   ├── routes/                 # Health and webhook route handlers
│   │   │   ├── health.py           # Health check endpoints
│   │   │   └── webhook.py          # Inbound webhook receiver
│   │   ├── webhooks/line.py        # LINE signature validation & parser
│   │   └── router.py               # Combined API router
│   ├── config.py                   # Pydantic Settings and environment configuration
│   ├── core/                       # Core system utilities (logging, security, scheduler)
│   ├── database/                   # Database session and base model definitions
│   ├── main.py                     # FastAPI application bootstrap and lifespan
│   ├── models/                     # SQLAlchemy domain entities (Group, Memory, Expense, ...)
│   ├── schemas/                    # Pydantic schemas for events and group settings
│   ├── services/
│   │   ├── line/                   # LINE Messaging API wrapper and Flex message builders
│   │   └── llm/                    # Multi-provider LLM engine
│   │       ├── client.py           # Gemini SDK adapter
│   │       ├── commands.py         # Admin commands (/model, /models, /model status)
│   │       ├── exceptions.py       # Standardized LLM exception hierarchy
│   │       ├── openai_client.py    # OpenAI-compatible / local GGUF adapter
│   │       ├── registry.py         # Model capability registry
│   │       ├── router.py           # Capability-based router and fallback engine
│   │       └── types.py            # Normalized data models (LLMResponse, CapabilityProfile)
│   └── tools/                      # Registered domain tools (expenses, tasks, reminders, GitHub)
├── docs/                           # Comprehensive technical documentation
│   ├── architecture.md             # Detailed architectural specification
│   ├── technical-specification.md  # Engineering requirements and API schemas
│   ├── research-notes.md           # Model benchmarks, routing experiments, and findings
│   ├── PRD.md                      # Product Requirements Document
│   ├── DATABASE_SCHEMA.md          # Database relational schema design
│   └── SECURITY.md                 # Security policies and cryptographic details
├── tests/                          # Test suite (50+ unit and integration tests)
│   ├── test_extended_models.py     # Qwen3.5 GGUF and OpenAI adapter tests
│   ├── test_runtime_model_selection.py # Admin commands and routing tests
│   └── ...                         # Agent, memory, and permission unit tests
├── .env.example                    # Template environment variables (no secrets)
├── docker-compose.yml              # Container composition specification
├── Dockerfile                      # Application container build definition
├── pyproject.toml                  # Project packaging and dependencies
├── requirements.txt                # Flat dependency manifest
└── README.md                       # Main project documentation
```

---

## 9. Installation & Deployment

### Prerequisites
- Python 3.12 or 3.14
- Virtual environment (`venv` or `conda`)
- A registered LINE Messaging API Channel (Developer Console)
- *(Optional)* A local inference server (e.g., `llama.cpp` server, `vLLM`, or `Ollama`) serving the target GGUF model

### Local Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/Blair4ever/MaryBotline.git
cd MaryBotline

# 2. Create and activate a Python virtual environment
python -m venv .venv

# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Open .env in your editor and provide your LINE and LLM keys (see Section 10)

# 5. Launch the application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Self-Hosted Local GGUF Inference (llama.cpp)

To serve the supported Qwen 3.5 9B IQ3_M GGUF model locally:

```bash
# Example launching llama-server (llama.cpp)
./llama-server \
  -m ./models/Qwen3.5-9B-The-Defiant-Fable-Uncnr-Heretic-NEO-MAX-MTP-IQ3_M.gguf \
  -c 32768 \
  --port 8080 \
  --host 0.0.0.0
```

Configure your `.env` to point to `http://localhost:8080/v1` with `CUSTOM_LLM_ENABLED=true`.

---

## 10. Configuration & Environment Variables

All settings are managed via environment variables with `.env` file support using `pydantic-settings`.

| Environment Variable | Type | Default | Description |
|---|---|---|---|
| `APP_NAME` | string | `MARY` | Human-readable application name |
| `APP_ENV` | string | `development` | Deployment environment (`development`, `production`, `test`) |
| `DEBUG` | boolean | `true` | Enable debug logs and tracebacks |
| `PORT` | integer | `8000` | HTTP port for Uvicorn |
| `HOST` | string | `0.0.0.0` | Bind IP address |
| `TIMEZONE` | string | `Asia/Bangkok` | Default timezone for scheduling and display |
| `SECRET_KEY` | string | *Required in Prod* | Application cryptographic secret key |
| `LINE_CHANNEL_SECRET` | string | `""` | LINE Channel Secret for HMAC-SHA256 signature verification |
| `LINE_CHANNEL_ACCESS_TOKEN` | string | `""` | Long-lived LINE Messaging Channel Access Token |
| `LINE_BOT_USER_ID` | string | `None` | Bot LINE User ID (to detect direct mentions) |
| `DATABASE_URL` | string | `sqlite+aiosqlite:///./mary.db` | SQLAlchemy async connection URI (SQLite or PostgreSQL) |
| `LLM_PROVIDER` | string | `gemini` | Default primary provider (`gemini`) |
| `LLM_API_KEY` | string | `""` | Google Gemini API key |
| `LLM_MODEL` | string | `gemini-3.5-flash` | Default Gemini model identifier |
| `CUSTOM_LLM_BASE_URL` | string | `http://localhost:8080/v1` | Base URL for OpenAI-compatible local/remote endpoint |
| `CUSTOM_LLM_API_KEY` | string | `""` | Bearer token for custom endpoint (optional for local servers) |
| `CUSTOM_LLM_MODEL` | string | `Qwen3.5-9B-...-IQ3_M.gguf`| Exact model filename / identifier reported by custom endpoint |
| `CUSTOM_LLM_PROVIDER_NAME`| string | `custom-openai` | Human-readable label for custom provider |
| `CUSTOM_LLM_ENABLED` | boolean | `false` | Enable/disable custom endpoint adapter |
| `GITHUB_TOKEN` | string | `None` | GitHub Personal Access Token for repository tools |

> [!WARNING] Never commit a `.env` file containing real credentials or API keys to version control. The repository `.gitignore` strictly excludes `.env`.

---

## 11. Usage & Examples

### Administrator Model Commands

Model switching and diagnostics are performed directly within the LINE group chat by authorized group administrators.

| Command | Permission | Description |
|---|---|---|
| `/model` | Any Member | Displays the active conversation model and default tool execution model. |
| `/models` | Administrator | Lists all registered models, context window size, quantization, and tool capability. |
| `/model qwen` | Administrator | Switches the group's default conversation model to Qwen 3.5 GGUF. |
| `/model gemini`| Administrator | Switches the group's default conversation model to Google Gemini 3.5 Flash. |
| `/model status`| Administrator | Performs a live health check on all endpoints, verifying network reachability and authentication. |

#### Example Interaction

```text
Admin: /model status
MARY:  🔍 ตรวจสอบสถานะการเชื่อมต่อโมเดล:
       1. gemini-3.5-flash (Google Gemini):
          • สถานะ: ✅ ออนไลน์ (Connected & Ready)
       2. Qwen3.5-9B-The-Defiant-Fable-... (OpenAI-Compatible / Local):
          • สถานะ: ✅ ออนไลน์ (Connected & Ready)
          • Endpoint: http://localhost:8080/v1

Admin: /model qwen
MARY:  ✅ สลับโมเดลสำเร็จ!
       • โมเดลปัจจุบัน: Qwen3.5-9B-The-Defiant-Fable-Uncnr-Heretic-NEO-MAX-MTP-IQ3_M.gguf
       • เอนจิน: Qwen3.5 (Local GGUF / OpenAI-Compatible)
       • หมายเหตุ: คำสั่งที่ต้องใช้เครื่องมือ (Tool Execution) จะถูกส่งต่อให้ Gemini โดยอัตโนมัติ

User: สรุปไอเดียทำแคมเปญการตลาดสัปดาห์หน้าให้หน่อย
MARY: [ตอบกลับด้วย Qwen 3.5 โดยใช้ context ของกลุ่ม]

User: เตือนประชุมพรุ่งนี้ 10 โมงด้วยนะ
MARY: [ส่งต่อคำสั่งไปยัง Gemini เพื่อเรียกใช้ add_reminder tool อย่างปลอดภัย]
```

---

## 12. Security & Compliance

MARY implements defense-in-depth principles across its edge and database layers:

- **Cryptographic Signature Verification:** Every inbound HTTP request to `/api/webhooks/line` is checked against `X-Line-Signature` using constant-time HMAC-SHA256 comparison. Unauthorized payloads are immediately rejected with HTTP 403.
- **Idempotency Guarantee:** Incoming events include a `webhookEventId`. Handled events are recorded in an in-memory/cache store to discard retransmitted duplicate webhook frames.
- **Tenant Data Isolation:** Multi-tenancy is enforced at the database layer. All entities (`Message`, `Memory`, `Expense`, `Reminder`) include a non-nullable `group_id` foreign key. Queries explicitly include `WHERE group_id = :group_id`.
- **Privilege Separation:** Dangerous operations (clearing memories, triggering GitHub commits, switching LLM models) check user authorization against group admin records.
- **Untrusted Input Handling:** User messages are parameterized in prompts and never evaluated as raw code or SQL queries.

---

## 13. Testing & Quality Assurance

The codebase maintains a comprehensive automated testing suite written with `pytest` and `pytest-asyncio`. All tests use mocked HTTP transports (`respx` and `httpx.MockTransport`), guaranteeing zero external network calls and zero API cost.

### Test Categories
1. **Model Registry & Capabilities:** Validates capability flags, quantization metadata, and context window limits.
2. **OpenAI-Compatible Adapter:** Tests connection timeouts, bearer token authentication, payload normalization, and usage tracking.
3. **Runtime Model Selection & Admin Authorization:** Tests permissions for `/model`, persistence of selections in the database, and isolation between groups.
4. **Reliability & Fallback:** Validates that offline endpoints trigger automatic failover to Gemini without duplicate tool execution.

### Running the Test Suite

```bash
# Run all tests with short progress summary
pytest -q

# Run with verbose output and coverage report
pytest -v --durations=10
```

Current test status: **50 passed, 0 failed, 0 warnings**.

---

## 14. Development Status & Roadmap

### Milestones Completed
- [x] Webhook receiver with HMAC-SHA256 verification and fast acknowledgement.
- [x] L1/L2/L3 autonomous orchestrator and prompt assembler.
- [x] Gemini GenAI integration with native tool-calling.
- [x] Domain tool registry (Expense splitting, Task manager, Reminders with APScheduler).
- [x] Extensible Model Capability Registry (`ModelCapabilityProfile`).
- [x] OpenAI-compatible endpoint adapter supporting self-hosted GGUF servers.
- [x] Registered specific Qwen 3.5 9B IQ3_M GGUF model profile.
- [x] Runtime model switching admin commands (`/model`, `/models`, `/model status`).
- [x] Capability-based routing ensuring tool safety and fallback without duplicate side-effects.

### Future Roadmap
- [ ] Implement web-based admin control panel for cross-group telemetry.
- [ ] Add streaming response support via LINE Flex Message incremental updates.
- [ ] Expand model capability registry with Ollama and Anthropic Claude adapters.
- [ ] Introduce semantic vector search for multi-month conversation retrieval.

---

## 15. Limitations & Future Work

- **Tool Execution in Open-Weight Models:** Qwen 3.5 9B GGUF models running in quantized local formats (such as IQ3_M) do not reliably generate standard tool-calling JSON schemas in our evaluation. Tool workloads are intentionally routed exclusively to Gemini.
- **Local Endpoint Availability:** When running local inference via `llama.cpp` or `vLLM`, host machine hardware (VRAM/RAM) directly bounds inference throughput. MARY gracefully falls back to Gemini if the local server goes offline.
- **LINE Reply Token Lifespan:** LINE Messaging API reply tokens expire after 60 seconds. Long-running model inferences must use push messages if processing exceeds this limit.

---

## 16. Research & Engineering Notes

A complete engineering log detailing architectural trade-offs, capability benchmarks, and the fallback state-machine design is available in [docs/research-notes.md](docs/research-notes.md). Key findings include:
- Multi-tier quantization (IQ3_M) reduces memory footprints to ~4.5 GB VRAM while maintaining solid Thai and English conversational coherence.
- Isolating tool-calling from conversational generation allows teams to use cost-effective self-hosted models for 80%+ of chat volume while reserving paid commercial APIs for tool execution.

---

## 17. Contributing Guidelines

We welcome contributions from the community! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) guide for details on:
1. Submitting bug reports and feature proposals.
2. Development environment setup and coding conventions (Black, Flake8, Mypy).
3. Writing unit tests for new model adapters or domain tools.
4. Submitting clean, rebased Pull Requests.

---

## 18. License

This project is open-source software licensed under the terms of the [MIT License](LICENSE).

---

## 19. Authors & Acknowledgments

- **Lead Developer & Maintainer:** [Blair4ever](https://github.com/Blair4ever)
- **Contributors:** Open-source AI and LINE developer community.
- **Special Thanks:**
  - Hugging Face model creator `CapitalSTEEZ47` for providing the `Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF` quantization.
  - The FastAPI and SQLAlchemy development teams.
