# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##########################################################################

from odoo import fields, models, api
from datetime import date
from odoo.tools.misc import xlwt
from io import BytesIO
import base64
from xlwt import easyxf
from datetime import datetime

class WarrantyHistory(models.TransientModel):
    _name = 'warranty.history.report'
    _description = 'Warranty History Report'

    def print_pdf(self):
        return self.env.ref('dev_warranty_management.action_warranty_history_report').report_action(self)

    start_date = fields.Date(string='Start Date', required=True, default=date.today())
    end_date = fields.Date(string='End Date', required=True, default=date.today())
    state = fields.Selection([('draft','Draft'),('running','Running'),('invoiced','Invoiced'),('done','Done'),('cancel','Cancelled'),
                              ('expire','Expired')],default='draft',string='Status') 


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
