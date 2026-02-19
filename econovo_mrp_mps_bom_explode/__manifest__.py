# -*- coding: utf-8 -*-
{
    'name': 'MPS - BoM Multi-Level Cascade Explode',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing/Manufacturing',
    'summary': 'Add all BoM levels when adding a product to MPS',
    'description': """
MPS - BoM Multi-Level Cascade Explode
======================================

Extends the Master Production Schedule (MPS) to allow adding all BoM
component levels (children, grandchildren, etc.) when adding a product,
instead of only the first level.

Adds a checkbox "Include multi-level cascade products" to the MPS product
creation dialog. When enabled, the system recursively traverses the entire
BoM tree and creates MPS entries for every component at every level.

Features:
- Recursive BoM traversal with cycle detection
- Skips consumable products and phantom/kit BoMs
- Respects existing MPS entries (no duplicates)
- Handles variant-specific BoM lines
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['mrp_mps'],
    'data': [
        'views/mrp_mps_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
