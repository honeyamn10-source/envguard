# Security Policy

`envguard` helps you stop leaking secrets — please report vulnerabilities
responsibly so we can keep it trustworthy.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Report it
privately, and we will respond within five business days:

- **Preferred:** open a private advisory on GitHub at
  <https://github.com/honeyamn10-source/envguard/security/advisories/new>
- **Alternative:** email the maintainers via the GitHub contact address on your
  profile once you have filed a draft advisory.

In your report, please include:

1. The affected version(s) and environment.
2. A minimal reproduction, including the vulnerable input.
3. The expected and observed behaviour.
4. Any suggested fix, if you have one.

We will confirm receipt, coordinate a fix and a release, and credit you in the
advisory unless you prefer to stay anonymous.

## Scope

The following are in scope:

- Code execution, path traversal or denial of service triggered by a crafted
  input file scanned by `envguard`.
- False-negative behaviour of a detector that could let committed secrets slip
  through.
- Memory/CPU exhaustion from pathological files (malicious `.gitignore`,
  `.envguard-ignore` or `.env` contents).

The following are not considered vulnerabilities:

- Detection gaps that are documented limitations or reasonable tunables
  (`--severity`, `.envguard-ignore`).
- Findings in third-party code used only at build time (the project has no
  runtime dependencies).

## Security hardening

The tool ships with sensible hardcoded defaults:

- Files larger than 1 MB are skipped during scans.
- Findings always mask the matched secret (`AKIA****MPLE`).
- `.envguard-ignore` and gitignore parsing are intentionally feature-minimal
  to avoid glob-evaluation surprises.