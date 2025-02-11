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

class warranty_report(models.AbstractModel):
    _name = 'report.dev_warranty_management.dev_warranty_report_template'
    _description='Warranty Report'

    def _get_report_values(self, docids, data=None):
        docs = self.env['warranty.warranty'].browse(docids)
        return {
            'doc_ids': docs.ids,
            'doc_model': 'warranty.warranty',
            'docs': docs,
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
