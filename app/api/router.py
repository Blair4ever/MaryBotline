from fastapi import APIRouter
from app.api.routes import health
from app.api.webhooks import line

api_router = APIRouter()

# Health endpoints (/health)
api_router.include_router(health.router)

# Webhook endpoints (/webhooks/line and /webhook/line)
api_router.include_router(line.router)
