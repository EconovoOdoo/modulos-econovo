# Stock Picking Production Info

Adds the Production Plan and Workcenter of a transfer to the native
`stock.picking` form and list views.

## Problem

`stock.picking` has no native way to know which Manufacturing Order's
Production Plan a transfer supplies components for: the only related data
lives on `stock.move` (`production_plan_id`, added by
`econovo_mrp_component_lines`), and it isn't linked directly on a "Choose
Components" transfer's own move - only on the actual MO consumption move
further down the destination chain.

Workcenter information was previously only available through a Studio field
(`x_studio_workcenter_id`), which cannot be referenced safely from a real
module (a view referencing a field that doesn't exist yet fails to install).

## Solution

* `production_plan_id` (computed, stored): aggregated from the transfer's
  moves, following the destination chain via `_get_supply_production()`.
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

* `econovo_mrp_component_lines` (provides `_get_supply_production`)
