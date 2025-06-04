# -*- coding: utf-8 -*-
{
    'name': 'Econovo Batch Production Assignment',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Mass/batch assignment of manufacturing orders from list view',
    'description': '''
        This module allows batch assignment of manufacturing orders directly from the list view.
        
        Key Features:
        - Add mass assignment action in the "Action" button (gear icon) when selecting Manufacturing Orders
        - Use Odoo's native assignment logic (same as "Allocation" smart button)
        - Apply "Assign All" functionality massively to selected Manufacturing Orders
        - Avoid manual one-by-one assignment process
        
        Technical Details:
        - Extends mrp.production model
        - Adds server action for batch assignment
        - Uses native action_assign() method for consistent behavior
        - Maintains compatibility with Odoo's stock allocation logic
    ''',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'mrp',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_production_views.xml',
        'wizard/mrp_production_batch_assignment_wizard_views.xml',
        'data/ir_actions_server.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
