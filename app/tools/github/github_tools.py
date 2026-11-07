import logging
import os
from typing import Any, Dict, List, Optional
from app.config import get_settings
from app.tools.base import tool_registry

logger = logging.getLogger(__name__)


@tool_registry.register(
    name="generate_project_readme",
    description="Generate a clean, structured README.md for a new project or repository.",
    parameters={
        "type": "object",
        "properties": {
            "project_name": {
                "type": "string",
                "description": "Name of the project.",
            },
            "description": {
                "type": "string",
                "description": "Summary of project purpose and architecture.",
            },
            "tech_stack": {
                "type": "string",
                "description": "Technologies used (e.g. 'Python, FastAPI, PostgreSQL').",
            },
        },
        "required": ["project_name", "description"],
    },
)
async def generate_project_readme(
    project_name: str,
    description: str,
    tech_stack: Optional[str] = "Python, FastAPI",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generates standard Markdown documentation without secrets."""
    readme_content = (
        f"# {project_name}\n\n"
        f"> {description}\n\n"
        f"## 🛠️ Tech Stack\n"
        f"{tech_stack}\n\n"
        f"## 🚀 Getting Started\n"
        f"```bash\n"
        f"# Clone the repository\n"
        f"git clone https://github.com/your-org/{project_name.lower().replace(' ', '-')}.git\n"
        f"```\n\n"
        f"## 📄 License\n"
        f"MIT License\n"
    )

    return {
        "success": True,
        "project_name": project_name,
        "readme_markdown": readme_content,
        "summary": f"สร้างแบบร่าง README.md สำหรับโปรเจกต์ '{project_name}' เรียบร้อยแล้วค่ะ",
    }


@tool_registry.register(
    name="draft_github_issue",
    description="Draft a structured GitHub issue for tracking a bug or feature request.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Issue title (e.g. '[Feature] Add PromptPay QR generation').",
            },
            "body": {
                "type": "string",
                "description": "Detailed description, steps to reproduce, or acceptance criteria.",
            },
            "labels": {
                "type": "string",
                "description": "Comma-separated labels (e.g. 'bug, enhancement, priority:high').",
            },
        },
        "required": ["title", "body"],
    },
)
async def draft_github_issue(
    title: str,
    body: str,
    labels: Optional[str] = "enhancement",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Prepares a validated issue draft with security scan."""
    # Security scan: check for potential secrets in issue body
    forbidden_terms = ["password", "secret_key", "api_key", "token="]
    if any(term in body.lower() for term in forbidden_terms):
        return {
            "success": False,
            "error": "ตรวจพบข้อความที่มีความเสี่ยงเป็นรหัสผ่านหรือ API Key ขอความกรุณาตัดข้อมูลสำคัญออกก่อนสร้าง Issue ค่ะ",
        }

    label_list = [l.strip() for l in labels.split(",")] if labels else []
    return {
        "success": True,
        "issue_draft": {
            "title": title,
            "body": body,
            "labels": label_list,
        },
        "summary": f"เตรียมแบบร่าง GitHub Issue: '{title}' เรียบร้อยแล้วค่ะ (พร้อมส่งตรวจทาน)",
    }

