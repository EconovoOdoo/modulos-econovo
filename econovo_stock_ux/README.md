# Econovo Stock UX Compatibility Patch

## Purpose

This module backports `stock_ux` quantity-constraint behavior from newer
`ingadhoc/stock` branches to Odoo 17 environments.

It is intentionally isolated in an `econovo_*` addon so that:

- `stock_ux` upstream code remains untouched.
- upgrades are safer and simpler.
- this addon can be uninstalled when the target Odoo version already includes
  equivalent upstream logic.

## What is patched

The module extends `stock_ux` and adapts two validation paths:

- `stock.move._check_quantity`
- `stock.move.line._check_manual_lines`

Behavior aligned with newer upstream branches:

- for scheduler/superuser automatic operations, invalid quantity updates are
  reverted and logged in picking chatter instead of crashing with
  `ValidationError`.
- manual user operations still raise `ValidationError`.
- stock availability check follows newer branch logic (`is_storable`,
  `picking_ids` context filtering).

## Upstream reference

Based on upstream evolution in `ingadhoc/stock` for `stock_ux`, including the
fix line introduced to prevent cron/scheduler failures:

- commit `40ae1e2d` (`[FIX]stock_ux: fix when cron active constrain`)
- subsequent improvements in 18.0/19.0 branches.

## Installation order

1. Ensure `stock_ux` is installed.
2. Install `econovo_stock_ux`.

## Uninstall strategy on future upgrade

When upgrading to a version where upstream `stock_ux` already provides the same
behavior:

1. Verify the target branch includes equivalent logic.
2. Uninstall `econovo_stock_ux`.
3. Keep `stock_ux` only.

This keeps Econovo-specific technical debt temporary and migration-friendly.
