# Contributing to MARY

Thank you for your interest in contributing to MARY! We welcome contributions from developers, researchers, and technical writers of all experience levels.

---

## 1. Code of Conduct

Please treat all contributors and users with respect and professional courtesy. Harassment, derogatory comments, or abusive behavior will not be tolerated.

---

## 2. Getting Started

### 2.1 Fork and Clone
```bash
# Clone your fork
git clone https://github.com/<your-username>/MaryBotline.git
cd MaryBotline
```

### 2.2 Environment Setup
```bash
# Create a virtual environment
python -m venv .venv

# Activate on Windows:
.venv\Scripts\Activate.ps1
# Activate on Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2.3 Verify Setup
Ensure that the test suite passes locally:
```bash
pytest -q
```
You should see all 50 tests pass.

---

## 3. Development Guidelines

### 3.1 Code Style & Standards
- Follow **PEP 8** style guidelines.
- Use explicit type annotations for function signatures.
- Keep business logic decoupled from external transport adapters.
- Use Pydantic models for request/response validation.

### 3.2 Multi-Tenant Scoping Rule
Every new database query, tool function, or context lookup **must** be scoped to `group_id`. Never perform global unconstrained queries against message or memory tables.

### 3.3 Adding a New LLM Adapter or Model
When adding an LLM provider:
1. Register the model capability profile in `app/services/llm/registry.py`.
2. Explicitly specify capabilities (`SUPPORTED`, `UNSUPPORTED`, `UNKNOWN`). Do not assume tool calling is supported unless verified with automated tests.
3. Normalize responses to the standard `LLMResponse` structure.
4. Add mocked unit tests in `tests/` verifying token usage handling, authentication errors, and capability enforcement.

---

## 4. Submitting a Pull Request

1. Create a feature branch:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Commit your changes with clear, descriptive commit messages following the Conventional Commits specification:
   - `feat:` for new capabilities
   - `fix:` for bug fixes
   - `docs:` for documentation updates
   - `test:` for test additions or adjustments
3. Ensure all automated tests pass:
   ```bash
   pytest -v
   ```
4. Push to your fork and submit a Pull Request against the `main` branch.
5. In your PR description, explain the motivation, changes made, and how they were tested.

---

## 5. Reporting Issues

- Use the GitHub Issue Tracker.
- Provide clear steps to reproduce the issue, expected behavior, and relevant logs.
- Never paste sensitive information, private `.env` variables, or real LINE channel access tokens into public issues.
