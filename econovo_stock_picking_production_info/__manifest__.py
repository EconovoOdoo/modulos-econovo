# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': "Stock Picking Production Info",
    'summary': "Show the Production Plan and Workcenter on transfers",
    'description': """
Stock Picking Production Info
==============================

``stock.picking`` has no native way to know which Manufacturing Order's
Production Plan a transfer supplies components for: the only related data
lives on ``stock.move`` (``production_plan_id``, added by
``econovo_mrp_component_lines``), and it isn't linked directly on a
"Choose Components" transfer's own move - only on the actual MO consumption
move further down the destination chain.

This module adds a computed **Production Plan** field and a proper
**Workcenter** field (``workcenter_id``) on ``stock.picking`` - replacing the
Studio field ``x_studio_workcenter_id`` it used to rely on, whose value is
copied over on install - and shows both, on:

* The transfer form view, right after "Source Document"
* The transfers list view (Inventory > Transfers and, since a Batch
  Transfer's own "Transfers" tab reuses that same list, there too), as
  optional (hideable) columns

Requirements:
-------------
* Module `econovo_mrp_component_lines` (provides `_get_supply_production`)
    """,
    'author': "Jose D. Leonett",
    'website': 'https://github.com/josedleonett',
    'category': 'Inventory/Inventory',
    'version': '17.0.1.0.0',
    'license': 'AGPL-3',
    'depends': [
        'econovo_mrp_component_lines',
    ],
    'data': [
        'views/stock_picking_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
