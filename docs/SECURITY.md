# AURA Security & Privacy Architecture

## 1. Security Architecture Principles
1. **Defense-in-Depth:** Multiple validation layers (cryptographic signature verification -> rate-limiting/idempotency -> tenant boundary enforcement -> typed tool argument validation -> human approval gate).
2. **Untrusted Input Invariant:** All incoming messages, attachment text, and webhook payloads are treated as untrusted data. User messages are never concatenated directly into system control instructions.
3. **No Direct Execution by LLMs:** The AI reasoning engine cannot run arbitrary SQL, shell scripts, or operating system calls.
4. **Tenant Isolation by Design:** Database queries must always be constrained by `group_id`.

---

## 2. Threat Modeling & Mitigations

| Threat | Risk Level | Mitigation Strategy |
|---|---|---|
| **Forged Webhooks** | Critical | Every request to `/api/webhooks/line` requires constant-time HMAC-SHA256 verification using `LINE_CHANNEL_SECRET` against the `X-Line-Signature` header. |
| **Replay Attacks** | High | `webhookEventId` deduplication store. Duplicate event IDs are acknowledged with 200 OK immediately and dropped from processing. |
| **Prompt Injection** | High | Strict prompt compartmentalization. System instructions enforce that user messages cannot redefine system rules or override permission levels. |
| **Cross-Tenant Data Leakage** | Critical | Multi-tenant scoping via `GroupScopedMixin`. All memory lookups, message queries, and expense balance calculations require `WHERE group_id = :group_id`. |
| **Unauthorized Destructive Actions** | High | `PermissionEngine` policy mapping. Destructive commands (repository deletion, irreversible state wipes) require multi-member or explicit approval gates. |
| **Credential & Secret Exposure** | Critical | Secrets stored strictly in environment variables (`.env`). Automated `.gitignore` rules prevent git commits of secrets or keys. |

---

## 3. Cryptographic Signature Verification
LINE uses HMAC-SHA256 with the Channel Secret as the secret key:

```python
def verify_line_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    hash_digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(hash_digest).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature)
```

Requests failing this check return HTTP 403 Forbidden and are logged to the security audit trail.

---

## 4. Permission & Approval Matrix

| Operation Category | Specific Action | Autonomous Policy |
|---|---|---|
| **Informational** | Summarize conversation, Answer questions | `AUTOMATIC` |
| **Memory** | Save new memory, Search memories | `AUTOMATIC` |
| **Memory Revision** | Correct memory, Delete memory | `AUTOMATIC` (scoped to group) |
| **Expenses** | Calculate split | `AUTOMATIC` |
| **Expenses** | Record shared expense with unambiguous details | `AUTOMATIC` |
| **Expenses** | Record shared expense with ambiguous details | `CONFIRM_AMBIGUOUS` (asks for confirmation) |
| **Reminders / Tasks** | Schedule one-off or recurring reminders | `AUTOMATIC` |
| **Travel & Events** | Draft itinerary, collect availability | `AUTOMATIC` |
| **Travel & Events** | Book hotel / payment transfer | `REQUIRE_APPROVAL` (requires explicit human approval) |
| **GitHub** | Summarize PRs / issues, create draft issue | `AUTOMATIC` |
| **GitHub** | Publish public repository | `REQUIRE_APPROVAL` |
| **GitHub** | Delete repository | `EXPLICIT_CONFIRMATION` |

---

## 5. Privacy & Data Retention
- **Memory Right-to-be-Forgotten:** Members can request `delete_group_memory(memory_id)`, which deactivates or removes the fact from context.
- **Expiration:** Time-bound facts (e.g., parking spot, temporary door code) support TTL (`expires_at`), after which they are omitted from prompt contexts.
- **Data Minimization:** No personal phone numbers, passwords, or credit card numbers are stored.

