# -*- coding: utf-8 -*-
{
    'name': 'PLM Enforce ECO Workflow',
    'version': '17.0.1.5.0',
    'category': 'Manufacturing/Manufacturing',
    'summary': 'Force BoM modifications through the PLM Engineering Change Order workflow for controlled editors.',
    'description': """
Adds a "PLM Controlled BoM Editor" group whose members can:

* Read all Bills of Materials.
* Create new Bills of Materials (including via Excel import).
* Edit Bills of Materials that have not yet been used in any Manufacturing Order.
* Edit a Bill of Materials when a related ECO is open (confirmed or in progress).
* Delete Bills of Materials they created if no Manufacturing Order uses them.
* Apply ECOs that they validated.

The group cannot edit a production-ready Bill of Materials directly once it
has been used. Changes must go through an Engineering Change Order.

A "Crear ECO" mass action is added to the Bill of Materials list view to
quickly open a draft ECO for the selected records.
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'mrp_plm',
    ],
    'data': [
        'security/econovo_mrp_plm_enforce_eco_groups.xml',
        'security/ir.model.access.csv',
        'security/econovo_mrp_plm_enforce_eco_security.xml',
        'views/mrp_bom_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
