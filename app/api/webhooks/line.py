import json
import logging
from typing import Annotated, Any, Dict, Optional
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from sqlalchemy import select

from app.config import get_settings
from app.core.security import verify_line_signature
from app.database.session import AsyncSessionLocal
from app.models.group import Group, Member
from app.models.conversation import Message
from app.schemas.group_settings import parse_group_settings
from app.schemas.webhook import LineEvent, LineWebhookPayload
from app.services.line.client import LineMessagingService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Webhooks"])


def mask_identifier(val: Optional[str]) -> str:
    """Safe identifier mask for logs to protect user privacy."""
    if not val:
        return "none"
    if len(val) <= 8:
        return val[:3] + "***"
    return val[:4] + "..." + val[-4:]


async def process_single_event(event_dict: dict) -> None:
    """
    Background worker task to process an individual LINE event idempotently.
    Enforces passive listening, intent-based activation, and safeguards against duplicate/unwanted replies.
    """
    event = LineEvent(**event_dict)
    destination = event_dict.get("destination") or ""
    event_id = event.webhookEventId
    target_id = event.source.target_id
    user_id = event.source.userId or "unknown_user"
    settings = get_settings()

    safe_group_id = mask_identifier(target_id)
    safe_user_id = mask_identifier(user_id)
    is_group = event.source.type in ["group", "room"]

    # ---------------------------------------------------------------------
    # Safeguard 1: Respect event mode (ignore standby events)
    # ---------------------------------------------------------------------
    if event.mode == "standby":
        logger.info(
            f"[Webhook Diagnostic] event_id={event_id} type={event.type} group={safe_group_id} "
            f"activated=False reason='standby mode event ignored'"
        )
        return

    # ---------------------------------------------------------------------
    # Safeguard 2: Ignore unsupported event types
    # ---------------------------------------------------------------------
    if event.type != "message":
        logger.info(
            f"[Webhook Diagnostic] event_id={event_id} type={event.type} group={safe_group_id} "
            f"activated=False reason='unsupported event type: {event.type}'"
        )
        return

    # ---------------------------------------------------------------------
    # Safeguard 3: Ignore non-text messages unless explicitly supported
    # ---------------------------------------------------------------------
    if not event.message or event.message.type != "text":
        msg_type = event.message.type if event.message else "none"
        logger.info(
            f"[Webhook Diagnostic] event_id={event_id} type={event.type} msg_type={msg_type} group={safe_group_id} "
            f"activated=False reason='unsupported non-text message type: {msg_type}'"
        )
        return

    # ---------------------------------------------------------------------
    # Safeguard 4: Ignore messages sent by MARY itself
    # ---------------------------------------------------------------------
    bot_id = settings.line_bot_user_id or destination
    if bot_id and user_id == bot_id:
        logger.info(
            f"[Webhook Diagnostic] event_id={event_id} type={event.type} group={safe_group_id} "
            f"activated=False reason='ignored message sent by bot itself'"
        )
        return

    async with AsyncSessionLocal() as db:
        # -----------------------------------------------------------------
        # Safeguard 5 & 6: Idempotency check against duplicate webhookEventId
        # -----------------------------------------------------------------
        stmt = select(Message).where(Message.webhook_event_id == event_id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            logger.info(
                f"[Webhook Diagnostic] event_id={event_id} group={safe_group_id} "
                f"activated=False reason='duplicate webhookEventId already processed'"
            )
            return

        # -----------------------------------------------------------------
        # Group & Member Auto-Registration & Configuration
        # -----------------------------------------------------------------
        group_stmt = select(Group).where(Group.id == target_id)
        group_res = await db.execute(group_stmt)
        group = group_res.scalar_one_or_none()
        if not group:
            group = Group(id=target_id, is_active=True)
            db.add(group)
            await db.flush()

        group_settings = parse_group_settings(group.settings_json)

        display_name = f"User_{user_id[:6]}"
        if user_id != "unknown_user":
            member_stmt = select(Member).where(
                Member.group_id == target_id,
                Member.line_user_id == user_id,
            )
            member_res = await db.execute(member_stmt)
            member = member_res.scalar_one_or_none()
            if not member:
                line_service = LineMessagingService()
                profile = await line_service.get_profile(
                    user_id=user_id,
                    group_id=event.source.groupId,
                )
                if profile:
                    display_name = profile.get("displayName", display_name)
                    picture_url = profile.get("pictureUrl")
                else:
                    picture_url = None

                member = Member(
                    group_id=target_id,
                    line_user_id=user_id,
                    display_name=display_name,
                    picture_url=picture_url,
                )
                db.add(member)
                await db.flush()
            else:
                display_name = member.display_name

        # -----------------------------------------------------------------
        # Passive Listening: Store message for shared memory & idempotency
        # -----------------------------------------------------------------
        msg_obj = Message(
            id=event.message.id,
            group_id=target_id,
            sender_id=user_id,
            sender_name=display_name,
            message_type=event.message.type,
            text=event.message.text,
            reply_token=event.replyToken,
            webhook_event_id=event_id,
            direction="incoming",
        )
        db.add(msg_obj)
        await db.commit()
        logger.info(f"Recorded incoming message {event.message.id} from {safe_user_id} in {safe_group_id}")

        # -----------------------------------------------------------------
        # Intent-Based Activation Decision
        # -----------------------------------------------------------------
        text = event.message.text or ""
        clean_text = text.strip()
        lower_text = clean_text.lower()

        # Check LINE mention metadata
        is_mentioned = event.message.is_bot_mentioned(bot_user_id=bot_id)

        should_activate = False
        activation_reason = ""

        if not is_group:
            # 1-on-1 chats directly with the bot always activate
            should_activate = True
            activation_reason = "1-on-1 direct message"
        else:
            # Group chat: apply Intent-Based Activation rules
            if not group_settings.passive_listening:
                should_activate = True
                activation_reason = "group passive_listening disabled"
            elif is_mentioned:
                # Rule B.1: Mentioned using LINE mention metadata
                should_activate = True
                activation_reason = "LINE mention metadata matched MARY"
            elif lower_text.startswith("mary") or clean_text.startswith("แมรี่"):
                # Rule B.2: Starts with "MARY" or "Mary" (case-insensitive) or "แมรี่"
                should_activate = True
                activation_reason = "message begins with MARY prefix"
            elif clean_text.startswith("/") or lower_text in ["ping", "status"]:
                # Rule B.3: Configured commands (/help, /summary, /tasks, etc.)
                cmd = clean_text.split()[0] if clean_text else "command"
                should_activate = True
                activation_reason = f"command invoked: {cmd}"
            elif not group_settings.mention_required:
                should_activate = True
                activation_reason = "mention_required disabled for group"
            else:
                # Rule A: Passive listening default - do not generate AI response
                should_activate = False
                activation_reason = "passive listening: ordinary conversation without mention or command"

        ai_provider = settings.llm_provider
        logger.info(
            f"[Webhook Diagnostic] event_id={event_id} type={event.type} group={safe_group_id} "
            f"is_group={is_group} activated={should_activate} reason='{activation_reason}' provider={ai_provider}"
        )

        # -----------------------------------------------------------------
        # Response Dispatch (Ensure at most ONE logical response)
        # -----------------------------------------------------------------
        if not should_activate:
            logger.info(
                f"[Webhook Diagnostic] event_id={event_id} reply_sent=False reason='Activation criteria not met'"
            )
            return

        if not event.replyToken:
            logger.warning(f"Active event {event_id} has no replyToken. Cannot reply.")
            return

        line_client = LineMessagingService()
        reply_sent = False

        # Fast path commands
        if lower_text == "ping":
            reply_sent = await line_client.reply_text(event.replyToken, "pong! MARY is alive.")
        elif lower_text in ["mary status", "status", "/status"]:
            status_text = (
                f"🤖 MARY Platform\n"
                f"📍 Group: {safe_group_id}\n"
                f"⚙️ Passive Listening: {'เปิด' if group_settings.passive_listening else 'ปิด'}\n"
                f"🏷️ Mention Required: {'เปิด' if group_settings.mention_required else 'ปิด'}\n"
                f"🔔 Proactive Alerts: {'เปิด' if group_settings.proactive_notifications else 'ปิด'}\n"
                f"🧠 Memory: {'เปิด' if group_settings.memory_enabled else 'ปิด'}"
            )
            reply_sent = await line_client.reply_text(event.replyToken, status_text)
        elif clean_text.lower().startswith("/model"):
            from app.services.llm.commands import handle_model_command
            # Admin = DB role is 'admin' OR user is listed in MARY_ADMIN_USER_IDS env var
            is_hardcoded_admin = user_id in settings.admin_user_ids
            is_db_admin = not is_group or (member and member.role == "admin")
            is_admin = is_hardcoded_admin or is_db_admin
            cmd_reply = await handle_model_command(
                text=clean_text,
                group_id=target_id,
                user_id=user_id,
                is_admin=is_admin,
                db=db,
            )
            if cmd_reply:
                reply_sent = await line_client.reply_text(event.replyToken, cmd_reply)
        elif clean_text.lower().startswith("/help"):
            help_text = (
                "👋 สวัสดีค่ะ แมรี่ (MARY) พร้อมช่วยเหลือค่ะ!\n\n"
                "📌 วิธีเรียกใช้งานในกลุ่ม:\n"
                "1. แท็กชื่อ @MARY\n"
                "2. พิมพ์ขึ้นต้นด้วย 'MARY' หรือ 'แมรี่' เช่น 'MARY ช่วยสรุปนัดวันนี้หน่อย'\n"
                "3. ใช้คำสั่ง เช่น /help, /tasks, /summary, /status, ping\n\n"
                "💡 ในบทสนทนาทั่วไป แมรี่จะรับฟังเงียบๆ เพื่อไม่รบกวนสมาชิกในกลุ่มค่ะ"
            )
            reply_sent = await line_client.reply_text(event.replyToken, help_text)
        else:
            # Delegate to AI Agent Orchestrator
            try:
                from app.agent.orchestrator import AgentOrchestrator
                orchestrator = AgentOrchestrator()
                ai_reply = await orchestrator.handle_message(
                    group_id=target_id,
                    sender_id=user_id,
                    sender_name=display_name,
                    text=event.message.text,
                    reply_token=event.replyToken,
                    is_group=is_group,
                    is_mentioned=is_mentioned,
                    group_settings=group_settings,
                )
                reply_sent = bool(ai_reply)
            except Exception as err:
                logger.error(f"Agent Orchestrator failed for event {event_id}: {err}", exc_info=True)
                if event.replyToken:
                    try:
                        await line_client.reply_text(
                            event.replyToken,
                            "ขออภัยค่ะ ระบบ AI ปลายทางกำลังโหลดสูงชั่วคราว รบกวนลองส่งใหม่อีกครั้งนะคะ 🙏"
                        )
                    except Exception:
                        pass

        logger.info(
            f"[Webhook Diagnostic] event_id={event_id} group={safe_group_id} reply_sent={reply_sent}"
        )


@router.post("/webhooks/line")
@router.post("/webhook/line")
@router.post("/api/webhooks/line")
@router.post("/api/webhook/line")
@router.post("/callback")
@router.post("/webhook")
async def line_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: Annotated[str | None, Header()] = None,
):
    """
    LINE Webhook ingestion endpoint.
    - Validates X-Line-Signature HMAC-SHA256 signature when secret is configured.
    - Fast HTTP 200 response.
    - Dispatches events to background worker.
    """
    settings = get_settings()
    body_bytes = await request.body()
    signature = (
        x_line_signature
        or request.headers.get("x-line-signature")
        or request.headers.get("X-Line-Signature")
    )

    # 1. Enforce signature verification when secret is configured
    if settings.line_channel_secret:
        if not signature or not verify_line_signature(
            body=body_bytes,
            signature=signature,
            channel_secret=settings.line_channel_secret,
        ):
            logger.warning("Rejected webhook request with invalid signature.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid LINE signature",
            )

    # 2. Parse JSON payload
    try:
        data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except json.JSONDecodeError:
        data = {}

    # LINE Verify Webhook check: If events list is empty, return 200 immediately
    if isinstance(data, dict) and data.get("events") == []:
        return {"status": "ok", "detail": "LINE verify webhook ok"}

    try:
        payload = LineWebhookPayload(**data)
    except Exception as exc:
        logger.error(f"Failed to parse webhook payload: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON or schema mismatch",
        )

    # 3. Asynchronously dispatch each event to background worker
    destination = payload.destination or ""
    for event in payload.events:
        event_dict = event.model_dump()
        event_dict["destination"] = destination
        background_tasks.add_task(process_single_event, event_dict)

    return {"status": "ok", "events_received": len(payload.events)}
