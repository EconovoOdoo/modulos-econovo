{
    'name': 'Econovo - Barcode Kit/BOM Stock Move Line Grouping',
    'version': '17.0.1.0.1',
    'category': 'Inventory/Barcode',
    'summary': 'Group kit/BOM components in barcode app with nested lot/serial grouping support',
    'description': """
Barcode Kit/BOM Component Grouping
===================================

Groups kit/BOM components under their parent kit name in the stock barcode app,
with full support for nested grouping (lot/serial groups within kit groups).

Features
--------
* Collapsible kit groups with component count badge
* Multi-location source indicators
* Nested lot/serial number grouping within kits
* Independent collapse/expand for each grouping level
* Native Odoo UI/UX patterns and styling
* Full compatibility with stock_barcode_mrp module

Technical
---------
* Uses OWL reactive state for nested group rendering
* Preserves Odoo's native lot/serial grouping logic
* CSS specificity rules for proper completion styling
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
            'econovo_barcode_kit_bom_stock_move_line_grouping/static/src/components/kit_subline.xml',
            'econovo_barcode_kit_bom_stock_move_line_grouping/static/src/components/kit_subline.js',
            'econovo_barcode_kit_bom_stock_move_line_grouping/static/src/components/kit_grouped_line.xml',
            'econovo_barcode_kit_bom_stock_move_line_grouping/static/src/components/kit_grouped_line.js',
            'econovo_barcode_kit_bom_stock_move_line_grouping/static/src/scss/kit_barcode.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
