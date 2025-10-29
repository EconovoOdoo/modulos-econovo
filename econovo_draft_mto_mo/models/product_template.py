# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    mo_draft_policy = fields.Selection([
        ('use_global', 'Use Global Settings'),
        ('native_flow', 'Native Odoo Behavior'),
        ('always_draft', 'Always Keep Draft'),
        ('always_confirm', 'Always Auto-Confirm'),
        ('custom', 'Custom by Source Type'),
    ], string="MO Draft Policy", 
       default='use_global',
       help="Override global settings for Manufacturing Orders of this product:\n"
            "- Use Global Settings: Follow system-wide configuration\n"
            "- Native Odoo Behavior: Use Odoo's standard logic (ignore global settings)\n"
            "- Always Keep Draft: All MOs for this product stay in draft\n"
            "- Always Auto-Confirm: All MOs for this product auto-confirm\n"
            "- Custom by Source Type: Configure individually for MTO, MTS, MPS, and Orderpoint")
    
    # Custom Configuration per Source Type (only if policy == 'custom')
    mo_draft_mto = fields.Boolean(
        "MTO: Keep Draft",
        help="Manufacturing Orders from Sales Orders for this product"
    )
    
    mo_draft_mts = fields.Boolean(
        "MTS: Keep Draft",
        help="Manufacturing Orders for stock replenishment for this product"
    )
    
    mo_draft_mps = fields.Boolean(
        "MPS: Keep Draft",
        help="Manufacturing Orders from Master Production Schedule for this product"
    )
    
    mo_draft_orderpoint = fields.Boolean(
        "Orderpoint: Keep Draft",
        help="Manufacturing Orders from Reordering Rules for this product"
    )
