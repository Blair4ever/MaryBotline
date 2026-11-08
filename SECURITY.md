# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| < 0.3.0 | :x:                |

---

## Reporting a Vulnerability

The MARY team takes security seriously. If you discover a security vulnerability, please **do not** open a public issue or discuss it in public chat channels.

### Reporting Procedure
1. Send a private report to the repository maintainer via email or via GitHub Private Vulnerability Reporting at:
   `https://github.com/Blair4ever/MaryBotline/security/advisories/new`
2. Please include:
   - Description of the vulnerability.
   - Proof-of-concept (PoC) code or reproduction steps.
   - Impact assessment (e.g., privilege escalation, cross-tenant data leakage, signature bypass).
3. You will receive an initial response within 48 hours acknowledging receipt.
4. Once a fix is verified, a patch will be released and credit will be acknowledged in the security advisories.

---

## Core Security Controls

For comprehensive details on MARY's threat model, HMAC-SHA256 signature verification, idempotency tracking, and multi-tenant isolation, refer to [docs/SECURITY.md](docs/SECURITY.md).

