{
    'name': 'Econovo MRP Workorder Blocked By Enforcement',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Enforce workorder dependencies: prevent starting a workorder until all its blockers are done.',
    'description': """
        Odoo's blocked_by_workorder_ids field only controls the visual state (pending/ready),
        but does NOT prevent an operator from clicking Start on a blocked workorder.

        This module enforces the dependency at execution time: if a workorder has any blocker
        in blocked_by_workorder_ids that is not yet done or cancelled, button_start raises a
        UserError listing the pending operations.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['mrp'],
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
