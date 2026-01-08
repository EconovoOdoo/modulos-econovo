# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Argentina COMEX Operations',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Purchase',
    'summary': 'Manage import/export operations for Argentina with ARCA and MULC integration',
    'description': """
Argentina COMEX Operations Management
=====================================

This module provides comprehensive management of international trade operations
(COMEX - Comercio Exterior) for Argentina, including:

**Features:**
* Dynamic stage management (Kanban-style like CRM/Project)
* MULC (Mercado Único y Libre de Cambios) operations tracking
* Integration with purchase orders and stock movements
* Transit stock locations for COMEX stages (En Viaje, Puerto, Zona Franca, Depósito Fiscal)
* Customs clearance tracking (Despacho de Aduana)
* NCM code management (Nomenclatura Común del Mercosur)
* Bidirectional date synchronization with purchase orders and pickings
* Full traceability with lots and serial numbers

**Regulatory Compliance:**
* ARCA (ex-AFIP) requirements
* BCRA MULC regulations
* Argentine customs procedures

**Integration:**
* purchase_stock: Automatic picking redirection to COMEX locations
* stock: Transit location hierarchy and internal transfers
* account: MULC exchange rate tracking
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'mail',
        'purchase_stock',
        'sale_stock',
        'stock',
        'account',
        'contacts',
    ],
    'data': [
        # Security
        'security/econovo_l10n_ar_comex_groups.xml',
        'security/ir.model.access.csv',
        'security/econovo_l10n_ar_comex_security.xml',
        # Data - Order matters: locations first, then stages that reference them
        'data/stock_location_data.xml',
        'data/comex_operation_stage_data.xml',
        'data/stock_route_data.xml',
        # Views
        'views/comex_operation_views.xml',
        'views/comex_operation_stage_views.xml',
        'views/comex_shipment_views.xml',
        'views/comex_customs_clearance_views.xml',
        'views/comex_mulc_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/res_partner_views.xml',
        'views/econovo_l10n_ar_comex_menus.xml',
    ],
    'demo': [
        'demo/comex_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'econovo_l10n_ar_comex/static/src/scss/comex_kanban.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': '_post_init_hook',
}
