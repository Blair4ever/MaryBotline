# Changelog

All notable changes to the **MARY** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - 2026-11-09

### Added
- **Qwen 3.5 9B GGUF Model Integration:** Added native capability profile for `CapitalSTEEZ47/Qwen3.5-9B-The-Defiant-Fable-Uncensored-Heretic-NEO-IMATRIX-MAX-MTP-GGUF` (`Qwen3.5-9B-The-Defiant-Fable-Uncnr-Heretic-NEO-MAX-MTP-IQ3_M.gguf`).
- **OpenAI-Compatible Custom Endpoint Adapter:** Implemented `OpenAICompatibleClient` supporting configurable base URL, Bearer authentication, normalized `LLMResponse`, and token usage tracking without fabricating missing counts.
- **Model Capability Registry (`ModelRegistry`):** Formalized capability profiling (`ModelCapabilityProfile`) tracking context window (32k), quantization parameters, tool support status, and reasoning flags.
- **Runtime Model Selection (`app/services/llm/commands.py`):**
  - `/model`: View active conversation and tool model.
  - `/models`: List configured models with capability icons.
  - `/model qwen`: Set Qwen 3.5 GGUF as default conversation model.
  - `/model gemini`: Set Gemini 3.5 Flash as default conversation model.
  - `/model status`: Perform live diagnostic health checks differentiating offline network connection refusal from authentication failures.
- **Database Persistence for Model Settings:** Persist model choices in `Group.settings_json` ensuring settings survive application restarts.
- **Zero-Duplicate Fallback Engine:** Automatic fallback to Gemini upon endpoint connection drops while ensuring already-committed tool actions are never re-executed.
- **Automated Test Suite:** 50 unit and integration tests covering model selection, capability validation, admin authorization, and fallback behavior using mocked transports.

---

## [0.2.0] - 2026-11-08

### Added
- **Passive Listening & Intent Activation (L1/L2 Autonomy):** Context analysis pipeline to extract long-term factual memories without triggering chat spam.
- **Group Safeguards & Admin Permissions:** Policy engine for administrative actions, destructive operations, and tool confirmation gates.
- **Gemini 3.5 Flash Integration:** Official Google GenAI SDK integration supporting native tool/function calling and multi-modal context.

---

## [0.1.0] - 2026-11-07

### Added
- **Initial Core Architecture:** FastAPI asynchronous web framework with Uvicorn server.
- **LINE Messaging API Integration:** Webhook receiver endpoint at `/api/webhooks/line` with HMAC-SHA256 signature verification and idempotency check.
- **Domain Tools:** Initial expense splitting, task tracking, and reminder scheduling using APScheduler.
- **Relational Storage:** PostgreSQL and SQLite asynchronous schema with multi-tenant `group_id` scoping.
