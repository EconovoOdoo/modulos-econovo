{
    'name': 'MRP BoM Category Costs',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Add category costs analysis to BoM Structure report',
    'description': """
        This module extends the BoM Structure report to show costs grouped by product category.
        Features:
        - Shows total cost per product category
        - Adds a new section in the BoM report with category analysis
        - Maintains all standard BoM report features
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'depends': ['mrp', 'product'],
    'data': [
        'views/report_mrp_bom_template.xml',
        'views/mrp_report_mo_overview_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}