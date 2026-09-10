# Automation Webhook - Form-Encoded Payload Support

## Overview

Extends the "On Webhook" trigger of Automation Rules (`base.automation`) so
it also understands a classic `application/x-www-form-urlencoded` request
body, not only JSON.

## Problem it solves

Odoo's own webhook endpoint (`/web/hook/<uuid>`, defined in `base_automation`)
only tries to parse the request body as JSON
(`json.loads(request.httprequest.get_data(as_text=True))`); if that raises
`ValueError` it falls back to the URL query string only
(`request.httprequest.args`), **never** to a POSTed form body
(`request.httprequest.form`). Many no-code website form builders do not send
JSON at all - for example Elementor Pro's native "Webhook" form action POSTs
a plain `application/x-www-form-urlencoded` body with PHP-style bracket keys
(`fields[email][value]=...`). Against that endpoint, every single call
results in an empty payload (`{}`): the automation rule still fires and
still returns HTTP 200 to the caller (so the external tool sees "success"),
but `record_getter` never has any real data to work with, so it silently
does nothing useful. There is no error surfaced anywhere except the
automation's own "Webhook Logs", so this can go unnoticed for a long time.

Confirmed for `crm.lead` automation id 55 ("Crear Leads desde formulario web
WP Econovo Agrovial", production): its Webhook Log showed
`payload {}` for a real form submission, while an independent capture of the
same request via webhook.site showed the actual body was
`application/x-www-form-urlencoded` (e.g.
`fields%5Bemail%5D%5Bvalue%5D=...`).

## Why this module must be installed

Without it, **any** `on_webhook` Automation Rule fed by a non-Odoo, non-JSON
source (Elementor, most WordPress form plugins, many other no-code tools)
is effectively dead code: it will never see the submitted data, no matter
how `record_getter` is written. This is not fixable by changing
`record_getter` alone - the payload is already empty by the time
`record_getter` runs. Uninstalling this module (or never installing it)
silently regresses every such automation back to receiving `{}` on every
call, with the external tool still reporting a successful submission.

## Features

- Overrides `/web/hook/<uuid>` (`base_automation`'s controller) to fall back
  to the parsed form body when the request isn't valid JSON and the query
  string is empty.
- No changes to the rest of the "On Webhook" mechanism: `record_getter`,
  linked server actions and Webhook Logs all keep working exactly as before.
- A form-encoded body with bracket-notation keys (e.g. Elementor Pro) is
  **not** unflattened into nested dicts - `record_getter` must read the
  flat key as-is, for example:
  ```python
  payload.get('fields[email][value]')
  ```

## Requirements

- `base_automation` (core, always installed alongside `base`).

## Configuration

Nothing to configure - installing the module is enough for every existing
and future `on_webhook` Automation Rule to gain the form-encoded fallback.

## How to verify it is working

1. Open the Automation Rule (Settings > Technical > Automation Rules) and
   make sure "Log Calls" is enabled.
2. Trigger a real call to its webhook URL from the external tool.
3. Open the rule's "Webhook Logs" smart button/action: the logged payload
   should now contain the real submitted fields instead of `{}`.
