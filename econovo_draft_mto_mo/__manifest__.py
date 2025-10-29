# -*- coding: utf-8 -*-
{
    'name': 'Econovo - Draft MTO/MO Control',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Configurable Manufacturing Order draft behavior by source type (MTO/MTS/MPS/Orderpoint)',
    'description': """
Manufacturing Order Draft Control
==================================

This module provides granular control over when Manufacturing Orders should stay in draft state 
vs. auto-confirm, based on the source type (MTO, MTS, MPS, Orderpoint).

Features:
---------
* **Global Configuration**: Set default behavior for all MOs by source type
* **Product-level Override**: Configure specific products to always draft/confirm or custom rules
* **User-level Override**: Allow users to have personalized MO draft preferences
* **Hierarchy**: Global → Product → User (each level can override the previous)
* **Source Types Supported**:
  - MTO (Make To Order from Sales)
  - MTS (Make To Stock replenishment)
  - MPS (Master Production Schedule)
  - Orderpoint (Reordering Rules)

Technical Highlights:
---------------------
* **User Session Propagation**: Correctly identifies the user who initiated the action
  (not OdooBot) by capturing and propagating the session user through context
* **Robust MTO Detection**: Multi-level detection via sale_line_id, procurement group,
  and route configuration - works regardless of sequence format
* **Optimized Performance**: Minimal overhead with cached parameters

Maintains all Odoo native behavior:
------------------------------------
* MO consolidation for non-MTO flows
* Quantity validation
* Traceability messages in chatter
* Standard confirmation filters

Configuration:
--------------
1. Go to Settings → Manufacturing → MO Draft Control
2. Set global policy (Native Flow / Always Draft / Custom by Source)
3. Override at product level: Manufacturing tab in product form
4. Override at user level: Preferences tab in user form

Author: Jose D. Leonett
Website: https://github.com/josedleonett
License: AGPL-3
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'mrp',
        'stock',
        'sale_stock',  # For MTO route detection
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/default_config.xml',
        'views/res_config_settings_views.xml',
        'views/product_template_views.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
