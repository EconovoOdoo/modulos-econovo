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
* Customs clearance tracking (Despacho de Aduana)
* NCM code management (Nomenclatura Común del Mercosur)
* Bidirectional date synchronization with purchase orders and pickings
* Full traceability with lots and serial numbers
* Support for custom stock locations and routes (user-configured)

**Regulatory Compliance:**
* ARCA (ex-AFIP) requirements
* BCRA MULC regulations
* Argentine customs procedures

**Integration:**
* purchase_stock: Integration with purchase order picking redirection
* stock: Support for transit locations and internal transfers
* account: MULC exchange rate tracking

**Configuration Required:**
* Stock locations for COMEX transit (En Viaje, Puerto, Zona Franca, Depósito Fiscal)
* Stock routes for COMEX import/export operations
* Picking types for COMEX workflow (COMEX/IN, COMEX/ARR, COMEX/FIS, COMEX/NAC)
* Push rules for automated stock flow between COMEX locations
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'mail',
        'purchase',
        'purchase_stock',
        'sale_stock',
        'stock',
        'stock_landed_costs',
        'account',
        'contacts',
    ],
    'auto_install': False,
    'application': False,
    'installable': True,
    'data': [
        # Security
        'security/econovo_l10n_ar_comex_groups.xml',
        'security/ir.model.access.csv',
        'security/econovo_l10n_ar_comex_security.xml',
        # Data
        'data/comex_operation_stage_data.xml',
        'data/comex_payment_instrument_data.xml',
        'data/comex_payment_timing_data.xml',
        'data/comex_port_data.xml',
        'data/comex_container_type_data.xml',
        'data/comex_customs_office_data.xml',
        'data/stock_package_type_data.xml',
        'data/comex_tribute_fields_data.xml',
        'data/comex_tribute_products_data.xml',
        'data/comex_tribute_keywords_data.xml',
        # Views
        'views/comex_operation_views.xml',
        'views/comex_operation_stage_views.xml',
        'views/comex_operation_product_line_views.xml',
        'views/comex_shipment_views.xml',
        'views/comex_customs_clearance_views.xml',
        'views/comex_mulc_views.xml',
        'views/comex_port_views.xml',
        'views/comex_container_type_views.xml',
        'views/comex_customs_office_views.xml',
        'views/comex_payment_instrument_views.xml',
        'views/comex_payment_timing_views.xml',
        'views/purchase_order_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_quant_package_views.xml',
        'views/res_partner_views.xml',
        'views/comex_tribute_product_mapping_views.xml',
        'views/comex_tribute_keyword_mapping_views.xml',
        'views/comex_tribute_parse_log_views.xml',
        'views/res_config_settings_views.xml',
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
}