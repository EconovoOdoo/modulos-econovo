# Econovo Login Audit Compatibility

## Overview

This addon adapts Code Sparks' `cs_login_audit_log` module to Odoo 17
non-interactive credential checks.

## Behavior

- Preserves the full `res.users` credential-validation chain and tolerates only
  the known unbound-request RuntimeError from the Code Sparks audit hook during
  non-interactive checks.
- Records successful logins through `/web/login` and
  `/web/session/authenticate`, where HTTP request metadata is available.
- Avoids duplicate rows when the original addon already logged the same user
  and HTTP session.
- Does not create audit rows for ordinary authenticated model RPC calls.
- Uses the request's resolved remote address; forwarded addresses should only
  be trusted when Odoo proxy mode is configured for a trusted reverse proxy.

## Dependencies

- `cs_login_audit_log`
- `web`
- Python package `user-agents`, already required by `cs_login_audit_log`

## Migration

This is an Odoo 17 compatibility addon. When migrating to a version where the
upstream addon no longer has the request-context defect, review the new version's
credential and controller hooks, then remove this addon or adapt it before
upgrading.