# Technical Specification: MARY Botline

**Document Version:** 1.0.0  
**Target Release:** v0.3.0  
**Status:** Approved & Implemented  

---

## 1. Overview & System Scope

MARY is an autonomous, multi-tenant conversational group agent operating on the LINE Messaging Platform. The system coordinates group interactions, maintains long-term contextual memory, provides automated expense splitting and reminder scheduling, and bridges commercial cloud LLM APIs with local open-weight inference engines through an intelligent, capability-aware routing architecture.

---

## 2. Functional Requirements

### FR-1: LINE Webhook Ingestion & Edge Security
- **FR-1.1:** The system shall expose a secure HTTP POST endpoint at `/api/webhooks/line`.
- **FR-1.2:** Every inbound request must be cryptographically validated against the `X-Line-Signature` header using HMAC-SHA256 and the application's `LINE_CHANNEL_SECRET`.
- **FR-1.3:** Requests with missing, malformed, or invalid signatures shall be rejected immediately with HTTP 403 Forbidden.
- **FR-1.4:** The ingestion pipeline shall verify the uniqueness of incoming `webhookEventId` values. Duplicate events shall return HTTP 200 without re-triggering business logic.
- **FR-1.5:** Webhook requests shall return an HTTP 200 acknowledgment within 500 milliseconds, deferring heavy computation to asynchronous background tasks.

### FR-2: Multi-Provider LLM Integration & Normalized Interface
- **FR-2.1:** The system shall support Google Gemini as a primary commercial provider using the official Google GenAI SDK.
- **FR-2.2:** The system shall support custom, self-hosted, or remote inference engines implementing the OpenAI-compatible `/chat/completions` API schema.
- **FR-2.3:** The custom adapter must support configurable `CUSTOM_LLM_BASE_URL`, optional Bearer token authentication (`CUSTOM_LLM_API_KEY`), and custom model names (`CUSTOM_LLM_MODEL`).
- **FR-2.4:** All model outputs must be normalized into an internal `LLMResponse` structure containing `text`, `tool_calls`, `raw_response`, and `usage` metadata.
- **FR-2.5:** Usage metadata must record reported token counts. When an endpoint does not report token statistics, the field must remain `None` rather than fabricating token counts.

### FR-3: Model Capability Registry
- **FR-3.1:** The system shall maintain an explicit `ModelCapabilityProfile` for each registered model.
- **FR-3.2:** Model profiles must specify:
  - Provider identifier (`gemini`, `custom-openai`, etc.)
  - Canonical Model ID and family
  - Context window size and maximum output tokens
  - Capability flags (`SUPPORTED`, `UNSUPPORTED`, `UNKNOWN`) for:
    - Tool / Function Calling
    - Streaming
    - Vision
    - Reasoning
  - Quantization parameters and source repository URLs where applicable
- **FR-3.3:** Unverified capabilities must default to `UNKNOWN` and cannot be treated as supported.

### FR-4: Workload-Based Routing & Fallback Engine
- **FR-4.1:** Workloads shall be categorized into:
  - `CONVERSATION`: Casual chat, brainstorming, general inquiry.
  - `REASONING`: Complex multi-step deduction.
  - `TOOL_EXECUTION`: Invocations of system tools (expenses, reminders, GitHub).
  - `SUMMARIZATION`: Group chat history compression.
  - `BACKGROUND`: Passive memory and entity extraction.
- **FR-4.2:** Workloads requiring tool execution shall only be dispatched to models where `tool_calling == CapabilityStatus.SUPPORTED`.
- **FR-4.3:** If a request routed to a custom or local endpoint fails with connection refusal (`EndpointConnectionError`), timeout, or authentication failure (`AuthenticationError`), the router shall automatically fail over to the secondary provider (Gemini).
- **FR-4.4:** Fallback execution must retain user conversation context and must never repeat a tool operation that was already committed prior to the failure.

### FR-5: Runtime Model Selection & Admin Chat Commands
- **FR-5.1:** Group administrators must be able to view and change active models via LINE chat commands:
  - `/model`: Displays the currently active conversation model.
  - `/models`: Formats and lists all registered models with context length and tool capabilities.
  - `/model qwen`: Sets Qwen 3.5 GGUF as the active conversation model for the current group.
  - `/model gemini`: Sets Gemini 3.5 Flash as the active conversation model for the current group.
  - `/model status`: Performs a real-time connectivity and authorization check across all endpoints.
- **FR-5.2:** Unauthorized users executing model modification commands must be rebuffed with an access denied notification.
- **FR-5.3:** Model configuration changes must persist to the database in `Group.settings_json` and be restored upon system restart.

