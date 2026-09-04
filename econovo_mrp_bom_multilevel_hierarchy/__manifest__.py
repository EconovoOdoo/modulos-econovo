# -*- coding: utf-8 -*-
{
    'name': 'Econovo MRP BOM Multilevel Hierarchy',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'View the full multi-level BOM hierarchy (this BOM + every sub-BOM) from the Bills of Materials list',
    'description': """
        Adds a fa-sitemap button to the Bills of Materials list (Manufacturing >
        Products > Bills of Materials), inspired by OCA's mrp_bom_hierarchy module:
        clicking it reopens the same list, in tree view, filtered to this BOM plus
        every sub-BOM used by its components, at any depth (e.g. Bicycle + Wheel +
        the rest of their sub-assemblies) - unlike a direct-children-only view.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['mrp', 'econovo_mrp_operations_multilevel_filter'],
    'data': [
        'views/mrp_bom_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
