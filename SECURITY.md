# Security Policy

## Supported Versions
| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅ |
| < 1.0   | ❌ |

## Reporting a Vulnerability

Report security vulnerabilities by opening an issue at:
https://github.com/hichemuuus/Veyron/issues

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

Vulnerabilities are addressed on a best-effort basis. For critical issues, expect a response within 48 hours.

## Security Architecture

Veyron implements defense-in-depth:

1. **Path Policy** — All file operations are restricted to a sandbox root directory. Path traversal attempts are detected and blocked.
2. **Command Policy** — Shell commands are classified as FREE, CONFIRM, or RESTRICTED based on risk. Dangerous commands require user confirmation.
3. **Safety Policy** — Task requests are analyzed for risk level before execution.
4. **Audit Log** — All security events are logged to an append-only JSONL file.
5. **Confirmation Flow** — High-risk operations require user approval via WebSocket gating.
6. **Tool Permissions** — Each tool has a permission level (FREE/CONFIRM/RESTRICTED).

## Best Practices

- Run Ollama locally for complete data privacy
- Review config.yaml security settings before deployment
- Keep Veyron updated to the latest version
- Do not disable security policies for convenience
