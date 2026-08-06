# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': "Stock Picking Batch Scheduled Date",
    'summary': "Set a scheduled date when creating a batch from the Add to batch wizard",
    'description': """
Stock Picking Batch Scheduled Date
===================================

The native "Add to batch" wizard (``stock.picking.to.batch``, opened from the
Transfers list action) lets the user pick a Responsible and whether the new
batch starts as Draft, but has no way to set a Scheduled Date: the batch is
left to whatever its native compute derives (the earliest scheduled date
among its transfers).

This module adds a Scheduled Date field to the wizard, shown only when
creating a NEW batch transfer.

Features:
---------
* Optional "Scheduled Date" field on the wizard, next to Responsible
* Left empty, behavior is unchanged (native compute applies)
* When filled in, it is applied to the new batch AND to every transfer being
  added to it, mirroring the batch form's own ``onchange_scheduled_date``
  behavior when the field is edited manually there

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
        'wizard/stock_picking_to_batch_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
