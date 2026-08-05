# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': "Stock Picking Batch Backorder",
    'summary': "Group the backorders of a validated batch into a new batch transfer",
    'description': """
Stock Picking Batch Backorder
=============================

When a batch transfer is validated with partial quantities, Odoo creates one
backorder per transfer and leaves them outside of any batch: the operator has
to rebuild the working set by hand.

This module adds an option on the "Create Backorder?" wizard (enabled by
default) to group all the generated backorders into a new batch transfer,
one per origin batch.

Features:
---------
* "Create a new batch with the backorders" checkbox on the backorder wizard,
  only shown when at least one of the transfers belongs to a batch
* Default value and status of the new batch configurable per operation type
* The new batch inherits the responsible, the company and the wave flag of
  the origin batch
* Traceability: `origin_batch_id` field, smart button on the origin batch and
  a message in its chatter
* Takes precedence over the Automatic Batches feature: because the batch is
  assigned while the backorders are created, `_find_auto_batch` is a no-op
  for them and no core method needs to be patched

Requirements:
-------------
* Module `stock_picking_batch` (core)
    """,
    'author': "Jose D. Leonett",
    'website': 'https://github.com/josedleonett',
    'category': 'Inventory/Inventory',
    'version': '17.0.1.0.0',
    'license': 'AGPL-3',
    'depends': [
        'stock_picking_batch',
    ],
    'data': [
        'views/stock_picking_type_views.xml',
        'views/stock_picking_batch_views.xml',
        'wizard/stock_backorder_confirmation_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
