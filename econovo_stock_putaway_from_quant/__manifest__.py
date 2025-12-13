{
    'name': 'Stock Putaway from Quant',
    'version': '17.0.1.0.1',
    'category': 'Inventory/Inventory',
    'summary': 'Create putaway rules directly from stock quant view',
    'description': """
Stock Putaway from Quant
========================

This module allows users to create putaway (storage) rules directly from the
stock quant list view.

Features:
---------
* Single quant: Opens a wizard showing existing rules and allows creating new ones
* Multiple quants: Bulk creation of putaway rules with conflict resolution
* Independent security group for permission control
* Preview of existing rules before creating new ones

Usage:
------
1. Go to Inventory > Products > Locations (stock.quant view)
2. Select one or more quants
3. Click on "Create Putaway Rule" button
4. Configure the destination location and confirm

The module creates putaway rules that will automatically suggest the configured
location when receiving products in the warehouse.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['stock'],
    'data': [
        'security/econovo_stock_putaway_from_quant_groups.xml',
        'security/ir.model.access.csv',
        'wizard/stock_quant_putaway_single_views.xml',
        'wizard/stock_quant_putaway_multi_views.xml',
        'views/stock_quant_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
