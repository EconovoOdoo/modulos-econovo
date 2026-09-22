# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
{
    'name': 'Econovo MRP Subcontracting Wizard',
    'version': '17.0.1.0.1',
    'category': 'Manufacturing/Manufacturing',
    'summary': 'Assisted externalization and internalization of manufacturing operations',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'mrp_subcontracting',
        'purchase_stock',
        'mrp_plm',
        'econovo_mrp_plm_enforce_eco',
    ],
    'data': [
        'security/econovo_mrp_subcontracting_wizard_groups.xml',
        'security/ir.model.access.csv',
        'data/mrp_subcontracting_chain_data.xml',
        'views/mrp_routing_operation_category_views.xml',
        'views/mrp_routing_workcenter_views.xml',
        'views/mrp_bom_views.xml',
        'views/product_template_views.xml',
        'views/mrp_subcontracting_chain_views.xml',
        'wizard/mrp_subcontracting_externalization_views.xml',
        'wizard/mrp_subcontracting_internalization_views.xml',
        'wizard/mrp_subcontracting_bulk_views.xml',
        'views/mrp_subcontracting_menus.xml',
    ],
    'installable': True,
    'application': False,
}
