{
    "name": "Econovo Stock Picking Split by Count",
    "summary": "Split a transfer into a chosen number of pickings, like the MO split wizard",
    "description": """
Adds a "Split by Count" mode to the picking split wizard (OCA stock_split_picking),
mirroring the Manufacturing Order split wizard (mrp.production.split): choose how
many transfers (#) to split into, quantities are auto-distributed per product and
stay editable, along with an optional responsible user and scheduled date for each
resulting transfer.
""",
    "version": "17.0.1.0.1",
    "category": "Inventory",
    "author": "Jose D. Leonett",
    "website": "https://github.com/josedleonett",
    "license": "AGPL-3",
    "depends": ["stock_split_picking"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_split_picking_views.xml",
    ],
    "installable": True,
    "application": False,
}
