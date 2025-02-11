from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class product_product(models.Model):
    _inherit = 'product.template'
    
    allow_warranty = fields.Boolean(string='Allow Warranty')
    allow_warranty_renewal = fields.Boolean(string='Warranty Renewal',related="warranty_details_id.allow_warranty_renewal")
    renewal_time = fields.Integer(string='Renewal Time',related="warranty_details_id.renewal_time")
    warranty_period = fields.Integer(string='Warranty Period(In Months)',related="warranty_details_id.warranty_period")
    waranty_type = fields.Selection([('free','Free'),('paid','Paid')],string='Warranty Type',related="warranty_details_id.waranty_type")
    waranty_charges = fields.Float(string='Paid Charges',related="warranty_details_id.waranty_charges")
    warranty_details_id = fields.Many2one("warranty.details",string="Warranty")
    
    
   
   
        
