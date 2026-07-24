# Econovo MRP Component Lines

Adds a **Manufacturing > Operations > Manufacturing Order Lines** menu entry
that lists the component (raw material) lines of every Manufacturing Order
(`mrp.production`) in a single flat, filterable and groupable list, instead
of having to open each Manufacturing Order individually to inspect its
"Components" tab.

## Why

`mrp.production` only exposes its components through the `move_raw_ids`
one2many field on the order's own form view. There is no native Odoo view
that lists those `stock.move` lines (one row per component per order) across
several Manufacturing Orders at once. This module adds that missing list
view, reusing the existing `stock.move` model and its
`raw_material_production_id` field (set on every component move).

## Features

* Flat list of `stock.move` records where `raw_material_production_id` is set
* Columns: Manufacturing Order, Production Plan, Scheduled Date, Component,
  From/To Location, Quantity To Consume, Consumed Quantity, UoM, Done,
  Status, Operation, Work Order, Source Document
* Column totals (sum) on "To Consume" and "Consumed"
* Quick filters: To Consume, Consumed, Done, Cancelled
* Group By: Manufacturing Order, Production Plan, Component, Status,
  Operation, Source Location
* Read-only (`create`/`edit`/`delete` disabled): use the Manufacturing Order
  itself to register consumption; this view is for consultation/reporting
  only

## Technical Notes

* No new security rules: it reuses `stock.move` and the access rights
  already granted by the `mrp`/`stock` modules to Manufacturing users.
* Adds one small related field, `stock.move.production_plan_id`
  (`related='raw_material_production_id.plan_id', store=True`), to expose
  the `mrp.plan` ("Plan de Producción") added by `gg_automatic_mrp_schedule`
  as a column/group-by without duplicating that module's logic.
* Depends on `mrp` and `gg_automatic_mrp_schedule` (the latter only for the
  `mrp.production.plan_id` field used above).
