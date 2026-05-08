{
    'name': 'Econovo MRP MO Cost Summary',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Collapsible cost breakdown summary in MO Overview report',
    'description': """
Adds a cost summary section at the bottom of the Manufacturing Order Overview
that displays component costs grouped by product category (MO Cost vs Real Cost)
and operation costs grouped by work center, with 3-level drill-down and
grand totals. Accessible from the MO form view via a smart button.
    """,
    'depends': ['econovo_mrp_bom_cost_summary', 'mrp'],
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'data': [
        'views/mrp_production_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'econovo_mrp_mo_cost_summary/static/src/utils/**/*.js',
            'econovo_mrp_mo_cost_summary/static/src/patches/**/*.js',
            'econovo_mrp_mo_cost_summary/static/src/patches/**/*.xml',
            'econovo_mrp_mo_cost_summary/static/src/views/**/*.js',
            'econovo_mrp_mo_cost_summary/static/src/views/**/*.xml',
            'econovo_mrp_mo_cost_summary/static/src/views/**/*.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'external_dependencies': {
        'python': ['openpyxl'],
    },
}
