# PCP - Planeamiento y Control de Produccion

Odoo 17 module extending `mrp.plan` (provided by `gg_automatic_mrp_schedule`) with a
priority/manufacturing-reason catalog, target dates and multi-company support, plus a native
production progress dashboard grouped by Production Plan and by process/operation.

## Overview

Ports the "Control de Avances de Produccion" React/Firebase application into a native Odoo app,
reusing native Odoo mechanisms wherever possible (see
`docs/control-de-avances-de-producción/PLAN_MIGRACION_MODULO_ODOO_PCP.md` in this repository for
the full field/model/UI mapping this module implements).

## Features

* `pcp.priority` / `pcp.reason`: editable catalogs (same pattern as `crm.lost.reason`), seeded
  with A1/B1/C1 priorities and 3 default manufacturing reasons.
* `mrp.plan` extended with `priority_id`, `date_start`, `date_end`, `company_id` and native
  `active` archiving.
* `mrp.production.reason_id`: manufacturing reason set per Manufacturing Order.
* `mrp.production`/`mrp.workorder` inherit the Plan's priority via a stored related field.
* Dashboard (Apps > PCP > Dashboard): production progress grouped by Plan x Process, with inline
  priority edit and archive/unarchive for the Manager group.
* Operators (`PCP / User` group) only see workorders whose workcenter's "Allowed Employees"
  (`mrp.workcenter.employee_ids`) list is empty or includes one of their own linked employees.
* XLSX export (`report_xlsx`), available from the Print menu on Production Plans.

## Requirements

* `mrp`
* `mrp_workorder` (Enterprise - Shop Floor, provides `mrp.workcenter.employee_ids`)
* `gg_automatic_mrp_schedule` (provides `mrp.plan`)
* `report_xlsx`

## Configuration

* Assign users to the `PCP / User` or `PCP / Manager` group (Settings > Users & Companies >
  Users).
* Configure `mrp.workcenter.employee_ids` ("Allowed Employees") on any workcenter that should be
  restricted to specific operators; leave it empty to keep a workcenter visible to every PCP user.
* Manage Priorities and Manufacturing Reasons under PCP > Configuration.

## Known limitations

* `static/description/icon.png` ships as a placeholder; replace it with the final app icon.
* `i18n/es_AR.po` ships as an empty skeleton; complete it with the translation exported from
  Odoo (Settings > Translations > Export Translation) once the module is installed.
* The base `mrp.plan` access rule (from `gg_automatic_mrp_schedule`) already grants full
  read/write/create/unlink to every internal user; this module does not tighten it, so priority/
  date edits are only prevented at the UI level for non-Manager users, not at the ORM level.
