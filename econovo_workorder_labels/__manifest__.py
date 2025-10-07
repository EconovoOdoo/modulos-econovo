{
    'name': 'Econovo Workorder Labels',
    'version': '17.0.1.1.0',
    'summary': 'Impresión de etiquetas de órdenes de trabajo de tamaño personalizado 100x70mm para productos Econovo',
    'category': 'Reporting',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['mrp', 'gg_automatic_mrp_schedule'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/workorder_labels_wizard_views.xml',
        'views/templates.xml',
        'reports/workorder_label_report.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            '/econovo_workorder_labels/static/src/scss/workorder_fonts.scss',
            '/econovo_workorder_labels/static/src/scss/workorder_label_report.scss',
        ],
    },
    'installable': True,
    'application': False
}