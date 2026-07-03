# -*- coding: utf-8 -*-
{
    'name': 'MRP Workorder Dependencies Planning Fix',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing/Manufacturing',
    'summary': 'Fix a core crash when (re)planning a Manufacturing Order whose workorders have cross-production dependencies.',
    'description': """
Fixes an Odoo core bug in ``mrp.production._plan_workorders()``
(``odoo/addons/mrp/models/mrp_production.py``) that can raise::

    TypeError: '<' not supported between instances of 'bool' and 'datetime.datetime'

This happens whenever a Manufacturing Order's last workorder is set, through the
"Workorder Dependencies" feature, as a blocker of a workorder that belongs to a
**different** Manufacturing Order (a common and legitimate setup when several
component MOs must finish before one assembly/welding MO can start).

The core method detects the "final" workorders of a production with
``not workorder.needed_by_workorder_ids``, without limiting that check to
workorders of the SAME production. A workorder that IS the last step of its own
MO, but ALSO blocks a workorder belonging to a different MO, is therefore never
(re)planned, keeps no calendar reservation (``leave_id``), and crashes the final
``min()``/``max()`` computation of the Manufacturing Order's overall
``date_start``/``date_finished`` as soon as it is mixed with another workorder
that does have a valid one (e.g. right after "Update Bill of Materials" from a
PLM Engineering Change Order, or when clicking "Replan").

This module overrides ``_plan_workorders()`` to:

* Scope the "final workorder" detection to workorders of the SAME production.
* Defensively ignore workorders that still have no scheduled ``leave_id`` when
  computing the Manufacturing Order's overall ``date_start``/``date_finished``,
  instead of crashing.

This override should be removed if/when the upstream bug is fixed in Odoo.
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'mrp',
    ],
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
