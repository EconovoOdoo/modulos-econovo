# -*- coding: utf-8 -*-
{
    'name': 'Econovo - Partner Delivered Lots & Serial Numbers',
    'version': '17.0.1.0.2',
    'category': 'Inventory/Inventory',
    'summary': (
        'Expose delivered lots and serial numbers per contact using '
        'last_delivery_partner_id.'
    ),
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['base', 'stock'],
    'data': [
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
