{
    'name': 'Inventory Count History',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Track inventory count history for applied and non-applied counts',
    'description': """
Inventory Count History
=======================

This module provides tracking of inventory counts, both applied and non-applied.

Features:
- Automatic registration when applying inventory adjustments
- Manual registration with "Save counted quantity to history" button
- View count history per quant with "Counts" button
- Full audit trail: user, datetime, quantities, differences
- Multi-company support
- Spanish (Argentina) translations included

The module uses non-invasive code patterns for easy migration to Odoo 18+.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['stock'],
    'data': [
        'security/econovo_stock_quant_count_history_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/stock_quant_count_history_views.xml',
        'views/stock_quant_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
