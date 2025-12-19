# -*- coding: utf-8 -*-
{
    'name': 'Econovo MRP Workorder State Control (Odoo 19 Backport)',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Allow flexible workorder state changes including reverting done to ready (backport from Odoo 19)',
    'description': """
        MRP Workorder State Control
        ============================
        
        This module backports Odoo 19 functionality that allows flexible
        workorder state changes, including reverting from 'done' to 'ready'
        as an intermediate step.
        
        Features:
        ---------
        * Identical implementation of Odoo 19's set_state() method
        * Allows reverting workorders from 'done' to 'ready' and then to 'progress'
        * Removes the readonly restriction from the state field
        * Fully compatible with Odoo's standard business logic
        
        Use Cases:
        ----------
        * Correcting errors in production registration
        * Reprocessing work orders
        * Greater flexibility in manufacturing workflow
        
        WARNING:
        --------
        This module allows modifying the state of already completed workorders.
        Use with caution and only by authorized users.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'mrp',
    ],
    'data': [
        'security/mrp_workorder_security.xml',
        'views/mrp_workorder_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
