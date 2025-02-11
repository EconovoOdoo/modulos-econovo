from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class stock_lot(models.Model):
    _inherit = 'stock.lot'
    
    warranty_period = fields.Integer(string='Warranty Period(In Months)')
    waranty_type = fields.Selection([('free','Free'),('paid','Paid')],string='Warranty Type')
    waranty_charges = fields.Float(string='Paid Charges')
    warranty_details_id = fields.Many2one("warranty.details",string="Warranty")
    
   
