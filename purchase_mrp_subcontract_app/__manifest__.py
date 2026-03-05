# -*- coding: utf-8 -*-

{
    'name' : "MRP Subcontracting - Workorder Subcontract Management",
    "author": "Edge Technologies",
    'version': '17.0.1.0',
    'live_test_url': "https://youtu.be/F4fUcgiDg7w",
    "images":['static/description/main_screenshot.png'],
    'summary': 'MRP Subcontracting process on manufacturing subcontracting process with MRP subcontract management workorder subcontracting process bill of material subcontract MO subcontract process with manufacturing subcontract process on MRP.',
    'description' : """MRP Subcontracting purchase, picking & return picking from work order.
    """,
    "license" : "OPL-1",
    'depends' : ['account','mrp','purchase',],
    'data': [
            'security/subcontracting_group.xml',
            'report/subcontract_report_template.xml',
            'views/subcontracting_po_orders.xml',
            'views/mrp_workorder.xml',
            'views/mrp_workcenter_view.xml',
             ],
    'installable': True,
    'auto_install': False,
    'price': 28,
    'currency': "EUR",
    'category': 'Manufacturing',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
