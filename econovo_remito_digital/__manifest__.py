{
    'name': 'Econovo Remito Digital',
    'version': '17.0.1.2.0',
    'summary': 'Remito digital A4 para Argentina (talonarios digitalizados con CAI)',
    'category': 'Inventory',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'stock_voucher',
        'stock_voucher_ux',
        'stock_ux',
        'l10n_ar',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_book_views.xml',
        'views/remito_digital_report.xml',
        'views/remito_digital_templates.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            '/econovo_remito_digital/static/src/scss/remito_digital.scss',
        ],
    },
    'installable': True,
    'application': False,
}
