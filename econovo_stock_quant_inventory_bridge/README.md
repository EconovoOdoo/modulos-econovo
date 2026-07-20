# Stock Quant / Inventory Adjustment Bridge

## Description

This module bridges the classic Odoo "Physical Inventory" quant list
(`stock.quant`) with the "Inventory Adjustment Group" (`stock.inventory`)
workflow added by the OCA `stock_inventory` module.

## Problem it solves

Installing `stock_inventory` replaces the direct access to the classic
"Physical Inventory" menu with its own "Inventory Adjustments" (grouped)
menu, by archiving the core menu item. It also has no built-in way to take
specific quants selected in the classic list view and organize them into an
Inventory Adjustment Group.

## Solution

1. **Menu coexistence**: keeps the core "Physical Inventory" menu
   (`stock.menu_action_inventory_tree`) active alongside the OCA
   "Inventory Adjustments" menu, one below the other under
   *Inventory > Operations > Adjustments*. Implemented with a
   `_register_hook()` on `ir.ui.menu` so it self-heals on every server
   restart or module update, even if `stock_inventory` is upgraded on its
   own.
2. **Quant to Inventory Adjustment Group bridge**: extends the
   "Request a Count" wizard (`stock.action_stock_request_count`, available
   from the classic quant list view) with an optional
   "Inventory Adjustment Group" section, letting the selected quants be:
   - Left untouched (default, same behavior as stock core).
   - Grouped into a **new** Inventory Adjustment Group (created in Draft).
   - Assigned to an **existing** Inventory Adjustment Group (Draft or
     In Progress), without changing that group's current state.

## Edge cases handled

- Quants spanning more than one company are rejected with a clear error
  (an Inventory Adjustment Group belongs to a single company).
- Quants in non-internal locations (transit/virtual) are skipped, with a
  notification of how many were skipped.
- Assigning to an existing group already using a different selection
  criteria (e.g. Product Category) is blocked to avoid silently overriding
  it, unless that group has no criteria configured yet.
- Assigning to an **In Progress** group replicates the same "quant already
  being counted elsewhere" conflict check used by
  `action_state_to_in_progress`.
- Assigning to an **In Progress** group updates the live quant bookkeeping
  (`to_do`, `user_id`, `inventory_date`, `current_inventory_id`) so the
  quants immediately show up as pending in that group's count screen.
- Every assignment is logged in the Inventory Adjustment Group's chatter.

## Installation

1. Copy the module to the addons folder.
2. Update the application list.
3. Install "Stock Quant / Inventory Adjustment Bridge" (requires
   `stock_inventory` to be installed).
