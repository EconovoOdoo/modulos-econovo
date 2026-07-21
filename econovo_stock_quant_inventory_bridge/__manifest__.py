# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Stock Quant / Inventory Adjustment Bridge',
    'version': '17.0.1.0.2',
    'summary': 'Keeps the classic Physical Inventory menu active alongside '
               'OCA Inventory Adjustment Groups, and allows assigning '
               'selected stock quants to a group from the Request a Count '
               'wizard.',
    'description': '''
This module bridges the classic Odoo "Physical Inventory" quant list with
the "Inventory Adjustment Group" (stock.inventory) workflow added by the
OCA stock_inventory module:

- Keeps the core "Physical Inventory" menu
  (stock.menu_action_inventory_tree) active alongside the OCA
  "Inventory Adjustments" menu, self-healing on every server restart or
  module update, even if stock_inventory is upgraded on its own.
- Extends the "Request a Count" wizard (stock.action_stock_request_count)
  so quants selected in the classic list view can also be assigned to a
  new or an existing Inventory Adjustment Group.
    ''',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'category': 'Inventory/Inventory',
    'depends': [
        'stock',
        'stock_inventory',
    ],
    'data': [
        'wizard/stock_request_count_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
