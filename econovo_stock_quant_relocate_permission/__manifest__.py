# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Stock Quant Relocate Permission',
    'version': '17.0.1.1.0',
    'summary': 'Allows non-admin users to use the Relocate button on stock.quant.',
    'description': '''
This module creates a special permission group that allows users with 
the "User" role in Inventory to access and use the "Relocate" button in:

- Inventory → Reports → Locations
- Inventory → Operations → Inventory Adjustments
- Products → On Hand Quantity (Update Quantity view)
- Barcode App → Scanned product quants view

Without this module, only Inventory Administrators can use this button.

Features:
- Creates the "Can Relocate Inventory Stock" group
- Grants permissions on the stock.quant.relocate wizard
- Makes the "Relocate" button visible for users in the group
    ''',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'category': 'Inventory/Inventory',
    'depends': [
        'stock',
        'stock_barcode',
    ],
    'data': [
        'security/econovo_stock_quant_relocate_permission_groups.xml',
        'security/ir.model.access.csv',
        'views/stock_quant_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
