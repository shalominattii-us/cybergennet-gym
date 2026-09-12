# Security Policy — CyberGenetic Gym

## Default Deny

The Gym operates on a **default deny** security model. No athlete has access
to anything unless explicitly granted through the credential system.

## Constitutional Separation

The **Constitutional Genome** is immutable. The genetic engine operates
exclusively on the **Adaptive Genome** (trait manifest). Any attempt to
mutate constitutional fields is a security event and is logged.

## Credential Model

- Credential ≠ trust
- Authentication ≠ authorization
- Authorization ≠ correctness
- Every credential is scoped and revocable

## Network

Default deny. Athletes have no network access unless explicitly granted
through a specialized credential.

## Secrets

No secrets are exposed to athletes. All secrets live in the system layer
and are never passed to athlete workspaces.

## Audit

Every state-changing action produces an audit event with:
- event_id, timestamp, actor, subject, action, result
- policy_version, environment_hash, provenance_hash

## Reporting

Report security vulnerabilities to the project maintainers.
