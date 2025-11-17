# -*- coding: utf-8 -*-
{
    'name': 'Econovo Location Labels',
    'version': '17.0.1.0.0',
    'summary': 'Print location barcode labels in DYMO 100x50mm and 100x70mm formats',
    'description': """
Econovo Location Labels
========================

Print individual location barcode labels using DYMO label formats.

Features:
---------
* Print location labels from location form view
* Batch printing via wizard for multiple locations
* Two label sizes: 100x50mm (compact) and 100x70mm (detailed)
* Clean minimalist layout with company logo
* Displays: warehouse, location name, barcode, complete path
* Compatible with DYMO label printers
* Auto-detect barcode symbology

Technical:
----------
* Extends stock.location model
* Inherits product.label.layout wizard pattern
* Custom QWeb templates for each format
* Responsive SCSS styling
* Paperformat definitions for precise printing

Author: Jose D. Leonett
License: AGPL-3
    """,
    'category': 'Inventory/Inventory',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/location_labels_wizard_views.xml',
        'views/stock_location_views.xml',
        'views/templates_100x50.xml',
        'views/templates_100x70.xml',
        'reports/location_label_report_100x50.xml',
        'reports/location_label_report_100x70.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            '/econovo_location_labels/static/src/scss/location_fonts.scss',
            '/econovo_location_labels/static/src/scss/location_label_report_100x50.scss',
            '/econovo_location_labels/static/src/scss/location_label_report_100x70.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
