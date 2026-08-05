# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': "Stock Picking Batch Backorder - Barcode",
    'summary': "Offer the backorder batch option in the Barcode app",
    'description': """
Stock Picking Batch Backorder - Barcode
=======================================

Bridge between `econovo_stock_picking_batch_backorder` and the Barcode app.

The barcode client never opens the backend "Create Backorder?" wizard: it
sends `skip_backorder` and displays its own `BackorderDialog` instead. This
module adds the "Create a new batch with the backorders" checkbox to that
dialog and forwards the choice to the server through the validation context.

Features:
---------
* Checkbox on the barcode *Incomplete Transfer* dialog, shown only when the
  record being validated is a batch transfer or a transfer belonging to one
* Default value taken from the operation type (`Batch Backorders`)
* Only proposed when the operation type creates backorders on demand
  (`Create Backorder = Ask`), to stay consistent with the desktop behavior

Requirements:
-------------
* Module `econovo_stock_picking_batch_backorder`
* Module `stock_barcode_picking_batch` (Enterprise)
    """,
    'author': "Jose D. Leonett",
    'website': 'https://github.com/josedleonett',
    'category': 'Inventory/Inventory',
    'version': '17.0.1.0.0',
    'license': 'AGPL-3',
    'depends': [
        'econovo_stock_picking_batch_backorder',
        'stock_barcode_picking_batch',
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'econovo_stock_picking_batch_backorder_barcode/static/src/**/*.js',
            'econovo_stock_picking_batch_backorder_barcode/static/src/**/*.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
