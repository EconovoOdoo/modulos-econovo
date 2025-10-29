# -*- coding: utf-8 -*-

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'
    
    mo_draft_policy = fields.Selection([
        ('use_global', 'Use Global/Product Settings'),
        ('native_flow', 'Native Odoo Behavior'),
        ('always_draft', 'Always Keep Draft'),
        ('always_confirm', 'Always Auto-Confirm'),
        ('custom', 'Custom by Source Type'),
    ], string="MO Draft Policy", 
       default='use_global',
       help="Override global/product settings for MOs created by this user:\n"
            "- Use Global/Product Settings: Follow system and product configuration\n"
            "- Native Odoo Behavior: Use Odoo's standard logic (ignore other settings)\n"
            "- Always Keep Draft: All MOs created by this user stay in draft\n"
            "- Always Auto-Confirm: All MOs created by this user auto-confirm\n"
            "- Custom by Source Type: Configure individually for MTO, MTS, MPS, and Orderpoint")
    
    # Custom Configuration per Source Type (only if policy == 'custom')
    mo_draft_mto = fields.Boolean(
        "MTO: Keep Draft",
        help="Manufacturing Orders from Sales Orders created by this user"
    )
    
    mo_draft_mts = fields.Boolean(
        "MTS: Keep Draft",
        help="Manufacturing Orders for stock replenishment created by this user"
    )
    
    mo_draft_mps = fields.Boolean(
        "MPS: Keep Draft",
        help="Manufacturing Orders from Master Production Schedule created by this user"
    )
    
    mo_draft_orderpoint = fields.Boolean(
        "Orderpoint: Keep Draft",
        help="Manufacturing Orders from Reordering Rules created by this user"
    )
