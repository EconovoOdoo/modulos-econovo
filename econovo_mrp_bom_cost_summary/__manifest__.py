{
    'name': 'Econovo MRP BOM Cost Summary',
    'version': '17.0.1.1.0',
    'category': 'Manufacturing',
    'summary': 'Collapsible cost breakdown summary in BOM Overview report',
    'description': """
Adds a cost summary section at the bottom of the BOM Overview (mrp_bom_report)
that displays component costs grouped by product category, operation costs
grouped by work center, and subcontracting costs grouped by vendor,
with 3-level drill-down, dual currency (ARS + USD) and grand total.
    """,
    'depends': ['mrp', 'product'],
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'data': [
        'report/report_cost_summary.xml',
        'views/mrp_bom_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'econovo_mrp_bom_cost_summary/static/src/utils/**/*.js',
            'econovo_mrp_bom_cost_summary/static/src/components/**/*.js',
            'econovo_mrp_bom_cost_summary/static/src/components/**/*.xml',
            'econovo_mrp_bom_cost_summary/static/src/components/**/*.scss',
            'econovo_mrp_bom_cost_summary/static/src/patches/**/*.js',
            'econovo_mrp_bom_cost_summary/static/src/patches/**/*.xml',
            'econovo_mrp_bom_cost_summary/static/src/views/**/*.js',
            'econovo_mrp_bom_cost_summary/static/src/views/**/*.xml',
            'econovo_mrp_bom_cost_summary/static/src/views/**/*.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'external_dependencies': {
        'python': ['openpyxl'],
    },
}
