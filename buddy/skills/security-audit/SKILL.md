---
description: "Use when the task involves security — hardening endpoints, reviewing auth flows, fixing vulnerabilities, or auditing a codebase for security issues."
---

# Security Audit

When working on security, be systematic. Don't just fix the reported issue — scan for the same pattern everywhere.

## How to Audit

1. **Map the attack surface.** Find all entry points: API routes, form handlers, webhooks, CLI args, file uploads. Use `grep` for route decorators (`@app.get`, `router.post`, `app.use`, etc.)
2. **Check each entry point** against the threat list below.
3. **Fix in order of severity.** Exploitable > data leak > hardening.
4. **Verify each fix.** Write a test or manually confirm the vulnerability is closed.

## Threat Checklist

**Injection** — Does any user input reach a query, command, or template without sanitization?
- SQL: parameterized queries only, never string interpolation
- Command: no `subprocess.run(user_input)` or backtick interpolation
- XSS: escape output in templates, use framework defaults
- Path traversal: validate file paths, reject `..`

**Auth & access** — Can unauthenticated users reach protected resources? Can users access other users' data?
- Every mutation endpoint needs auth
- Check authorization, not just authentication (user A can't edit user B's data)
- Tokens: stored securely, rotated, scoped

**Secrets** — Are credentials exposed?
- Grep for hardcoded tokens, passwords, API keys in source
- Check `.env` files aren't committed (verify `.gitignore`)
- Check error responses and logs don't leak secrets

**Config** — Are defaults safe?
- CORS: explicit origins, not `*`
- Debug mode off in production
- Rate limiting on auth endpoints
- HTTPS enforced where applicable

## When You Fix Something

- Commit the fix with a message explaining the vulnerability and how the fix closes it
- If there's a test suite, add a test that proves the vulnerability is closed
- If you find the same pattern in multiple places, fix all of them
