import json
import logging
from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import verify_line_signature
from app.database.session import AsyncSessionLocal, get_db
from app.models.group import Group, Member
from app.models.conversation import Message
from app.schemas.webhook import LineEvent, LineWebhookPayload
from app.services.line.client import LineMessagingService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["LINE Webhook"])


async def process_single_event(event_dict: dict) -> None:
    """
    Background worker task to process an individual LINE event.
    Guarantees database persistence, member/group registration, and idempotency.
    """
    settings = get_settings()
    event = LineEvent(**event_dict)
    event_id = event.webhookEventId
    target_id = event.source.target_id
    user_id = event.source.userId or "unknown_user"

    async with AsyncSessionLocal() as db:
        # Idempotency check: verify if webhookEventId was already processed
        stmt = select(Message).where(Message.webhook_event_id == event_id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            logger.info(f"Event {event_id} already processed. Skipping.")
            return

        # Ensure Group exists in DB
        group_stmt = select(Group).where(Group.id == target_id)
        group_res = await db.execute(group_stmt)
        group = group_res.scalar_one_or_none()
        if not group:
            group = Group(id=target_id, is_active=True)
            db.add(group)
            await db.flush()

        # Ensure Member exists
        if user_id != "unknown_user":
            member_stmt = select(Member).where(
                Member.group_id == target_id,
                Member.line_user_id == user_id,
            )
            member_res = await db.execute(member_stmt)
            member = member_res.scalar_one_or_none()
            if not member:
                # Fetch profile if available
                line_service = LineMessagingService()
                profile = await line_service.get_profile(
                    user_id=user_id,
                    group_id=event.source.groupId,
                )
                display_name = profile.get("displayName", f"User_{user_id[:6]}") if profile else f"User_{user_id[:6]}"
                picture_url = profile.get("pictureUrl") if profile else None

                member = Member(
                    group_id=target_id,
                    line_user_id=user_id,
                    display_name=display_name,
                    picture_url=picture_url,
                )
                db.add(member)
                await db.flush()

        # Record incoming message
        if event.type == "message" and event.message:
            msg_obj = Message(
                id=event.message.id,
                group_id=target_id,
                sender_id=user_id,
                sender_name=member.display_name if "member" in locals() and member else "Unknown",
                message_type=event.message.type,
                text=event.message.text,
                reply_token=event.replyToken,
                webhook_event_id=event_id,
                direction="incoming",
            )
            db.add(msg_obj)
            await db.commit()
            logger.info(f"Recorded incoming message {event.message.id} from {user_id} in {target_id}: {event.message.text}")

            # Phase 1 verification: If bot is in test mode or replied, handle ping/pong
            if event.message.text and event.replyToken:
                cleaned_text = event.message.text.strip().lower()
                if cleaned_text == "ping":
                    line_client = LineMessagingService()
                    await line_client.reply_text(event.replyToken, "pong! MARY is alive.")
                elif cleaned_text in ["mary status", "status"]:
                    line_client = LineMessagingService()
                    await line_client.reply_text(
                        event.replyToken,
                        f"MARY Platform\nTarget ID: {target_id}\nStatus: Active"
                    )


@router.post("/webhook/line")
async def line_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: Annotated[str | None, Header()] = None,
):
    """
    LINE Webhook endpoint.
    1. Validates X-Line-Signature HMAC-SHA256 signature.
    2. Enqueues events for background idempotent processing.
    3. Returns 200 OK immediately to LINE servers.
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

    # Dispatch events asynchronously
    for event in payload.events:
        background_tasks.add_task(process_single_event, event.model_dump())

    return {"status": "ok", "events_received": len(payload.events)}

