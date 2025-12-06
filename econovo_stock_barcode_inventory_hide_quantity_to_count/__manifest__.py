# -*- coding: utf-8 -*-
{
    "name": "Econovo - Stock Barcode Inventory Hide Quantity to Count",
    "version": "17.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Hide expected quantity during inventory adjustments for true blind counting",
    "description": """
This module adds a configuration option to hide the expected quantity (quantity on hand)
during inventory adjustments in the Barcode app.

When enabled (blind count mode):
- Before counting: Shows "? / ?" instead of actual quantities
- After counting: Shows "12 / ?" (counted quantity visible, expected hidden)

This forces operators to perform a true blind count without being influenced
by the system's expected quantities.

Configuration:
- Go to Inventory > Configuration > Settings
- In the Barcode section, uncheck "Show Quantity to Count" to enable blind counting
    """,
    "author": "Jose D. Leonett",
    "website": "https://github.com/josedleonett",
    "license": "AGPL-3",
    "depends": [
        "stock_barcode",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "econovo_stock_barcode_inventory_hide_quantity_to_count/static/src/**/*.js",
            "econovo_stock_barcode_inventory_hide_quantity_to_count/static/src/**/*.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
