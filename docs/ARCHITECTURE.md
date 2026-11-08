# System Architecture & Technical Design

## 1. Architectural Philosophy & Principles

MARY (Messaging AI Runtime) is structured according to six foundational engineering principles:

1. **Hexagonal (Ports and Adapters) Architecture:** Strict boundaries isolate external transport interfaces (LINE Webhook, HTTP REST API) from core cognitive orchestration and persistent infrastructure (PostgreSQL/SQLite, LLM providers, job schedulers).
2. **Deterministic Agent Safety:** Large Language Models are treated as non-deterministic parsing and reasoning components, never unchecked execution environments. All external side effects (database modifications, financial calculations, reminder scheduling) are mediated by typed Pydantic schemas and deterministic permission policies.
3. **Multi-Tenant Tenant Isolation:** Every operation, entity model, context window, and persistent memory is strictly scoped by the unique LINE `group_id`.
4. **Asynchronous Non-Blocking Pipeline:** Native Python `asyncio` handles inbound webhook requests, background orchestrator dispatching, and external model inference.
5. **Dynamic Model Agnosticism & Runtime Selection:** LLM providers are decoupled from workload execution. Administrators can swap the active model runtime on a per-group basis without redeploying the application.
6. **Zero-Duplicate Fallback Safety:** In the event of primary provider outage or failure, fallback routines preserve conversation context and prevent re-executing previously completed tool side effects.

---

## 2. End-to-End System Architecture

```mermaid
flowchart TD
    subgraph Ingestion & Edge Security
        LINEClient[LINE Platform] -->|POST Webhook| IngestRoute[FastAPI /api/webhooks/line]
        IngestRoute --> SignatureAuth{HMAC-SHA256\nX-Line-Signature}
        SignatureAuth -->|Invalid| Rejection[403 Forbidden]
        SignatureAuth -->|Valid| Deduplicator{webhookEventId\nSeen Check}
        Deduplicator -->|Duplicate| FastAck200[200 OK - No-op]
        Deduplicator -->|New Event| FastAckAccepted[200 OK Accepted]
    end

    subgraph Async Processing Pipeline
        FastAckAccepted -.->|Background Task| EventWorker[Async Event Ingestion Worker]
        EventWorker --> SyncContext[Auto-Sync Group & Member Profiles]
        EventWorker --> Orchestrator[Agent Orchestrator]
    end

    subgraph Cognitive Layer & Model Routing
        Orchestrator --> TriggerDecision{Should Respond?\nMention / Active Chat / Direct}
        TriggerDecision -->|No| L1Listen[L1: Passive Context Extraction & Long-Term Memory]
        TriggerDecision -->|Yes| PromptBuilder[Prompt & Context Assembler]
        
        PromptBuilder --> LoadMemory[(Group Scoped Memory)]
        PromptBuilder --> LoadHistory[(Recent 15-30 Message History)]
        
        PromptBuilder --> ModelRouter[ModelRouter]
        ModelRouter --> Registry[Model Capability Registry]
        
        ModelRouter --> WorkloadClassification{Workload Type}
        WorkloadClassification -->|Tool Execution| EnforceToolModel[Select Gemini\n(Tool Verified)]
        WorkloadClassification -->|Conversation / Brainstorm| SelectGroupModel[Select Active Model\n(Qwen3.5 or Gemini)]
        
        SelectGroupModel --> PrimaryCall{Call Endpoint}
        PrimaryCall -->|Success| ModelResponse[Standardized LLMResponse]
        PrimaryCall -->|Offline / Auth Error| FallbackHandler[ModelRouter Fallback Routine]
        FallbackHandler --> GeminiClient[Gemini Client Adapter]
        GeminiClient --> ModelResponse
        EnforceToolModel --> GeminiClient
    end

    subgraph Safety, Policy & Tool Execution
        ModelResponse --> ToolDetector{Tool Call Requested?}
        ToolDetector -->|No| MessageSynthesizer[Format Reply Text / Flex UI]
        ToolDetector -->|Yes| PermissionPolicy{Permission Engine\nCheck Policy Level}
        
        PermissionPolicy -->|Automatic| ToolRunner[Typed Tool Registry]
        PermissionPolicy -->|Require Approval| AdminApprovalQueue[Pending Approval Queue]
        
        ToolRunner --> ExpenseTool[Expense & Split Manager]
        ToolRunner --> ReminderTool[APScheduler Reminder Manager]
        ToolRunner --> TaskTool[Task Tracking Manager]
        ToolRunner --> GitHubTool[GitHub Integration Tool]
        
        ExpenseTool --> AppDB[(PostgreSQL / SQLite)]
        ReminderTool --> AppDB
        TaskTool --> AppDB
        
        ToolRunner --> ToolResultFeedback[Feed Tool Output Back to LLM]
        ToolResultFeedback --> MessageSynthesizer
    end

    subgraph Outbound Dispatch
        MessageSynthesizer --> LINEOutbound[LINE Messaging API Client]
        LINEOutbound --> LINEPlatform[LINE Group Chat]
    end
```