### FR-6: Group Memory & Context Engine
- **FR-6.1:** The system shall maintain short-term conversational context by retrieving the last 15-30 chronological messages within the active `group_id`.
- **FR-6.2:** The system shall store structured long-term memories classified into `factual`, `event_decision`, `user_preference`, and `project`.
- **FR-6.3:** Memories must include creation metadata, source message identifiers, and optional expiration timestamps (`expires_at`).

### FR-7: Domain Tools & Permission Gates
- **FR-7.1:** Tools must be registered with typed Pydantic parameter schemas and auto-generated JSON function specifications.
- **FR-7.2:** Expense splitting tools must calculate balances, record repayments, and enforce multi-tenant isolation by `group_id`.
- **FR-7.3:** Reminder tools must integrate with an asynchronous scheduler (APScheduler) and support cron and fixed-time alerts.

---

## 3. Non-Functional Requirements

### NFR-1: Performance & Latency
- Inbound webhook acknowledgment: **< 500ms**.
- Normal conversational response latency (Gemini API): **< 2.5s** under standard network conditions.
- Local model inference response: Bound by host VRAM/compute; must enforce a 60-second client timeout to stay within LINE reply token validity windows.

### NFR-2: Security & Privacy
- Zero credential exposure: `/model status` and `/models` must never output API keys, base URLs with embedded tokens, or sensitive credentials.
- Strict multi-tenancy: No database query or memory retrieval may occur without an explicit `WHERE group_id = :group_id` filter.
- Cryptographic verification of all external payloads.

### NFR-3: Fault Tolerance & Availability
- Offline local inference servers must not cause user-facing request crashes. The router must fall back transparently and log the diagnostic incident.
- Database connection failure retry logic with connection pooling (`asyncpg` / `aiosqlite`).

### NFR-4: Testability
- 100% of integration and routing tests must execute against mocked endpoints without consuming external API credits or requiring active internet access.

---

## 4. API & Interface Specifications

### 4.1 Internal LLM Response Contract (`app/services/llm/types.py`)

```python
class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class LLMResponse(BaseModel):
    text: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    raw_response: Any = None
    model_id: str
    provider: str
    usage: Optional[TokenUsage] = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)
```

### 4.2 Webhook Endpoint Specification
- **Path:** `/api/webhooks/line`
- **Method:** `POST`
- **Headers:**
  - `Content-Type: application/json`
  - `X-Line-Signature: <base64-encoded-hmac-sha256>`
- **Response Status Codes:**
  - `200 OK`: Payload verified and queued for processing.
  - `400 Bad Request`: Payload body missing or non-JSON.
  - `403 Forbidden`: Signature verification failed.

### 4.3 Health Check Endpoint Specification
- **Path:** `/api/health`
- **Method:** `GET`
- **Response:**
```json
{
  "status": "healthy",
  "app": "MARY",
  "version": "0.3.0",
  "timezone": "Asia/Bangkok",
  "line_configured": true,
  "custom_llm_enabled": true
}
```

---

## 5. Relational Database Schema Design

All tables inherit from `GroupScopedMixin` or enforce strict referential scoping:

```sql
-- Groups Table
CREATE TABLE groups (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    settings_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Messages Table
CREATE TABLE messages (
    id VARCHAR PRIMARY KEY,
    group_id VARCHAR NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    user_id VARCHAR NOT NULL,
    user_name VARCHAR NULL,
    message_type VARCHAR NOT NULL DEFAULT 'text',
    text TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_messages_group_time ON messages (group_id, created_at DESC);

-- Memories Table
CREATE TABLE memories (
    id VARCHAR PRIMARY KEY,
    group_id VARCHAR NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    category VARCHAR NOT NULL,
    content TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ NULL,
    source_message_id VARCHAR NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Expenses Table
CREATE TABLE expenses (
    id VARCHAR PRIMARY KEY,
    group_id VARCHAR NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    payer_id VARCHAR NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    description TEXT NOT NULL,
    split_details_json JSONB NOT NULL,
    is_settled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Reminders Table
CREATE TABLE reminders (
    id VARCHAR PRIMARY KEY,
    group_id VARCHAR NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    creator_id VARCHAR NOT NULL,
    target_time TIMESTAMPTZ NOT NULL,
    message TEXT NOT NULL,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. Model Capability Matrix

| Model Identifier | Provider | Tool Calling | Vision | Reasoning | Max Context | Deployment Mode |
|---|---|---|---|---|---|---|
| `gemini-3.5-flash` | Google Gemini | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | 1,048,576 | Cloud SaaS API |
| `gemini-2.5-flash` | Google Gemini | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | 1,048,576 | Cloud SaaS API |
| `Qwen3.5-9B-The-Defiant-Fable-...-IQ3_M.gguf` | Custom OpenAI | **UNSUPPORTED** | **UNKNOWN** | **SUPPORTED** | 32,768 | Local / Self-Hosted GGUF |

