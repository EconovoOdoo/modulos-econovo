# Econovo - Stock Delivery Slip Signature

## Overview

`stock.action_report_delivery` is overridden by `base_advanced_report_templates`
to render one of several themed templates instead of the native Odoo delivery
slip. Only "Traditional" and "Standard" happened to show the signature image,
and none of the themes showed who signed. This module fixes that across all
of them, without touching the vendored modules directly.

## Features

- Adds the missing signature block to "Modern", "Attractive" (`base_advanced_report_templates`)
  and "Preimpreso" (`gg_lot_data`)
- Adds `signed_by` (falling back to the customer's name) next to the
  signature image on all 5 themes

## Requirements

- Module `base_advanced_report_templates`
- Module `gg_lot_data`
- Module `econovo_remito_digital` (provides `signed_by` on `stock.picking`)

## Notes

- The "Preimpreso" theme is an absolute-positioned overlay meant for
  pre-printed paper. The signature block's `top`/`left` coordinates are a
  best-effort placement and may need adjusting to match the actual
  pre-printed paper's signature line.
