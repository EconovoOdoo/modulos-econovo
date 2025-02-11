# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################
from odoo.exceptions import ValidationError
from odoo import api, fields, models, _

class warranty_details(models.Model):
    _name = "warranty.details"
    
    name = fields.Char(string="Name")
    warranty_period = fields.Integer(string='Warranty Period(In months)')
    waranty_type = fields.Selection([('free','Free'),('paid','Paid')],default='free'
                                    ,string='Warranty Type')
    waranty_charges = fields.Float(string='Paid Charges')
    allow_warranty_renewal = fields.Boolean(string='Warranty Renewal')
    renewal_time = fields.Integer(string='Renewal Time')

    @api.constrains('warranty_period')
    def onchange_of_periodamount(self):
        if self.warranty_period <= 0:
            raise ValidationError(_("Warranty Period must be greater than Zero."))    

 #   @api.constrains('waranty_charges')
 #   def onchange_of_chargeamount(self):
  #      if self.waranty_charges <= 0:
 #           raise ValidationError(_("Charges must be greater than Zero."))    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
