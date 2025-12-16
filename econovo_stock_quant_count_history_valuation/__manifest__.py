# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Stock Quant Count History - Valuation',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Cost valuation for inventory count history with dual currency support',
    'description': """
Stock Quant Count History - Valuation
======================================

This module extends the count history functionality to include cost valuation,
allowing users to see the financial impact of inventory counts.

Features
--------
* Captures unit cost at the moment of count (snapshot)
* Supports dual currency: Company currency (ARS) and USD
* Links to Stock Valuation Layers (SVL) when counts are applied
* Hybrid approach: Uses SVL values when available, snapshot otherwise
* Shows losses/gains with visual indicators

Compatibility
-------------
* Odoo 17.0
* Works with or without gg_cost_dolarization module
* Respects all cost methods: Standard, FIFO, Average

Author: Jose D. Leonett
Website: https://github.com/josedleonett
License: AGPL-3
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'econovo_stock_quant_count_history',
        'stock_account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/stock_quant_count_history_valuation_security.xml',
        'views/stock_quant_views.xml',
        'views/stock_quant_count_history_views.xml',
    ],
    'assets': {},
    'installable': True,
    'auto_install': False,
    'application': False,
    'post_init_hook': '_post_init_hook',
}
