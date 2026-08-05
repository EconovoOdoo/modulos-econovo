# Stock Picking Batch Backorder - Barcode

Bridge between `econovo_stock_picking_batch_backorder` and the Barcode app
(Enterprise).

## Why a bridge module

The barcode client never opens the backend "Create Backorder?" wizard: it sends
`skip_backorder: true` in the validation context and displays its own OWL
`BackorderDialog` ("Incomplete Transfer") instead. The checkbox added by the
base module to the backend wizard is therefore never shown in the app.

## What it does

* Adds the **Create a new batch with the backorders** checkbox to the barcode
  `BackorderDialog`, through template inheritance and an OWL patch.
* Forwards the choice to the server in the validation context
  (`econovo_create_backorder_batch`), read right before the validation request
  because the dialog is already closed at that point.
* Exposes `create_backorder_batch` to the client through
  `stock.picking.type._get_barcode_config()`.
* Adds `batch_id` to `stock.picking._get_fields_stock_barcode()` so the option
  is also proposed when validating a single transfer belonging to a batch.

## Conditions

The checkbox is only displayed when:

* the operation type creates backorders on demand (`Create Backorder = Ask`), and
* the record being validated is a batch transfer, or a transfer that belongs to
  a batch.

## Requirements

* `econovo_stock_picking_batch_backorder`
* `stock_barcode_picking_batch` (Enterprise)
