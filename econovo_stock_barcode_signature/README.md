# Econovo - Stock Barcode Signature

## Overview

Adds a dedicated "Sign" button to the Barcode app top navigation bar, so a
signature can be captured directly from a Transfer or a Batch Transfer
without leaving the scanning screen.

## Features

- Dedicated pencil icon in the Barcode app top navigation bar (next to the
  info/scanner/settings icons)
- Signature requirement configurable per Operation Type, from the
  "Barcode App" tab (Inventory > Configuration > Operation Types)
- Works for single Transfers and for Batch Transfers
- For a Batch Transfer, one signature is captured and stored on every
  underlying transfer — it represents a single custody handoff (e.g. a
  carrier picking up several orders, possibly for different customers), not
  a proof of delivery per customer
- Reuses the native web signature dialog, the same one used by
  `stock.picking`'s own "Sign" widget — no extra dependency required
- Non-invasive implementation using OWL patches and template inheritance

## Requirements

- Module `stock_barcode` (Enterprise) must be installed

## Configuration

1. Go to *Inventory > Configuration > Operation Types*
2. Open the desired operation type (e.g. *Delivery Orders*, *Pick
   Components*, *Store Finished Product*) and open the *Barcode App* tab
3. Enable *Require Signature*
4. In the Barcode app, the sign icon appears in the top navigation bar for
   transfers of that operation type until they are signed

## Notes

- *Store Finished Product* and *Pick Components* only exist as separate
  Operation Types when the warehouse's manufacturing route is configured
  with 2 or 3 steps (*Manufacture* setting on the warehouse). Enable the
  signature requirement only on the operation types that actually need it;
  it does not apply to every warehouse or every operation type by default.
- Manufacturing Orders (`mrp.production`) are not covered by this module:
  they are not `stock.picking` records and are not handled by the Barcode
  app's Transfer client action.
