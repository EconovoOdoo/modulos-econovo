{
    'name': 'Econovo Workorder Labels',
    'version': '17.0.1.0.0',
    'summary': 'Impresión de etiquetas de órdenes de trabajo de tamaño personalizado 100x70mm para productos Econovo',
    'category': 'Reporting',
    'author': 'Jose D. Leonett',
    'website': 'http://josedleonett.github.com',
    'license': 'AGPL-3',
    'depends': ['mrp'],
    'data': [
        'reports/workorder_label_report.xml',
        'views/templates.xml',
        'data/workorder_label_layout_data.xml',
    ],
    'installable': True,
    'application': False
}