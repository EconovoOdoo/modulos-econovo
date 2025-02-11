# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import fields, models
from odoo import tools

class WarrantyAnalysisReport(models.Model):
    _name = 'warranty.analysis'
    _description = 'Warranty Analysis Report'
    _auto = False
    _rec_name = 'number'
    
    number = fields.Char(string="Number")
    customer_id = fields.Many2one('res.partner', string='Customer')
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Email')

    sale_id = fields.Many2one('sale.order', string='Sale Order')
    serial_no_id = fields.Many2one('stock.lot', string='Serial No')
    product_id = fields.Many2one('product.product', string='Product')
    warranty_period = fields.Integer(string='Warranty Period(In Months)')
    waranty_type = fields.Selection([('free','Free'),('paid','Paid')],string='Warranty Type')
    waranty_charges = fields.Float(string='Paid Charges')
    quantity = fields.Float(string='Quantity')
    uom_id = fields.Many2one('uom.uom',string='Unit Of Measure')
    date = fields.Date(String="Date")
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    state = fields.Selection([('draft','Draft'),('running','Running'),('invoiced','Invoiced'),('done','Done'),('cancel','Cancelled'),
                              ('expire','Expired')],string='Status')

    currency_id = fields.Many2one('res.currency')
    user_id = fields.Many2one('res.users', string='Salesperson')
    company_id = fields.Many2one('res.company', string='Company')
#    note = fields.Char(string="Note..")
    invoice_id = fields.Many2one('account.move', string='Invoice')
    warranty_renewal = fields.Boolean(string='Warranty Renewal')
    warranty_renewal_id = fields.Many2one('warranty.warranty',string='Warranty Renewal')
    warranty_source = fields.Char(string='Source')
    rene_warranty_count = fields.Integer(string='Renewal Warranty Count')
    warranty_details_id = fields.Many2one("warranty.details",string="Warranty")

    def _select(self):
        select_str = """ SELECT
                    min(co.id) as id,
                    co.number,
                    co.customer_id,
                    co.mobile,
                    co.email,
                    co.sale_id,
                    co.serial_no_id,
                    co.warranty_period,
                    co.product_id,
                    co.waranty_type,
                    co.waranty_charges,
                    co.quantity,
                    co.uom_id,
                    co.date,
                    co.start_date,
                    co.end_date,
                    co.state,
                    co.currency_id,
                    co.user_id,
                    co.company_id,
                    co.invoice_id,
                    co.warranty_renewal,
                    co.warranty_renewal_id,
                    co.warranty_source,
                    co.rene_warranty_count,
                    co.warranty_details_id
        """
        return select_str

    def _from(self):
        from_str = """warranty_warranty co join res_partner cust on (co.customer_id = cust.id)"""
        return from_str

    def _group_by(self):
        group_by_str = """ GROUP BY
                    co.number,
                    co.customer_id,
                    co.mobile,
                    co.email,
                    co.sale_id,
                    co.serial_no_id,
                    co.warranty_period,
                    co.product_id,
                    co.waranty_type,
                    co.waranty_charges,
                    co.quantity,
                    co.uom_id,
                    co.date,
                    co.start_date,
                    co.end_date,
                    co.state,
                    co.currency_id,
                    co.user_id,
                    co.company_id,
                    co.invoice_id,
                    co.warranty_renewal,
                    co.warranty_renewal_id,
                    co.warranty_source,
                    co.rene_warranty_count,
                    co.warranty_details_id
        """
        return group_by_str

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (
            %s
            FROM ( %s ) %s
            )""" % (self._table, self._select(), self._from(), self._group_by()))

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
