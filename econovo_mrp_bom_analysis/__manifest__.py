# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Econovo MRP BOM Analysis',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'BOM Component Analysis with Cost Breakdown',
    'description': """
Econovo MRP BOM Analysis
========================

This module provides comprehensive Bill of Materials analysis including:

* Recursive explosion of all BOM levels
* Grouping by product category, product, origin type
* Inline cost editing synchronized with products
* Cost impact analysis with percentages
* Price variation tracking
* Stock availability display
* Supplier information display

Key Features:
-------------
* Smart button on BOM form to access component analysis
* Native tree view with Odoo grouping capabilities
* Editable fields that sync with original BOM lines and products
* Pivot and graph views for detailed analysis
* Support for multi-currency cost tracking (ARS/USD)

    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'mrp',
        'mrp_account',
        'stock',
        'product',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/product_category_origin_type_data.xml',
        'views/product_category_origin_type_views.xml',
        'views/product_category_views.xml',
        'views/bom_component_analysis_views.xml',
        'views/mrp_bom_views.xml',
        'views/bom_cost_report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'econovo_mrp_bom_analysis/static/src/components/**/*.js',
            'econovo_mrp_bom_analysis/static/src/components/**/*.xml',
            'econovo_mrp_bom_analysis/static/src/components/**/*.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
