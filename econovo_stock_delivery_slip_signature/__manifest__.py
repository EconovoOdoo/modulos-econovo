# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': "Stock Delivery Slip Signature",
    'summary': "Show the registered signature on every delivery slip theme",
    'description': """
Stock Delivery Slip Signature
==============================

stock.action_report_delivery is overridden (by base_advanced_report_templates)
to render one of several themed templates (Traditional, Standard, Modern,
Attractive, and Preimpreso from gg_lot_data) instead of the native Odoo
delivery slip. Only Traditional and Standard happened to show the signature
image, and none of them showed who signed (signed_by).

This module adds the missing signature block to Modern, Attractive and
Preimpreso, and adds signed_by (falling back to the customer's name) next to
the signature image on all 5 themes, using non-invasive template inheritance
so the vendored modules stay untouched.

Requirements:
-------------
* Module `base_advanced_report_templates`
* Module `gg_lot_data` (Preimpreso theme)
* Module `econovo_remito_digital` (provides the signed_by field)
    """,
    'author': "Jose D. Leonett",
    'website': 'https://github.com/josedleonett',
    'category': 'Inventory/Inventory',
    'version': '17.0.1.0.0',
    'license': 'AGPL-3',
    'depends': [
        'base_advanced_report_templates',
        'gg_lot_data',
        'econovo_remito_digital',
    ],
    'data': [
        'views/report_stock_signature_inherit.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
