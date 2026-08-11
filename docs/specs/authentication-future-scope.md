# Authentication: Future Scope

## Current boundary

AirMonitor v2 currently has no public authentication or account contract. The
frontend must not submit or persist email addresses, passwords, access tokens,
refresh tokens, roles, or profile data. The `/login` route is visual and
informational: it explains that personal accounts are not yet available and
links participants to the current device-based application.

## Required backend work before enabling login

A separate approved sprint must define and review:

1. identity and account ownership rules;
2. registration, sign-in, sign-out, session refresh, and recovery contracts;
3. password hashing and credential breach protections;
4. authorization for devices, sessions, measurements, and any shared data;
5. session/token transport, expiry, rotation, revocation, CSRF, and CORS policy;
6. rate limiting, abuse controls, audit events, privacy/retention, and account
   deletion behavior;
7. safe public errors and non-enumerating recovery responses;
8. OpenAPI schemas, threat model, migration plan, tests, deployment secrets,
   observability, and rollback.

## Frontend activation criteria

The login UI may become functional only after the backend contract is approved,
implemented, documented, and verified. Frontend work must then add test-first
credential handling, accessible validation, explicit session expiry, secure
logout, and authorization-aware routing. A local fake JWT, simulated success,
social-login button, or “protected” client-only state is not an acceptable
bridge.

