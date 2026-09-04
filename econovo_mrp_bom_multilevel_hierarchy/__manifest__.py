# -*- coding: utf-8 -*-
{
    'name': 'Econovo MRP BOM Multilevel Hierarchy',
    'version': '17.0.1.0.1',
    'category': 'Manufacturing',
    'summary': "View a BOM's full multi-level sub-assembly hierarchy from the Bills of Materials list",
    'description': """
        Adds a fa-sitemap button to the Bills of Materials list (Manufacturing >
        Products > Bills of Materials), inspired by OCA's mrp_bom_hierarchy module:
        clicking it reopens the same list, in tree view, filtered to every sub-BOM
        used by this BOM's components, at any depth (e.g. Wheel + the rest of
        Bicycle's sub-assemblies, without repeating Bicycle itself) - unlike a
        direct-children-only view. The breadcrumb trail shows which BOM the
        cascade came from.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['mrp'],
    'data': [
        'views/mrp_bom_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
