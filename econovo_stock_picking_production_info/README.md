# Stock Picking Production Info

Adds the Production Plan and Workcenter of a transfer to the native
`stock.picking` form and list views.

## Problem

`stock.picking` has no native way to know which Manufacturing Order's
Production Plan a transfer supplies components for. A "Choose Components"
transfer's own move is never linked to its MO directly (no
`raw_material_production_id`, no `move_dest_ids`/`move_orig_ids` chain in
this Econovo install's replenishment-to-workcenter routes) - the only real
link is the procurement group (`group_id`) shared with the MO, exactly like
the existing Studio field `x_studio_group_id_mo_plan_id` this module
replaces.

Workcenter information was previously only available through a Studio field
(`x_studio_workcenter_id`), which cannot be referenced safely from a real
module (a view referencing a field that doesn't exist yet fails to install).

## Solution

* `production_plan_id` (`related='group_id.mrp_production_ids.plan_id'`,
  stored): the MO sharing the transfer's procurement group, mirroring the
  Studio field it replaces - a plain related field, so it stays correct
  automatically (no manual recompute dependencies to maintain).
* `workcenter_id` (`mrp.workcenter`): a proper, module-owned field replacing
  `x_studio_workcenter_id`. On install, its value is copied from the Studio
  field if present (`post_init_hook`), so no data is lost - the Studio field
  can then be safely deleted.

Both fields are shown:

* On the transfer form view, right after "Source Document"
* On the transfers list view (Inventory > Transfers, and a Batch Transfer's
  own "Transfers" tab, which reuses that same list), as optional/hideable
  columns

## Requirements

* `mrp` (provides `mrp.workcenter`)
* `gg_automatic_mrp_schedule` (provides `mrp.plan`)
