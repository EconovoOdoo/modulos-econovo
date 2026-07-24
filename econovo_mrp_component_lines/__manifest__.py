# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Econovo MRP Component Lines',
    'version': '17.0.1.0.2',
    'category': 'Manufacturing',
    'summary': 'List view of component (raw material) lines across all Manufacturing Orders',
    'description': """
Econovo MRP Component Lines
============================

Adds a Manufacturing > Operations > Manufacturing Order Lines menu entry
that lists the component (raw material) lines of every Manufacturing Order
in a single flat view, instead of having to open each Manufacturing Order
individually to see its "Components" tab.

Key Features:
-------------
* Flat, filterable and groupable list of ``stock.move`` records that are
  components of a Manufacturing Order (``raw_material_production_id`` set)
* Group by Manufacturing Order, Component, Status, Operation, Source
  Location or Production Plan (``gg_automatic_mrp_schedule``'s ``mrp.plan``,
  exposed as a related ``production_plan_id`` field)
* Quick filters for Pending, Consumed, Done and Cancelled lines
* Totals (sum) on Quantity To Consume and Consumed columns
* Buttons to open the transfer that supplied the component to its source
  location (e.g. the "Choose components" transfer), in form view or
  directly in the Barcode app, reusing stock_barcode's own actions
* Read-only view: use the Manufacturing Order itself to register consumption

    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'mrp',
        'gg_automatic_mrp_schedule',
        'stock_barcode',
    ],
    'data': [
        'views/stock_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
