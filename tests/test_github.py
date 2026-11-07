import pytest
from app.tools.github.github_tools import generate_project_readme, draft_github_issue


@pytest.mark.asyncio
async def test_generate_project_readme():
    res = await generate_project_readme(
        project_name="AuraProject",
        description="Autonomous AI Agent",
        tech_stack="Python, FastAPI, Postgres",
    )
    assert res["success"] is True
    assert "# AuraProject" in res["readme_markdown"]
    assert "Python, FastAPI, Postgres" in res["readme_markdown"]


@pytest.mark.asyncio
async def test_draft_github_issue_valid():
    res = await draft_github_issue(
        title="Add PromptPay QR",
        body="Implement dynamic PromptPay QR rendering for LINE Flex Message",
        labels="feature, payments",
    )
    assert res["success"] is True
    assert res["issue_draft"]["title"] == "Add PromptPay QR"
    assert "feature" in res["issue_draft"]["labels"]


@pytest.mark.asyncio
async def test_draft_github_issue_security_leak_rejection():
    # Attempting to post text containing API keys/passwords must be rejected
    res = await draft_github_issue(
        title="Config leak",
        body="Here is my secret_key: 12345",
    )
    assert res["success"] is False
    assert "ความเสี่ยง" in res["error"]
