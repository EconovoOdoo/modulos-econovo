# -*- coding: utf-8 -*-
{
    "name": "Econovo - Stock Barcode Inventory Hide Completion Status",
    "version": "17.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Hide visual completion feedback (green/red) during inventory adjustments",
    "description": """
This module adds a configuration option to hide the visual completion status
during inventory adjustments in the Barcode app.

When enabled (hide completion status):
- Lines are shown with a neutral background color
- No green (complete) or red (incomplete) visual feedback
- Useful for blind counting where operators should not know if their count matches

Configuration:
- Go to Inventory > Configuration > Settings
- In the Barcode section, uncheck "Show Completion Status" to hide visual feedback
    """,
    "author": "Jose D. Leonett",
    "website": "https://github.com/josedleonett",
    "license": "AGPL-3",
    "depends": [
        "stock",
        "stock_barcode",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "econovo_stock_barcode_inventory_hide_completion_status/static/src/**/*.js",
            "econovo_stock_barcode_inventory_hide_completion_status/static/src/**/*.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
