# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################
{
	'name':'Warranty Management | Product Warranty Management | Warranty Registration and Warranty Claim | Helpdesk for Claim and Support',
	'sequence': 1,
	'version':'17.0.1.6',
	'category':'Services',
	'description':'''
Warranty Management app simplifies how you handle product warranties and claims. With this app, you can easily create and manage warranties for products you sell. When a customer buys a product, the warranty is automatically added to their account. If something goes wrong with the product, customers can claim their warranty through an online portal and raise a ticket for any issues they face.

This app helps to manage both free and paid warranties.It even sends automatic emails to customers when their warranty is about to expire. You can also manage warranty renewals with ease. If a warranty is paid, the app will automatically generate an invoice for it.

You can track and manage warranties directly from the website using a dedicated tracking menu. The app also helps you handle repairs and replacements as part of the warranty process by creating repair orders, assigning tasks to technicians, and tracking repair progress.

Customers who submit a claim will receive a request to rate the warranty service, and their feedback will be visible on the warranty screen. For reporting, the app lets you print warranties, warranty cards, and warranty histories as PDF reports. You can also view detailed warranty analysis to keep track of everything.
	''',
	'summary':'Warranty Management Warranty Management Product Warranty Management Warranty Registration and Warranty Claim Helpdesk for Claim and Support Create warranty manage products warranty and claims product warranty in odoo product warranty registration Helpdesk for customer ticket support Product Warranty Management Product Warranty Claim warranty module claim Warranty Maintenance Customer Service Management manage warranty app website product Warranty product Maintenance product service warranty serial number claim Warranty renewal Warranty product Warranty register product Warranty product warranty management serial number Registration lead to create ticket',
	'depends':['sale','helpdesk','product','website','stock','sale_management','repair','project','rating', 'mail'],
	'data':[
	        'data/sequence_sequence.xml',
	        'data/mail_template.xml',
	        'data/warranty_expiry_cron.xml',
	        'data/email_template.xml',
    		'security/ir.model.access.csv',
            'views/main_menu.xml',
            'report/report_menu.xml',
            'wizard/create_task.xml',
            'wizard/warranty_history.xml',
            #'views/dashboard.xml',
            'views/res_config_settings_views.xml',
    		'views/product_product_view.xml',
    		'views/warranty_warranty_view.xml',
    		'views/renewal_warranty_view.xml',
    		'views/warranty_expiry_view.xml',
    		'views/warranty_product_view.xml',
    		'views/warranty_ticket_view.xml',
    		'views/warranty_ticket_tag_view.xml',
    		'portal/warranty_portal_view.xml',
    		'views/sale_order_view.xml',
    		'views/repair_order_view.xml',
    		'views/project_task.xml',
    		'views/warranty_details_view.xml',
    		'views/stock_lot_view.xml',
    		'views/warranty_policy.xml',
    		'views/views.xml',
    		'report/warranty_analysis.xml',
    		'report/warranty_card_view.xml',
    		'report/warranty_history_template.xml',
    		'report/warranty_report_view.xml',
			],
    'assets': {
      # 'web.assets_backend': [
       #    'dev_warranty_management/static/src/css/dashboard.css',
      #     'dev_warranty_management/static/src/js/main.js',
      #     'dev_warranty_management/static/src/xml/dashboard.xml'
       #],
       'web.assets_frontend': [
            'dev_warranty_management/static/src/js/portal.js',
        ],
   },
	'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'images': ['images/main_screenshot.gif'],
    'installable': True,
    'application': True,
    'auto_install': False,
    
    #author and support Details
    'author': 'DevIntelle Consulting Service Pvt.Ltd',
    'website': 'http://www.devintellecs.com',    
    'maintainer': 'DevIntelle Consulting Service Pvt.Ltd', 
    'support': 'devintelle@gmail.com',
    'price':53.0,
    'currency':'EUR',
    #'live_test_url':'https://youtu.be/A5kEBboAh_k',
	'pre_init_hook' :'pre_init_check',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
