"""Final project health check script."""
import sqlite3
import json
import sys
import os

MARY_DB = "mary.db"
QWEN_MODEL = "Qwen3.5-9B-The-Defiant-Fable-Uncnr-Heretic-NEO-MAX-MTP-IQ3_M.gguf"
GEMINI_MODEL = "gemini"

errors = []
warnings = []

print("=" * 60)
print("  MARY Botline Final Health Check")
print("=" * 60)

# 1. Check DB connection and tables
print("\n[1] Database structure")
try:
    conn = sqlite3.connect(MARY_DB)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"  Tables: {tables}")
    # Schema stores settings inside groups.settings_json (not a separate table)
    expected = {"groups", "members", "messages", "memories"}
    missing = expected - set(tables)
    if missing:
        errors.append(f"Missing DB tables: {missing}")
    else:
        print("  ✅ All expected tables exist")
except Exception as e:
    errors.append(f"DB connection error: {e}")
    conn = None

# 2. Check group settings
print("\n[2] Group settings (Qwen defaults)")
if conn:
    try:
        # Settings are embedded inside groups.settings_json (not a separate table)
        cur.execute("SELECT id, settings_json FROM groups")
        rows = cur.fetchall()
        print(f"  Total groups: {len(rows)}")
        for gid, sj in rows:
            s = json.loads(sj) if sj else {}
            dm = s.get("default_model", "")
            cm = s.get("general_conversation_model", "")
            tm = s.get("tool_execution_model", "")
            sm = s.get("summarization_model", "")
            ok_conv = QWEN_MODEL[:10] in (dm or "") or QWEN_MODEL[:10] in (cm or "")
            ok_tool = GEMINI_MODEL in (tm or "")
            ok_summ = QWEN_MODEL[:10] in (sm or "")
            status = "✅" if ok_conv else "⚠️ "
            print(f"  {status} {gid[:12]}..  conv_ok={ok_conv}  tool_ok={ok_tool}  summ_ok={ok_summ}")
            if not ok_conv:
                warnings.append(f"Group {gid[:12]} does not have Qwen as conv model")
    except Exception as e:
        errors.append(f"Group settings query error: {e}")

# 3. Check .env exists but is NOT tracked
print("\n[3] Environment & secrets safety")
if os.path.exists(".env"):
    print("  ✅ .env file exists locally")
else:
    warnings.append(".env file not found locally - set env vars before running")

if os.path.exists(".gitignore"):
    with open(".gitignore") as f:
        gi = f.read()
    checks = [".env", "*.db", "*.key", "*.pem", "*.secret"]
    for item in checks:
        if item in gi:
            print(f"  ✅ .gitignore covers {item}")
        else:
            errors.append(f".gitignore missing entry: {item}")
else:
    errors.append(".gitignore not found")

# 4. Check no hardcoded secrets in py files
print("\n[4] Scanning Python files for hardcoded secrets")
import re
SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI API Key"),
    (r"ghp_[A-Za-z0-9]{30,}", "GitHub Token"),
    (r"['\"]U[0-9a-f]{31}['\"]", "LINE User ID literal"),
    (r"channel_secret\s*=\s*['\"][A-Za-z0-9]{16,}['\"]", "LINE Channel Secret"),
]
found_secrets = []
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in {".venv", ".git", "__pycache__", ".pytest_cache"}]
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            for pattern, label in SECRET_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    found_secrets.append(f"{path}: {label}")
        except Exception:
            pass
if found_secrets:
    for s in found_secrets:
        errors.append(f"Potential secret: {s}")
else:
    print("  ✅ No hardcoded secrets detected")

# 5. Check key files exist
print("\n[5] Key project files")
required_files = [
    "app/main.py",
    "app/config.py",
    "app/api/router.py",
    "app/database/session.py",
    "app/schemas/group_settings.py",
    "app/services/llm/router.py",
    "app/services/llm/commands.py",
    "app/services/llm/registry.py",
    "Dockerfile",
    "render.yaml",
    "requirements.txt",
    ".env.example",
    "README.md",
]
for rf in required_files:
    if os.path.exists(rf):
        print(f"  ✅ {rf}")
    else:
        errors.append(f"Missing file: {rf}")

# 6. Summary
print("\n" + "=" * 60)
print("  SUMMARY")
print("=" * 60)
if errors:
    print(f"\n❌ ERRORS ({len(errors)}):")
    for e in errors:
        print(f"   - {e}")
if warnings:
    print(f"\n⚠️  WARNINGS ({len(warnings)}):")
    for w in warnings:
        print(f"   - {w}")
if not errors and not warnings:
    print("\n🎉 ALL CHECKS PASSED! Project is clean and ready.")
elif not errors:
    print("\n✅ No errors — only minor warnings above.")
else:
    print("\n❌ Fix errors above before deploying.")

if conn:
    conn.close()

sys.exit(1 if errors else 0)
