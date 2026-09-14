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
