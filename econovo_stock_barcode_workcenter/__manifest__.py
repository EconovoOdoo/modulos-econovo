# -*- coding: utf-8 -*-
{
    "name": "Econovo - Stock Barcode Workcenter Display",
    "version": "17.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Display the assigned workcenter in the Barcode app picking view",
    "description": """
This module displays the assigned workcenter (Centro de trabajo) in the Barcode
application's picking detail view.

The workcenter is shown in the header area, below the picking reference name,
only when the picking has an assigned workcenter.

Requires the Studio field x_studio_workcenter_id on stock.picking.
    """,
    "author": "Jose D. Leonett",
    "website": "https://github.com/josedleonett",
    "license": "AGPL-3",
    "depends": [
        "stock_barcode",
        "mrp",
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "econovo_stock_barcode_workcenter/static/src/**/*.js",
            "econovo_stock_barcode_workcenter/static/src/**/*.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
