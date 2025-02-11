# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import api, fields, models, _

class warranty_history(models.Model):
    _name = "warranty.history"
    
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    warranty_id = fields.Many2one('warranty.warranty',string='Warranty(Link)')
    base_warranty_id = fields.Many2one('warranty.warranty',string='Warranty')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
