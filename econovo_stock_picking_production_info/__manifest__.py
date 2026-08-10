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
Production Plan a transfer supplies components for. A "Choose Components"
transfer's own move is never linked to its MO directly (no
raw_material_production_id, no move_dest_ids/move_orig_ids chain in this
Econovo install's replenishment-to-workcenter routes) - the only real link
is the procurement group (``group_id``) shared with the MO, exactly like
the existing Studio field ``x_studio_group_id_mo_plan_id`` this module
replaces.

This module adds a proper **Production Plan** field
(``related='group_id.mrp_production_ids.plan_id'``) and a proper
**Workcenter** field
(``related='group_id.mrp_production_ids.workorder_ids.workcenter_id'``) on
``stock.picking`` - faithful, module-owned copies of the Studio fields they
replace (same relation, same related path, same store=True) - and shows
both, on:

* The transfer form view, right after "Source Document"
* The transfers list view (Inventory > Transfers and, since a Batch
  Transfer's own "Transfers" tab reuses that same list, there too), as
  optional (hideable) columns

Requirements:
-------------
* Module `mrp` (provides `mrp.workcenter`)
* Module `gg_automatic_mrp_schedule` (provides `mrp.plan`)
    """,
    'author': "Jose D. Leonett",
    'website': 'https://github.com/josedleonett',
    'category': 'Inventory/Inventory',
    'version': '17.0.2.1.0',
    'license': 'AGPL-3',
    'depends': [
        'mrp',
        'gg_automatic_mrp_schedule',
    ],
    'data': [
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
