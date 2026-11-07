# AURA API Design & Webhook Specification

## 1. HTTP Endpoints Overview

| Method | Path | Description | Auth / Security |
|---|---|---|---|
| `POST` | `/api/webhooks/line` | Ingests incoming LINE webhook events | `X-Line-Signature` HMAC-SHA256 |
| `GET` | `/api/health` | Service liveness, readiness, and config diagnostics | Public |
| `GET` | `/api/admin/metrics` | System operational metrics and active group counts | Admin Token / Local |
| `GET` | `/api/admin/audit` | Audit log inspection | Admin Token |

---

## 2. LINE Webhook Endpoint

### `POST /api/webhooks/line`

#### Headers
- `X-Line-Signature`: Base64-encoded HMAC-SHA256 signature generated with `LINE_CHANNEL_SECRET`.
- `Content-Type`: `application/json; charset=UTF-8`

#### Payload Schema (JSON)
```json
{
  "destination": "U1234567890abcdef1234567890abcdef",
  "events": [
    {
      "type": "message",
      "mode": "active",
      "timestamp": 1625642911123,
      "source": {
        "type": "group",
        "groupId": "Caabbccddeeff00112233445566778899",
        "userId": "U00112233445566778899aabbccddeeff"
      },
      "webhookEventId": "01FZ74A0TDDPYRVKNK77XKC3ZR",
      "deliveryContext": {
        "isRedelivery": false
      },
      "replyToken": "nHuyWiB7yP5Zw52FIkcQobQuGDXCTA",
      "message": {
        "id": "325708",
        "type": "text",
        "text": "วันนี้กินข้าว 850 บาท 4 คน ฉันจ่ายเอง"
      }
    }
  ]
}
```

#### Responses
- **`200 OK`**: Webhook received, signature validated, events enqueued for background processing.
  ```json
  {
    "status": "ok",
    "events_received": 1
  }
  ```
- **`403 Forbidden`**: Missing or invalid `X-Line-Signature`.
  ```json
  {
    "detail": "Invalid LINE signature"
  }
  ```
- **`400 Bad Request`**: Malformed JSON or unparseable event format.

---

## 3. Health Check Endpoint

### `GET /api/health`

#### Response (`200 OK`)
```json
{
  "status": "healthy",
  "app_name": "AURA",
  "environment": "development",
  "timezone": "Asia/Bangkok",
  "timestamp_utc": "2026-11-07T12:54:00.123456+00:00",
  "timestamp_local": "2026-11-07 19:54:00 +07",
  "line_configured": true,
  "database_connected": true
}
```

---

## 4. AI Agent Tool Function Calling Schemas

Tools registered in `app/tools/` adhere to standard OpenAI/Gemini tool calling definitions.

### Example: `record_expense`
```json
{
  "type": "function",
  "function": {
    "name": "record_expense",
    "description": "Calculate and record a shared group expense, splitting equally or itemized.",
    "parameters": {
      "type": "object",
      "properties": {
        "title": {
          "type": "string",
          "description": "Description of what was purchased (e.g. 'Dinner', 'Shabu', 'Grab')."
        },
        "total_amount": {
          "type": "number",
          "description": "Total amount in THB."
        },
        "payer_id": {
          "type": "string",
          "description": "LINE userId of the person who paid the total bill."
        },
        "participant_count": {
          "type": "integer",
          "description": "Number of participants sharing the bill."
        },
        "split_type": {
          "type": "string",
          "enum": ["equal", "custom", "exact"],
          "default": "equal"
        }
      },
      "required": ["title", "total_amount", "payer_id"]
    }
  }
}
```

### Example: `schedule_reminder`
```json
{
  "type": "function",
  "function": {
    "name": "schedule_reminder",
    "description": "Schedule a reminder notification for the group or a specific member.",
    "parameters": {
      "type": "object",
      "properties": {
        "title": {
          "type": "string",
          "description": "Short title of reminder."
        },
        "message": {
          "type": "string",
          "description": "Message text to be pushed."
        },
        "scheduled_time_iso": {
          "type": "string",
          "description": "ISO 8601 UTC timestamp when reminder should fire."
        },
        "recurrence": {
          "type": "string",
          "enum": ["once", "daily", "weekly"],
          "default": "once"
        }
      },
      "required": ["title", "message", "scheduled_time_iso"]
    }
  }
}
```

