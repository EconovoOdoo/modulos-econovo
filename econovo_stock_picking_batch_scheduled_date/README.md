# Stock Picking Batch Scheduled Date

Adds a Scheduled Date field to the native "Add to batch" wizard
(`stock.picking.to.batch`), so a batch transfer can be given a scheduled date
right when it is created instead of only through the batch form afterwards.

## Problem

The wizard opened from Transfers > Add to batch lets the user pick a
Responsible and whether the new batch starts as Draft, but has no field for
the Scheduled Date: the batch is left to its native compute (the earliest
scheduled date among its transfers).

## Solution

A **Scheduled Date** field is added next to Responsible, shown only when
creating a NEW batch transfer (mode = "a new batch transfer").

* Left empty: unchanged behavior, the native compute applies.
* Filled in: applied to the new batch AND to every transfer being added to
  it, mirroring the batch form's own `onchange_scheduled_date` behavior when
  the field is edited manually there.

## Requirements

* `stock_picking_batch` (core)
