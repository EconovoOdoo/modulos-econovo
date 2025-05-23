{
    'name': 'Econovo Operations Dependency by Sequence',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Automatically set operation dependencies based on sequence',
    'description': """
        This module enhances the manufacturing process by allowing automatic configuration 
        of operation dependencies based on their sequence in the bill of materials.
        
        When the "allow_operation_dependencies" field is checked on a BoM, a button will appear 
        that automatically sets up operation dependencies. Each operation will be blocked by 
        the previous operation in the sequence.
    """,
    'author': 'Jose D. Leonett',
    'website': 'http://josedleonett.github.com',
    'license': 'AGPL-3',
    'depends': ['mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_bom_views.xml',
        'views/server_actions.xml',
        'wizards/set_dependencies_wizard_view.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
