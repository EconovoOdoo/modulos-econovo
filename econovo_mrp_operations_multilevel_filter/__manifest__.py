# -*- coding: utf-8 -*-
{
    'name': 'Econovo MRP Operations Multilevel Filter',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Filter the Operations list down to a BOM and all its multi-level sub-assemblies',
    'description': """
        Adds a contextual action to the Manufacturing > Configuration > Operations
        list (mrp.routing.workcenter): select one or more operations and reopen the
        same list filtered to their Bill of Material(s) plus every sub-BOM used by
        their components, at any depth (e.g. Bicycle + Wheel + the rest of their
        sub-assemblies), using the same BOM explosion relation Odoo's own
        "Structure and Cost" report relies on.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['mrp'],
    'data': [
        'views/mrp_routing_workcenter_server_actions.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
