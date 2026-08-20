# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Argentina COMEX Operations',
    'version': '17.0.5.0.2',
    'category': 'Inventory/Purchase',
    'summary': 'Manage import/export operations for Argentina with automatic tribute tax calculation',
    'description': """
Argentina COMEX Operations Management
=====================================

Comprehensive management of international trade operations (COMEX - Comercio Exterior) 
for Argentina with full regulatory compliance and automated tax calculation.

**Core Features:**
* Dynamic Kanban-style workflow for operation stages
* Multi-shipment tracking with container management
* Customs clearance (Despacho de Aduana) management
* MULC (Mercado Único y Libre de Cambios) operations tracking
* Bidirectional synchronization with purchase orders and stock movements

**Tribute & Tax Management:**
* Automatic tax calculation via Tax Groups (IVA 21%, IIGG 6%, IIBB 3%)
* Smart invoice creation from customs clearance data
* Configurable product and keyword-based tribute field mapping
* Bidirectional sync: edit amounts in invoice or clearance
* Comprehensive audit trail with parsing logs

**Stock Integration:**
* COMEX-specific transit locations (En Viaje, Puerto, Zona Franca, Depósito Fiscal)
* Automatic picking redirection to COMEX locations
* Full product traceability through import lifecycle
* Support for packages and container tracking

**Regulatory Compliance:**
* ARCA (ex-AFIP) requirements support
* BCRA MULC regulations compliance
* Argentine customs procedures workflow
* Tax group system matching Argentine tax structure

**Technical Architecture:**
* Smart computed fields with inverse methods for bidirectional sync
* Configurable tribute field mappings (product and keyword-based)
* Parse log system for audit and configuration refinement
* Multi-company support with company-specific configurations
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
    'post_init_hook': '_create_comex_sequences',
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
        'data/comex_stock_data.xml',
        'data/comex_cron_data.xml',
        # Views
        'views/comex_operation_views.xml',
        'views/comex_operation_stage_views.xml',
        'views/comex_operation_tag_views.xml',
        'report/comex_operation_report_line_views.xml',
        'views/comex_operation_product_line_views.xml',
        'views/comex_shipment_views.xml',
        'views/comex_customs_clearance_views.xml',
        'views/comex_mulc_views.xml',
        'views/comex_port_views.xml',
        'views/comex_container_type_views.xml',
        'views/comex_customs_office_views.xml',
        'views/comex_payment_instrument_views.xml',
        'views/comex_payment_timing_views.xml',
        'views/account_move_views.xml',
        'views/purchase_order_views.xml',
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_picking_type_views.xml',
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