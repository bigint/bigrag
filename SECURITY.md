# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | Yes                |

## Reporting a Vulnerability

If you discover a security vulnerability in bigRAG, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email **security@bigrag.io** with:

- A description of the vulnerability
- Steps to reproduce the issue
- The potential impact
- Any suggested fixes (if applicable)

## Response Timeline

- **Acknowledgment**: Within 48 hours of your report
- **Initial assessment**: Within 5 business days
- **Fix and disclosure**: We aim to release a patch within 30 days of confirmed vulnerabilities

## Disclosure Policy

- We will coordinate with you on a disclosure timeline
- We will credit reporters in the security advisory (unless you prefer anonymity)
- We ask that you do not publicly disclose the vulnerability until a fix is available

## Scope

The following are in scope:

- The bigRAG API server and all Python packages in this repository
- Official Docker images
- Official client SDKs (Python, TypeScript)

The following are out of scope:

- Third-party dependencies (report to the upstream project)
- Self-hosted deployments with misconfigured infrastructure
- Denial of service via expected resource exhaustion (e.g., uploading very large documents)

## Security Best Practices

When deploying bigRAG in production:

- Run behind a reverse proxy (nginx, Caddy) with TLS termination
- Use network-level access controls to restrict who can reach the API
- Enable authentication if exposed to untrusted networks
- Keep bigRAG updated to the latest version
- Monitor logs for unusual access patterns
