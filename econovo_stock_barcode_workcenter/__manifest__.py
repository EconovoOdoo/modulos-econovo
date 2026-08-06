# -*- coding: utf-8 -*-
{
    "name": "Econovo - Stock Barcode Workcenter Display",
    "version": "17.0.1.1.0",
    "category": "Inventory/Inventory",
    "summary": "Display the assigned workcenter in the Barcode app picking view",
    "description": """
This module displays the assigned workcenter (Centro de trabajo) in the Barcode
application's picking detail view.

The workcenter is shown in the header area, below the picking reference name,
only when the picking has an assigned workcenter.

When viewing a Batch Transfer, each line also shows its own transfer's
Production Plan and workcenter (below the origin transfer reference, above the
destination location), since a batch mixes lines from different transfers.

Requires the Studio field x_studio_workcenter_id on stock.picking.
    """,
    "author": "Jose D. Leonett",
    "website": "https://github.com/josedleonett",
    "license": "AGPL-3",
    "depends": [
        "stock_barcode",
        "stock_barcode_picking_batch",
        "mrp",
        "econovo_mrp_component_lines",
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
