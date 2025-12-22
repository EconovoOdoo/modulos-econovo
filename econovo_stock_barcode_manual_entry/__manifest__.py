# -*- coding: utf-8 -*-
# Copyright 2024 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': "Stock Barcode Manual Entry",
    'summary': "Adds manual barcode entry button to the barcode main menu",
    'description': """
Stock Barcode Manual Entry
==========================

This module adds a button to the Stock Barcode main menu that allows users
to manually enter a barcode without requiring a physical scanner or camera.

Features:
---------
* Manual barcode entry button on the main menu screen
* Reuses the existing ManualBarcodeScanner dialog from stock_barcode
* Low coupling with the original module for easy migration
* Non-invasive implementation using OWL patches and template inheritance

Usage:
------
1. Go to Barcode app
2. Click the "Manual Entry" button (keyboard icon)
3. Type the barcode and press Apply

This module is designed to be lightweight and easily maintainable across
Odoo version upgrades.
    """,
    'author': "Jose D. Leonett",
    'website': 'https://github.com/josedleonett',
    'category': 'Inventory/Inventory',
    'version': '17.0.1.0.0',
    'license': 'AGPL-3',
    'depends': ['stock_barcode'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'econovo_stock_barcode_manual_entry/static/src/**/*.js',
            'econovo_stock_barcode_manual_entry/static/src/**/*.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
