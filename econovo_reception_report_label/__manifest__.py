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
        - Product barcode (large, 850x140px Code128)
        - Origin operation barcode (DE row with picking name)
        - Destination operation barcode (RESERVADO PARA row with picking/location)
        - Delivery information (sale order, manufacturing order, or partner)
        - Quantity and lot/serial number in horizontal footer
        
        Custom paperformat: 100x70mm thermal labels with 2mm margins.
        Optimized for wkhtmltopdf with fixed height containers to prevent overflow.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'stock',
    ],
    'data': [
        'data/paperformat.xml',
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
