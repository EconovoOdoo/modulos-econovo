# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ComexTributeInvoiceLineConfig(models.Model):
    """Configuration for tribute fields to include in invoice pre-fill.
    
    This model allows users to configure which tribute amounts should be
    included as lines when creating tribute invoices from customs clearances.
    Users can control the order, products, and descriptions for each line.
    """
    
    _name = 'comex.tribute.invoice.line.config'
    _description = 'COMEX Tribute Invoice Line Configuration'
    _order = 'company_id, sequence, id'
    
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in which tributes will appear in invoice lines",
    )
    
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Company for which this configuration applies",
    )
    
    tribute_field_id = fields.Many2one(
        'comex.tribute.field',
        string="Tribute Field",
        required=True,
        help="Tribute field to include in invoice",
    )
    
    product_id = fields.Many2one(
        'product.product',
        string="Override Product",
        domain="[('detailed_type', '=', 'service')]",
        help="Optional: Use this specific product instead of auto-detected from mappings",
    )
    
    include_if_zero = fields.Boolean(
        string="Include if Zero",
        default=False,
        help="Include this line even if amount is zero",
    )
    
    description = fields.Text(
        string="Custom Description",
        help="Optional: Override the default line description",
    )
    
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to temporarily disable this line configuration",
    )
