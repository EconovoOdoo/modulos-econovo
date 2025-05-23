{
    'name': 'Econovo DYMO Labels',
    'version': '17.0.1.0.0',
    'summary': 'Formato de etiquetas DYMO de tamaño personalizado 100x70mm para productos',
    'category': 'Reporting',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['product'],
    'data': [
        'security/ir.model.access.csv',
        'data/product_label_layout_data.xml',
        'wizard/dymo_labels_wizard_views.xml',
        'views/templates.xml',
        'reports/dymo_label_report.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            '/econovo_dymo_labels/static/src/scss/dymo_fonts.scss',
            '/econovo_dymo_labels/static/src/scss/dymo_label_report.scss',
        ],
    },
    'installable': True,
    'application': False,
}