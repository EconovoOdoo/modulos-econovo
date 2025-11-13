{
    'name': 'Econovo - Barcode Kit/BOM Stock Move Line Grouping',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Barcode',
    'summary': 'Group kit/BOM components in barcode app with collapse/expand functionality',
    'description': """
Groups kit/BOM components under their parent kit name in the stock barcode app, 
with support for multi-location components and native Odoo UI patterns.
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'stock_barcode',      # Base barcode app (Enterprise)
        'mrp',                # BOM/kit functionality
        'stock_barcode_mrp',  # Kit explosion compatibility
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'econovo_barcode_kit_bom_stock_move_line_grouping/static/src/models/barcode_picking_model.js',
            'econovo_barcode_kit_bom_stock_move_line_grouping/static/src/components/kit_grouped_line.xml',
            'econovo_barcode_kit_bom_stock_move_line_grouping/static/src/components/kit_grouped_line.js',
            'econovo_barcode_kit_bom_stock_move_line_grouping/static/src/scss/kit_barcode.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
