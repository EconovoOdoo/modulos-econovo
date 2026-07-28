# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': "Stock Barcode Signature",
    'summary': "Capture a signature from the Barcode app before validating transfers",
    'description': """
Stock Barcode Signature
========================

This module adds a dedicated "Sign" button to the Barcode app top navigation
bar, allowing a signature (customer, warehouse responsible or carrier) to be
captured directly from a Transfer or a Batch Transfer, without leaving the
scanning screen.

Features:
---------
* Dedicated signature icon in the Barcode app top navigation bar
* Signature requirement configurable per Operation Type (Barcode App tab),
  e.g. Delivery Orders, Pick Components, Store Finished Product
* Works for single Transfers and for Batch Transfers
* For a Batch Transfer, the signature is stored on every underlying transfer
  (it represents a single custody handoff, e.g. a carrier picking up several
  orders for different customers, not a proof of delivery per customer)
* Reuses the native web signature dialog (the same one used by
  stock.picking's own "Sign" widget), no new dependency required
* Non-invasive implementation using OWL patches and template inheritance
* The typed signer name is also captured into signed_by (provided by
  econovo_remito_digital / econovo_stock_picking_batch_signature), so it can
  be shown on printed documents alongside the signature image

Usage:
------
1. Go to Inventory > Configuration > Operation Types
2. Open the operation type (e.g. Delivery Orders, Pick Components, Store
   Finished Product) > "Barcode App" tab
3. Enable "Require Signature"
4. In the Barcode app, the sign icon appears in the top navigation bar for
   transfers of that operation type until they are signed
    """,
    'author': "Jose D. Leonett",
    'website': 'https://github.com/josedleonett',
    'category': 'Inventory/Inventory',
    'version': '17.0.1.1.0',
    'license': 'AGPL-3',
    'depends': [
        'stock_barcode',
        'econovo_remito_digital',
        'econovo_stock_picking_batch_signature',
    ],
    'data': [
        'views/stock_picking_type_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'econovo_stock_barcode_signature/static/src/**/*.js',
            'econovo_stock_barcode_signature/static/src/**/*.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
