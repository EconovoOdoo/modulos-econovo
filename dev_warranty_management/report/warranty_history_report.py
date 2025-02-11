# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models
import itertools
import operator 
from itertools import groupby
from operator import itemgetter
from datetime import datetime


class WarrantyHistoryReport(models.AbstractModel):
    _name = 'report.dev_warranty_management.dev_warranty_history_tmpl'

    def get_warranty_details(self, wizard_id):
        record = [('date', '>=', wizard_id.start_date), ('date', '<=', wizard_id.end_date)]
        if wizard_id.state:
            record.append(('state','=',wizard_id.state))
            
        warranty_ids = self.env['warranty.warranty'].search(record,order="id desc")

        box=[]
        if warranty_ids:
            for rec in warranty_ids:
               vals = {'state':rec.state,'date':rec.date,
                        'customer':rec.customer_id.name,'sale':rec.sale_id.name,
                        'product': rec.product_id.name,'start':rec.start_date.strftime('%d/%m/%Y') if rec.start_date else None,
                        'end':rec.end_date.strftime('%d/%m/%Y') if rec.end_date else None,
                        'number':rec.number,'type':rec.waranty_type
                        }
               box.append(vals)
            
            box = sorted(box, key=itemgetter('state'))
            groups = itertools.groupby(box, key=operator.itemgetter('state'))
            group_lines = [{'state': k, 'values': [x for x in v]} for k, v in groups]
            return group_lines
        else:
            return False

    def _get_report_values(self, docids, data=None):
        docs = self.env['warranty.history.report'].browse(docids)
        return {
            'doc_ids': docs.ids,
            'doc_model': 'warranty.history.report',
            'get_warranty_details': self.get_warranty_details,
            'docs': docs,
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
