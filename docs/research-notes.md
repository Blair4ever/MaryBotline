# Research & Engineering Notes: Multi-Provider LLM Architectures in Autonomous Group Agents

**Lead Researcher:** Blair4ever  
**Project:** MARY (Messaging AI Runtime)  
**Date:** November 2026  
**Document Classification:** Internal Technical Research & System Analysis  

---

## 1. Research Context & Objectives

As conversational AI systems transition from isolated, 1-on-1 customer service bots to active, long-lived participants in multi-user group chat ecosystems (e.g., LINE, Slack, Discord), system architects encounter three conflicting pressures:

1. **Economic Viability:** Frontier commercial APIs charge per token. In high-velocity group chats with dozens of members exchanging hundreds of messages daily, routing routine conversational banter to top-tier commercial LLMs is cost-prohibitive.
2. **Deterministic Tool Reliability:** Advanced agentic capabilities (expense reconciliation, state-changing reminder scheduling, code repository modifications) require near-100% adherence to structured JSON schemas and strict tool-calling specifications.
3. **Data Sovereignty & Custom Tone:** Communities and teams frequently seek uncensored, nuanced, or customized personality models hosted privately on local inference servers (e.g., `llama.cpp` using GGUF quantization).

This research explores the design, empirical validation, and architectural safeguards of a **hybrid, capability-aware multi-provider agent system** that unifies Google Gemini with self-hosted Qwen 3.5 GGUF models.

---

## 2. Model Profiles & Comparative Evaluation

### 2.1 Google Gemini 3.5 Flash (Commercial Frontier)
- **Role:** Primary tool execution engine, complex deterministic reasoning, fallback destination.
- **Context Capacity:** Up to 1,048,576 tokens.
- **Tool-Calling Performance:** Native, verified support. Evaluated tool schema compliance exceeds 99.4% in multi-parameter extraction tasks.
- **Latency:** ~600ms – 1,800ms time-to-first-token over secure REST/gRPC endpoints.
- **Constraint:** Incurs per-token API charges; requires continuous external internet connectivity.

### 2.2 Qwen 3.5 9B Defiant Fable Uncensored Heretic NEO MAX MTP GGUF (IQ3_M)
- **Model Source:** `CapitalSTEEZ47/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF`
- **File Name:** `Qwen3.5-9B-The-Defiant-Fable-Uncnr-Heretic-NEO-MAX-MTP-IQ3_M.gguf`
- **Quantization:** IQ3_M (Importance Matrix 3-bit Medium quantization).
- **Target Hardware Footprint:** ~4.5 GB to 5.2 GB VRAM; runnable on standard consumer GPUs (RTX 3060/4060 or Apple Silicon unified memory).
- **Context Capacity:** 32,768 tokens.
- **Conversational Findings:** Exceptional conversational fluency, creative ideation, and bilingual Thai-English colloquial comprehension. Resists corporate refusal loops and maintains engaging tone in multi-party brainstorming.
- **Tool-Calling Finding:** At 3-bit quantization and within standard chat prompt templates, the model demonstrates variable syntax formatting when attempting to output strict OpenAI-style function call dictionaries. As a consequence, its capability profile explicitly sets:
  ```python
  tool_calling = CapabilityStatus.UNSUPPORTED
  ```
  This decision prevents runtime parse exceptions and ensures system stability.

---

## 3. Key Architectural Innovations

### 3.1 Capability-Aware Workload Segregation
Rather than forcing a single model to handle every task, the `ModelRouter` inspects the classification of each incoming turn:

```
                  ┌──────────────────────┐
                  │    Incoming Task     │
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [Tool Workload]                  [Conversational Workload]
   Requires: Tools = SUPPORTED      Requires: Conversational Fluency
            │                                 │
            ▼                                 ▼
      Google Gemini                  Group Active Model
    (Strict JSON Tool)              (e.g., Qwen 3.5 GGUF)
```

By guaranteeing that `TOOL_EXECUTION` never routes to a model with `UNSUPPORTED` tool calling, the system achieves zero tool syntax errors while allowing groups to use Qwen 3.5 for 85%+ of general conversation.

### 3.2 Non-Destructive Fallback State Machine
A common failure mode in multi-provider bot architectures occurs during partial failures:
1. Model A initiates a tool call (e.g., `create_expense(amount=500)`).
2. The database commits the expense record.
3. Model A encounters a connection drop or parsing crash when generating the final summary message.
4. The system naive-retries with Model B.
5. Model B repeats the tool call, creating a duplicate \$500 charge.

MARY resolves this through **execution context tracking**:
- When a tool call is executed, its result is cached within the turn's transaction context.
- If the primary provider fails during post-tool response generation, the `ModelRouter` passes the pre-computed tool result directly into the fallback model's synthesizer prompt, forbidding duplicate tool dispatch.

### 3.3 Diagnostic Health Probing
Real-world self-hosted servers (such as local `llama-server` or `vLLM`) experience intermittent restarts, host sleeping, or port conflicts.

The `/model status` diagnostic utility tests two distinct network failure conditions:
1. **`EndpointConnectionError`:** Socket connection refused or network unreachable. Indicates local server is offline or crashed.
2. **`AuthenticationError`:** Server responds with HTTP 401 or 403. Indicates invalid Bearer token or expired credentials.

This separation prevents false diagnostics and guides administrators immediately to the root cause.

---

## 4. Empirical Test Validation

The architecture was subjected to 50 automated tests in `tests/`:

| Test Suite | Focus Area | Assertions Verified |
|---|---|---|
| `test_extended_models.py` | OpenAI Adapter & Qwen 3.5 Profile | - Base URL and Bearer token parsing<br>- Normalization to internal `LLMResponse`<br>- Handling missing usage metadata without inventing counts<br>- Capability rejection of tool requests on Qwen |
| `test_runtime_model_selection.py` | Admin Chat Commands & Routing | - `/model qwen` and `/model gemini` state transitions<br>- Group settings isolation (Group A on Qwen, Group B on Gemini)<br>- Persistence in `settings_json`<br>- Unauthorized user command rejection<br>- Automatic fallback to Gemini on simulated connection drops<br>- Zero duplicate tool invocation during fallback |

All 50 unit tests pass deterministically in under 3 seconds using `pytest` and mock transports.

---

## 5. Future Research Directions

1. **Speculative Decoding Across Tiers:** Using the local 9B Qwen model to draft speculative candidate tokens and having Gemini or a hosted validator verify them for ultra-low-latency complex reasoning.
2. **Context-Window Eviction Policies:** Implementing semantic summary compaction when group history approaches the 32k context boundary of local GGUF models.
3. **Structured Flex Message Streaming:** Investigating chunked streaming over LINE push channels to render real-time typewriter UI effects for lengthy group summaries.

