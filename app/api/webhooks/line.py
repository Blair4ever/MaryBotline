import json
import logging
from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from sqlalchemy import select

from app.config import get_settings
from app.core.security import verify_line_signature
from app.database.session import AsyncSessionLocal
from app.models.group import Group, Member
from app.models.conversation import Message
from app.schemas.webhook import LineEvent, LineWebhookPayload
from app.services.line.client import LineMessagingService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Webhooks"])


async def process_single_event(event_dict: dict) -> None:
    """
    Background worker task to process an individual LINE event idempotently.
    Ensures message persistence, auto-registers group & member, and tracks duplicate event IDs.
    """
    event = LineEvent(**event_dict)
    event_id = event.webhookEventId
    target_id = event.source.target_id
    user_id = event.source.userId or "unknown_user"

    async with AsyncSessionLocal() as db:
        # 1. Idempotency check: verify if webhookEventId was already processed
        stmt = select(Message).where(Message.webhook_event_id == event_id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            logger.info(f"Event {event_id} already processed. Skipping duplicate.")
            return

        # 2. Ensure Group exists in DB
        group_stmt = select(Group).where(Group.id == target_id)
        group_res = await db.execute(group_stmt)
        group = group_res.scalar_one_or_none()
        if not group:
            group = Group(id=target_id, is_active=True)
            db.add(group)
            await db.flush()

        # 3. Ensure Member exists
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

        # 4. Record incoming message
        if event.type == "message" and event.message:
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
            logger.info(f"Recorded incoming message {event.message.id} from {user_id} in {target_id}")

            # Basic ping/status echo check
            if event.message.text and event.replyToken:
                cleaned_text = event.message.text.strip().lower()
                line_client = LineMessagingService()
                if cleaned_text == "ping":
                    await line_client.reply_text(event.replyToken, "pong! MARY is alive.")
                elif cleaned_text in ["mary status", "status"]:
                    await line_client.reply_text(
                        event.replyToken,
                        f"MARY Platform\nTarget: {target_id}\nStatus: Active"
                    )


@router.post("/webhooks/line")
@router.post("/webhook/line")
async def line_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: Annotated[str | None, Header()] = None,
):
    """
    LINE Webhook ingestion endpoint.
    - Validates X-Line-Signature HMAC-SHA256 signature.
    - Fast HTTP 200 response.
    - Asynchronously dispatches events to the worker.
    """
    settings = get_settings()
    body_bytes = await request.body()

    # Enforce signature verification when secret is configured
    if settings.line_channel_secret:
        if not x_line_signature or not verify_line_signature(
            body=body_bytes,
            signature=x_line_signature,
            channel_secret=settings.line_channel_secret,
        ):
            logger.warning("Rejected webhook request with invalid signature.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid LINE signature",
            )

    try:
        data = json.loads(body_bytes.decode("utf-8"))
        payload = LineWebhookPayload(**data)
    except Exception as exc:
        logger.error(f"Failed to parse webhook payload: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON or schema mismatch",
        )

    for event in payload.events:
        background_tasks.add_task(process_single_event, event.model_dump())

    return {"status": "ok", "events_received": len(payload.events)}
