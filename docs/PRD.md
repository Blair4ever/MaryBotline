# AURA Product Requirements Document (PRD)

## 1. Executive Summary
**AURA (Autonomous Group AI Agent)** is an autonomous group productivity platform integrated with the LINE Messaging API. Unlike single-user conversational bots, AURA acts as an intelligent, context-aware group member for collaborative teams and social circles. It observes conversations, retains episodic and factual group memory, coordinates schedules and tasks, manages split expenses, plans events, and interfaces with external developer workflows (GitHub) under strict multi-tenant security boundaries and human-in-the-loop approval gates.

---

## 2. Problem Statement & User Personas
### 2.1 The Problem
LINE groups are ubiquitous across Southeast Asia (particularly Thailand and Japan) for team collaboration, friend circles, family coordination, and project management. However:
- Decisions, deadlines, and action items get buried in hundreds of casual messages.
- Expense tracking and repayments require juggling external spreadsheets or manual calculations.
- Context is lost over time; new members or returning members cannot quickly query past decisions or agreements.
- Standard chatbots are disruptive, spammy, lack group awareness, or treat private messages and group conversations identically.

### 2.2 Target Personas
1. **The Organizer / Team Lead:** Needs automated summaries, action item tracking, decision logging, and deadline reminders delivered directly in LINE.
2. **The Group Member / Collaborator:** Needs seamless bill splitting ("หารค่าข้าว"), fast answers to group facts, and reminder notifications without leaving LINE.
3. **The Developer / Technical Member:** Wants project status, GitHub issue tracking, PR summaries, and repository scaffolding triggered via chat.

---

## 3. Product Scope: MVP vs. Future Horizons

| Functional Area | In Scope (MVP) | Out of Scope (Future Horizon) |
|---|---|---|
| **Interface** | LINE Messaging API (Webhooks, Text, Flex Messages, Quick Replies) | Discord, Slack, Telegram, Web Dashboard |
| **Conversational AI** | Bilingual Thai & English; Slang/Colloquial Thai handling; Contextual intent classification | Voice message transcription, multi-lingual beyond TH/EN |
| **Autonomy Model** | L1 (Observe), L2 (Assist), L3 (Execute) with deterministic permission checks | Fully autonomous money movement, automated external bookings |
| **Group Memory** | Scoped by `group_id`; Factual, Event/Decision, Preferences; Source tracking, correction & deletion | Semantic vector embedding store with pgvector clustering |
| **Expense Manager** | Equal & itemized splits, payer tracking, balance ledger, Thai Baht (THB) calculations | OCR slip verification, PromptPay QR dynamic generation |
| **Reminders & Tasks** | Natural language schedule parsing, APScheduler cron/one-off triggers, push reminders | Calendar sync (Google Calendar, Outlook) |
| **Travel & Events** | Event proposal, availability coordination, itinerary drafting | Direct hotel/flight booking APIs |
| **GitHub Integration** | Read-only repository status, issue/PR summaries, draft creation with confirmation | Automated branch merges, automated deployment triggers |

---

## 4. Functional Requirements

### FR-1: Messaging & Ingestion
- **FR-1.1 Webhook Verification:** The system MUST verify every incoming LINE webhook using HMAC-SHA256 signature verification against `LINE_CHANNEL_SECRET`.
- **FR-1.2 Idempotency:** The system MUST reject or ignore duplicate webhook events based on `webhookEventId`.
- **FR-1.3 Low Latency Acknowledgment:** The system MUST acknowledge LINE webhook requests with HTTP 200 within 2 seconds, processing agent actions asynchronously.

### FR-2: Group Awareness & Identity
- **FR-2.1 Group Scoping:** Every data record (messages, memories, expenses, tasks) MUST belong strictly to a `group_id`. Cross-group data access is strictly forbidden.
- **FR-2.2 Member Directory:** The system MUST track members within each group, recording LINE user IDs, display names, and roles.

### FR-3: Conversational Intelligence & Autonomy
- **FR-3.1 Quiet Observation (L1):** In group chats, AURA MUST NOT respond to casual chit-chat unless addressed, mentioned, or identifying high-confidence utility (decisions, expenses, reminders).
- **FR-3.2 Proactive Assistance (L2):** When a decision or plan is identified, AURA MAY offer structured drafts, summaries, or clarifying questions.
- **FR-3.3 Safe Tool Execution (L3):** When performing actions, AURA MUST execute registered tools, verify output parameters, and format user responses based on verified results.

### FR-4: Group Memory
- **FR-4.1 Categories:** Factual, Event/Decision, User Preference, Project, Short-term context.
- **FR-4.2 CRUD Lifecycle:** Members can view, correct (`correct_group_memory`), or delete/forget (`delete_group_memory`) memories.
- **FR-4.3 Expiration:** Time-bound memories MUST support an `expires_at` UTC timestamp.

### FR-5: Utilities (Expense, Task, Reminder)
- **FR-5.1 Expense Calculation:** Bill splitting must verify participants, calculate exact shares, and track outstanding balances.
- **FR-5.2 Reminders:** Support one-time and recurring reminders with timezone awareness (`Asia/Bangkok`).
- **FR-5.3 Tasks:** Support assigning tasks to specific group members with deadlines and completion statuses.

---

## 5. Non-Functional Requirements (NFR)
- **NFR-1 Security:** Zero hardcoded credentials. User inputs are treated as untrusted text. No direct shell/SQL execution by LLMs.
- **NFR-2 Performance:** Asynchronous non-blocking architecture (FastAPI + AsyncIO + SQLAlchemy Async).
- **NFR-3 Reliability:** Automatic graceful recovery from database disconnects and third-party API rate limits.
- **NFR-4 Observability:** Structured JSON logging, audit logging for all L3 tool executions, and health metrics.
- **NFR-5 Data Integrity:** Timestamps stored in UTC; displayed in `Asia/Bangkok` (UTC+7).

