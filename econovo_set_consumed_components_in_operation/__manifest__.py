{
    'name': 'Econovo Set Consumed Components in Operation',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Set component consumption in specific operations for Bills of Materials',
    'description': """
        This module allows bulk configuration of component consumption in specific operations
        for Bills of Materials. You can set components to be consumed in:
        - First operation
        - Last operation  
        - Specific operation by sequence number
        
        The module provides a wizard for processing multiple BOMs at once and handles
        various edge cases like BOMs without operations.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/server_actions.xml',
        'wizards/set_consumed_components_wizard_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
