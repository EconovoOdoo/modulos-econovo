# Stock Picking Validated By

Tracks which user validated a transfer, automatically.

## Problem

`stock.picking` has no native way to know which user validated a transfer -
only the current responsible (`user_id`, which can be reassigned or left
empty) and `date_done` (when it happened, but not who did it). This makes
internal audit control of who actually processed a transfer harder than it
should be.

## Solution

This module adds a **Validated By** field (`validation_user_id`, a
`res.users` many2one, `readonly`, `copy=False`) that is stamped with the
active session user automatically the moment a transfer is set to done via
the "Validate" button, by overriding `_action_done()` - the exact method
`button_validate()` calls right when a transfer becomes `done` (alongside
the native `date_done`). This also covers batch validation, since
`stock.picking.batch.action_done()` funnels into the same
`button_validate()`/`_action_done()` flow, and multi-picking validation
from the list view.

The field is never editable by hand (`readonly=True`) and is not copied
when a transfer is duplicated or when a backorder is created
(`copy=False`) - it only ever reflects who actually performed the
validation.

The field is shown:

* On the transfer form view, right after "Effective Date" (`date_done`)
* On the transfers list view, as an optional (hideable) column
* On the transfers search view, as a directly searchable field and as a
  "Group By" option
* On the "Moves" and "Moves History" report list views (`stock.move` and
  `stock.move.line`), as an optional (hideable) column. `stock.move` is
  stamped independently by overriding its own `_action_done()` - this
  also covers moves that never belong to any transfer at all (inventory
  adjustments, quant relocations), which `button_validate()`/
  `stock.picking._action_done()` never touch. `stock.move.line` simply
  follows its move's value (`related='move_id.validation_user_id'`).

## Historical data

A migration script (`migrations/17.0.1.0.1/post-migrate.py`) backfills
`validation_user_id` on pre-existing `done` records so past data is not
left empty:

* Transfers: looked up from the `state` field's tracking history
  (`mail.tracking.value`) - the author of the most recent "state changed"
  message on the transfer.
* Moves/move lines that already belong to a transfer: copied down from
  that transfer's (possibly just-backfilled) value.
* Moves/move lines with no transfer at all (inventory adjustments, quant
  relocations): taken from `create_uid`, since those flows create and
  complete the move in the same call - the creating user is the one who
  performed the action.
