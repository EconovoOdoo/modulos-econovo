# -*- coding: utf-8 -*-
{
    'name': 'Econovo Reception Report Label',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Custom reception report labels with barcodes for origin, destination and delivery info',
    'description': """
        Custom Reception Report Labels for Econovo
        ===========================================
        
        This module extends the standard Odoo reception report labels with:
        - Product barcode (Code128, 850x140px)
        - Origin operation barcode (Code128, 700x150px)
        - Destination operation barcode (Code128, 700x150px)
        - Delivery information (sale order, manufacturing order, or partner)
        - Quantity and lot/serial number
        
        Layout optimized for 100x70mm thermal labels with overflow prevention,
        fixed heights throughout to prevent page breaks, and horizontal footer layout.
        Uses JetBrainsMono and DejaVuSansMono fonts for optimal barcode rendering.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'stock',
    ],
    'data': [
        'views/templates.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'econovo_reception_report_label/static/src/scss/reception_fonts.scss',
            'econovo_reception_report_label/static/src/scss/reception_label.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
