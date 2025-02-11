# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields

class res_company(models.Model):
    _inherit = 'res.company'

    warranty_create_sale_order_time = fields.Boolean(string='Warranty Create On Sale Order Confirm')
    warranty_expiry_day = fields.Integer(string='Warranty Expired')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    warranty_create_sale_order_time = fields.Boolean(string='Warranty Create On Sale Order Confirm', related='company_id.warranty_create_sale_order_time', readonly=False)
    
    warranty_expiry_day = fields.Integer(string='Warranty Expired', related='company_id.warranty_expiry_day', readonly=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
