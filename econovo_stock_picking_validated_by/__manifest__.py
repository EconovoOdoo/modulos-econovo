# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': "Stock Picking Validated By",
    'summary': "Track which user validated a transfer",
    'description': """
Stock Picking Validated By
===========================

``stock.picking`` has no native way to know which user validated a
transfer, only the current responsible (``user_id``, which can be
reassigned or left empty) and ``date_done`` (when it happened, but not
who did it).

This module adds a **Validated By** field (``validation_user_id``,
``res.users``, ``readonly``, ``copy=False``) that is stamped with the
active session user automatically the moment a transfer is set to done
via the "Validate" button (including batch validation, since
``stock.picking.batch`` funnels into the same flow) - never editable by
hand, always reflecting who actually performed the validation.

The field is shown:

* On the transfer form view, right after "Effective Date" (``date_done``)
* On the transfers list view, as an optional (hideable) column
* On the transfers search view, as a directly searchable field and as a
  "Group By" option
* On the Moves and Moves History report list views (``stock.move`` and
  ``stock.move.line``), as an optional (hideable) column. ``stock.move``
  is stamped independently (covers moves with no transfer at all, such as
  inventory adjustments or quant relocations); ``stock.move.line``
  follows its move's value.

A migration script backfills the field on historical ``done`` records
(transfers, via their tracking history; picking-less moves, via their
creating user) so past data is not left empty.
    """,
    'author': "Jose D. Leonett",
    'website': 'https://github.com/josedleonett',
    'category': 'Inventory/Inventory',
    'version': '17.0.1.0.1',
    'license': 'AGPL-3',
    'depends': [
        'stock',
    ],
    'data': [
        'views/stock_picking_views.xml',
        'views/stock_move_views.xml',
        'views/stock_move_line_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
