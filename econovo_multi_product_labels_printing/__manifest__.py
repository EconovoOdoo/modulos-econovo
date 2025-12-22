{
    'name': 'Econovo Multi Product Labels Printing',
    'version': '17.0.1.1.0',
    'summary': 'Permite imprimir múltiples etiquetas de productos con cantidades personalizadas',
    'category': 'Inventory',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['stock', 'econovo_dymo_labels'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/multi_labels_wizard_views.xml',
        'views/stock_quant_views.xml',
    ],
    'installable': True,
    'application': False,
}
