# AURA System Architecture & Design

## 1. Architectural Principles
AURA is designed following six foundational principles:
1. **Hexagonal / Clean Architecture:** Clear boundaries between external interfaces (LINE Webhook, HTTP API), core business logic (agent orchestrator, permission engine), and infrastructure (PostgreSQL, LLM client, APScheduler).
2. **Deterministic Agent Safety:** The LLM is a reasoning and parsing engine, never an unconstrained execution environment. Every state change is mediated by validated Pydantic models, typed tool functions, and deterministic permission checks.
3. **Strict Multi-Tenant Scoping:** All operations, memory lookups, and data writes are strictly scoped to `group_id`.
4. **Asynchronous Non-Blocking I/O:** Built on Python's `asyncio`, FastAPI, and SQLAlchemy Async (`asyncpg`).
5. **Configurable Model Agnosticism:** LLM providers (Gemini, OpenAI, Anthropic, LiteLLM) are behind an abstract interface.
6. **Comprehensive Auditability:** All agent actions, tool invocations, and approvals are persistently logged.

---

## 2. High-Level System Architecture

```mermaid
flowchart TD
    subgraph External Clients
        LINEUser[LINE Group Members] -->|Chat Messages & Events| LINEOA[LINE Messaging API Platform]
    end

    subgraph Ingestion & Edge Security
        LINEOA -->|POST /api/webhooks/line| WebhookController[FastAPI Webhook Controller]
        WebhookController --> SigValidator[HMAC-SHA256 Signature Validator]
        SigValidator -->|Invalid| Reject403[HTTP 403 Forbidden]
        SigValidator -->|Valid| IdempotencyStore{Deduplication Check\nwebhookEventId}
        IdempotencyStore -->|Duplicate| AckDup[HTTP 200 OK - No-op]
        IdempotencyStore -->|New Event| Ack200[HTTP 200 OK Fast Ack]
    end

    subgraph Async Worker Pipeline
        Ack200 -.->|Background Task| Dispatcher[Event Ingestion Worker]
        Dispatcher --> MessageStore[(Store Incoming Message)]
        Dispatcher --> MemberSync[Auto-Sync Group & Member Profile]
        Dispatcher --> Orchestrator[Agent Orchestrator]
    end

    subgraph Intelligence & Agent Core
        Orchestrator --> TriggerGate{Should Respond?\n(Mention / Keyword / 1-on-1)}
        TriggerGate -->|No| L1Observe[L1: Passive Context & Memory Extraction]
        TriggerGate -->|Yes| ContextMgr[Context & Memory Retrieval]
        
        ContextMgr --> MemoryEngine[Memory Engine\n(Factual, Decisions, Preferences)]
        ContextMgr --> HistoryEngine[Message History Window]
        
        MemoryEngine --> PromptBuilder[Prompt & Tool Spec Assembler]
        HistoryEngine --> PromptBuilder
        
        PromptBuilder --> LLMClient[LLM Client Interface\n(Gemini 2.5 Flash / OpenAI / Claude)]
        LLMClient --> ReasoningLoop{Agent Response Evaluation}
    end

    subgraph Safety & Tool Execution
        ReasoningLoop -->|Direct Message| MsgFormatter[LINE Message Builder]
        ReasoningLoop -->|Tool Call Request| PermEngine[Permission & Policy Engine]
        
        PermEngine -->|Requires Approval| ApprovalQueue[Pending Approvals Ledger]
        PermEngine -->|Authorized| ToolRegistry[Typed Tool Registry]
        
        ToolRegistry --> ToolExpense[Expense & Split Manager]
        ToolRegistry --> ToolReminder[Scheduler & Reminders]
        ToolRegistry --> ToolTask[Task Tracker]
        ToolRegistry --> ToolMemory[Memory Store/Correct/Delete]
        ToolRegistry --> ToolTravel[Travel & Itinerary Planner]
        ToolRegistry --> ToolGitHub[GitHub Integration Agent]
        
        ToolExpense --> DB[(PostgreSQL Database)]
        ToolReminder --> DB
        ToolTask --> DB
        ToolMemory --> DB
        ToolReminder --> APSchedulerWorker[APScheduler Engine]
    end

    subgraph Verification & Outgoing Dispatch
        ToolRegistry --> ResultVerifier{Verify Tool Execution}
        ResultVerifier --> LLMFeedback[LLM Result Synthesizer]
        LLMFeedback --> MsgFormatter
        MsgFormatter --> LINEClient[LINE Messaging API Client]
        LINEClient -->|Reply / Push Message| LINEOA
    end
```

---

## 3. Subsystem Breakdown

### 3.1 Backend Architecture
- **Framework:** FastAPI with Uvicorn ASGI server.
- **Lifespan Manager:** Handles asynchronous database connection pooling (`asyncpg`), table creation/migrations, and background scheduler startup/shutdown.
- **API Routing:**
  - `/api/webhooks/line`: High-throughput webhook ingestion endpoint.
  - `/api/health`: Service readiness, liveness, and configuration diagnostics.
  - `/api/admin`: Administrative queries and audit inspections.

### 3.2 Agent Orchestration Architecture
The `AgentOrchestrator` implements a three-tier autonomy model:
- **L1 (Observe):** Silently monitors conversation streams, extracts entities, and invokes memory tools without cluttering group chat.
- **L2 (Assist):** When discussions are detected (travel ideas, expense mentions, schedule coordination), provides suggestions, draft calculations, and clarifying prompts.
- **L3 (Execute):** Executes authorized tools with schema-validated parameters.

### 3.3 Memory Architecture
Group memory is managed hierarchically:
1. **Short-Term Context Window:** The last 15-30 chronological messages in the specific group.
2. **Persistent Structured Memory:** Stored in the `memories` table with categories:
   - `factual`: Immutable or long-lasting facts (e.g., "Team wifi password", "Office address").
   - `event_decision`: Group consensus reached in past chats (e.g., "Offsite confirmed for Dec 15th").
   - `user_preference`: Individual member dietary restrictions, preferred tools, or working hours.
   - `project`: Repository links, project goals, tech stack.
3. **Memory Correction & Expiration:** Memories include `expires_at`, `source_message_id`, and `is_active` flags to support full auditing, revision, and privacy-compliant deletion.

### 3.4 Tool Execution & Permission Architecture
- **Tool Registry:** Tools are declared using Python decorators with explicit Pydantic schemas and auto-generated JSON function schemas.
- **Permission Matrix:** Every tool is assigned a strict security policy:
  - `AUTOMATIC`: Read-only queries, memory lookups, draft calculations, conversational summaries.
  - `CONFIRM_AMBIGUOUS`: Shared expense recording when participant lists are incomplete or assumptions are required.
  - `REQUIRE_APPROVAL`: Financial commitments, external bookings, GitHub public repo publishing.
  - `EXPLICIT_CONFIRMATION`: Destructive operations (repository deletion, irreversible state drops).

### 3.5 Database Architecture
- **Engine:** PostgreSQL 16+ via SQLAlchemy 2.0 Async (`asyncpg`).
- **Isolation:** Multi-tenant scoping enforced via `GroupScopedMixin` on all domain entities.
- **Timezone Standard:** Timestamps stored in `TIMESTAMPTZ` (UTC internally), converted to `Asia/Bangkok` (UTC+7) at presentation boundaries.

### 3.6 LINE Integration Architecture
- Uses asynchronous HTTP clients (`httpx`) and `line-bot-sdk` to interact with LINE endpoints.
- Supports both immediate token-based replies (`replyToken` valid for 1 minute) and proactive push messages (`push_text` / Flex Messages) for scheduled reminders.

