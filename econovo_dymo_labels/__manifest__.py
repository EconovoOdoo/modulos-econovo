{
    'name': 'Econovo DYMO Labels',
    'version': '17.0.1.0.0',
    'summary': 'Impresión de etiquetas DYMO de tamaño personalizado 100x70mm para productos Econovo',
    'category': 'Reporting',
    'author': 'Jose D. Leonett',
    'website': 'http://josedleonett.github.com',
    'license': 'AGPL-3',
    'depends': ['product'],
    'data': [
        'reports/dymo_label_report.xml',
        'views/templates.xml',
    ],
    'installable': True,
    'application': False,
}