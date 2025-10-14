{
    'name': 'Econovo DYMO Labels',
    'version': '17.0.4.2.0',
    'summary': 'Custom DYMO label formats 100x70mm and 100x50mm for products',
    'category': 'Reporting',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['product', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/product_label_layout_data.xml',
        'wizard/dymo_labels_wizard_views.xml',
        'views/templates.xml',
        'views/templates_100x50.xml',
        'reports/dymo_label_report.xml',
        'reports/dymo_label_report_100x50.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            '/econovo_dymo_labels/static/src/scss/dymo_fonts.scss',
            '/econovo_dymo_labels/static/src/scss/dymo_label_report.scss',
            '/econovo_dymo_labels/static/src/scss/dymo_label_report_100x50.scss',
        ],
    },
    'installable': True,
    'application': False,
}