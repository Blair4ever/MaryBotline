"""
LINE Flex Message builders for rich visual cards in chat.
"""
from typing import Any, Dict, List, Optional


def build_expense_flex(
    title: str,
    total_amount: float,
    share_per_person: float,
    payer_name: str,
    participant_count: int,
) -> Dict[str, Any]:
    """Generates a stylish receipt Flex Message for shared bills."""
    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1DB446",
            "contents": [
                {
                    "type": "text",
                    "text": "🧾 สรุปค่าใช้จ่ายกลุ่ม (MARY)",
                    "weight": "bold",
                    "color": "#FFFFFF",
                    "size": "sm",
                },
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "color": "#FFFFFF",
                    "size": "lg",
                    "margin": "sm",
                    "wrap": True,
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "ยอดรวมทั้งหมด", "size": "sm", "color": "#8C8C8C"},
                        {"type": "text", "text": f"{total_amount:,.2f} THB", "size": "md", "weight": "bold", "align": "end", "color": "#111111"},
                    ],
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "ผู้จ่ายเงิน", "size": "sm", "color": "#8C8C8C"},
                        {"type": "text", "text": payer_name, "size": "sm", "align": "end", "color": "#111111"},
                    ],
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "sm",
                    "contents": [
                        {"type": "text", "text": "จำนวนผู้หาร", "size": "sm", "color": "#8C8C8C"},
                        {"type": "text", "text": f"{participant_count} คน", "size": "sm", "align": "end", "color": "#111111"},
                    ],
                },
                {"type": "separator", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "lg",
                    "contents": [
                        {"type": "text", "text": "ตกคนละ", "size": "md", "weight": "bold", "color": "#1DB446"},
                        {"type": "text", "text": f"{share_per_person:,.2f} บาท", "size": "lg", "weight": "bold", "align": "end", "color": "#1DB446"},
                    ],
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "อย่าลืมโอนคืนผู้จ่ายด้วยนะคะ ✨",
                    "size": "xs",
                    "color": "#AAAAAA",
                    "align": "center",
                }
            ],
        },
    }


def build_reminder_flex(
    title: str,
    message: str,
    scheduled_time: str,
) -> Dict[str, Any]:
    """Generates an eye-catching notification Flex Message."""
    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#FF7A00",
            "contents": [
                {
                    "type": "text",
                    "text": "⏰ แจ้งเตือนจาก MARY",
                    "weight": "bold",
                    "color": "#FFFFFF",
                    "size": "md",
                }
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "size": "lg",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": message,
                    "size": "sm",
                    "color": "#666666",
                    "margin": "md",
                    "wrap": True,
                },
                {"type": "separator", "margin": "lg"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "เวลากำหนด:", "size": "xs", "color": "#AAAAAA"},
                        {"type": "text", "text": scheduled_time, "size": "xs", "align": "end", "color": "#888888"},
                    ],
                },
            ],
        },
    }
