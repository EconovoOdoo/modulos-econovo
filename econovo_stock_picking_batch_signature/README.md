# Econovo - Stock Picking Batch Signature

## Overview

Adds signature capture to the Batch Transfer (`stock.picking.batch`) desktop
form, which has no signing capability at all natively (unlike
`stock.picking`).

## Features

- "Firmar" widget on the Batch Transfer form header (before and after
  validation, like the native `stock.picking` Sign widget)
- Reuses the `signature_signer` widget from `econovo_remito_digital`, so the
  typed signer name is captured into `signed_by`, not just the image
- Represents a single custody handoff for the whole batch (e.g. a carrier
  picking up several transfers, possibly for different customers) rather
  than a per-customer proof of delivery: signing the batch copies
  `signature` / `signed_by` / `signature_date` onto every `stock.picking` it
  contains
- The Batch Transfer PDF report now shows the registered signature, signer
  name and date

## Requirements

- Module `stock_picking_batch` (core)
- Module `econovo_remito_digital` (provides the `signature_signer` widget)

## Configuration

No additional configuration needed beyond the existing
`stock.group_stock_sign_delivery` group (Inventory Settings > "Require a
signature on your delivery orders"), reused here to gate the widget's
visibility.