---

## 3. Subsystem Breakdown

### 3.1 Ingestion & Edge Security
- **HMAC Signature Verification:** Verifies the cryptographic digest provided in the `X-Line-Signature` header against the application secret `LINE_CHANNEL_SECRET`.
- **Event Idempotency:** Extracts `webhookEventId` to identify and silently discard re-delivered events from LINE edge retries.
- **Fast Acknowledgment:** Ingestion responds with HTTP 200 within milliseconds to meet LINE's strict response timeout requirements, deferring heavy computation to background tasks.

### 3.2 Agent Orchestrator & Autonomy Tiers
The orchestrator drives agent behavior through three explicit operational tiers:
- **L1 (Observe):** Silently monitors conversation streams, identifies factual entities, user preferences, and decisions, and stores them in group memory without interrupting chat.
- **L2 (Assist):** Triggers when ambiguous planning, expense discussions, or scheduling requests are detected, offering structured suggestions and calculations.
- **L3 (Execute):** Executes system mutations (recording debt, setting reminders, creating tasks) with schema validation and role-based confirmation gates.

### 3.3 LLM Multi-Provider Architecture & Capability Registry

```
                    ┌─────────────────────────┐
                    │    ModelCapability      │
                    │         Profile         │
                    └────────────┬────────────┘
                                 │
           ┌─────────────────────┴─────────────────────┐
           ▼                                           ▼
┌──────────────────────┐                    ┌──────────────────────┐
│    Gemini Adapter    │                    │  OpenAI-Compatible   │
│  (Google GenAI SDK)  │                    │     GGUF Adapter     │
├──────────────────────┤                    ├──────────────────────┤
│ - Model: gemini-3.5  │                    │ - Model: Qwen 3.5 9B │
│ - Tools: SUPPORTED   │                    │ - Tools: UNSUPPORTED │
│ - Vision: SUPPORTED  │                    │ - Quant: IQ3_M       │
│ - Reasoning: SUPP.   │                    │ - Context: 32,768    │
└──────────────────────┘                    └──────────────────────┘
```

The system separates provider configuration from model configuration:
1. **Model Capability Profiles (`app/services/llm/types.py`):**
   Models declare explicit capability status flags: `SUPPORTED`, `UNSUPPORTED`, or `UNKNOWN`. Capabilities include:
   - Tool/Function Calling
   - Streaming
   - Vision
   - Reasoning
   - Context Window and Maximum Output Tokens
   - Quantization and source repository details
2. **Capability-Aware Router (`app/services/llm/router.py`):**
   - Routes requests based on workload demand (`CONVERSATION`, `REASONING`, `TOOL_EXECUTION`, `SUMMARIZATION`, `BACKGROUND`).
   - Rejects routing a tool workload to a model with `UNSUPPORTED` or `UNKNOWN` tool support.
   - Detects connection drops (`EndpointConnectionError`) or authentication failures (`AuthenticationError`) and automatically triggers the fallback provider while safeguarding existing context.
3. **Duplicate Tool Prevention:**
   If a model initiates a tool execution that successfully alters external state before an adapter crash, the fallback router does not re-run the tool; instead, it synthesizes the user-facing response using the cached tool result.

### 3.4 Runtime Model Selection Subsystem
Administrators configure active models dynamically using in-chat commands:
- `/model`: Displays current model configuration.
- `/models`: Lists all registered models with capability indicators.
- `/model qwen`: Switches conversation and brainstorming workloads to the local Qwen 3.5 GGUF instance.
- `/model gemini`: Reverts conversation workloads to Google Gemini 3.5 Flash.
- `/model status`: Performs non-destructive connectivity and authentication diagnostics on all configured endpoints.

Selections are committed to the `groups` database table in `settings_json` and restored seamlessly upon application restart.

### 3.5 Tool Safety & Policy Engine
Tools must inherit from `BaseTool` and specify a `PermissionPolicy`:
- `AUTOMATIC`: Read-only queries, memory lookups, and summaries.
- `CONFIRM_AMBIGUOUS`: Expense recording with missing participant data.
- `REQUIRE_APPROVAL`: Financial commitments and external state mutations.
- `EXPLICIT_CONFIRMATION`: Irreversible operations.

### 3.6 Data Persistence & Multi-Tenant Scoping
The relational store (PostgreSQL in production, SQLite in local development) uses `GroupScopedMixin` across all domain models:
- `groups`: Metadata, administrator mappings, and active LLM configuration.
- `messages`: Chronological conversation logs for context assembly.
- `memories`: Structured factual, preference, and decision entries with expiration timestamps.
- `expenses`: Split records, debts, and settlement logs.
- `reminders`: Scheduled task alerts managed by APScheduler.
- `audit_logs`: Tamper-evident ledger of administrative actions and tool invocations.
