# -*- coding: utf-8 -*-
{
    'name': "MRP BOM Tree Consolidation",
    'summary': "Consolidates components of BOMs and their hierarchical components (child, grandchild, etc.)",
    'description': """This module aggregates and consolidates the components used by a Bill of Materials (BoM) and all the nested BoMs (child, grandchild, etc.). It recursively collects all the components involved in a manufacturing process, providing a comprehensive summary of all materials used, including those from subassemblies and lower-level BoMs.""",
    'author': "J. Leonett",
    'website': "https://github.com/josedleonett",
    'category': 'Manufacturing',
    'version': '1.0.0',
    'depends': ['mrp', 'bom_components_operations_total_time'],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_bom_views_inherit.xml',
        'views/mrp_bom_tree_consolidation_views.xml',
        'views/mrp_bom_tree_expanded_views.xml',
        # 'reports/mrp_bom_consolidated_report.xml'  (Add if creating a report)
    ],
    'installable': True,
    'application': True,
}