# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, api

class warranty_policy(models.Model):
    _name = 'warranty.policy'
    _description = 'Warranty Policy'
    
    name = fields.Char(string='Name', required=True)
    note = fields.Html(string='Policy Details')
    
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
