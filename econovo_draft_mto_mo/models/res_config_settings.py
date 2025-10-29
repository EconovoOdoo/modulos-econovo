# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # Global Policy
    mo_draft_global_policy = fields.Selection([
        ('native_flow', 'Native Odoo Behavior'),
        ('always_draft', 'All MOs stay in Draft'),
        ('custom', 'Custom by Source Type'),
    ], string="Global MO Draft Policy", 
       default='native_flow',
       config_parameter='econovo_draft_mto_mo.global_policy',
       help="Control when Manufacturing Orders should stay in Draft state:\n"
            "- Native Odoo Behavior: Use Odoo's standard logic (auto-confirm based on context)\n"
            "- All MOs stay in Draft: Never auto-confirm, always require manual confirmation\n"
            "- Custom by Source Type: Configure individually for MTO, MTS, MPS, and Orderpoint")
    
    # Custom Configuration per Source Type (only if policy == 'custom')
    mo_draft_mto = fields.Boolean(
        "MTO: Keep Draft",
        config_parameter='econovo_draft_mto_mo.draft_for_mto',
        default=True,
        help="Manufacturing Orders triggered from Sales Orders (Make To Order)\n"
             "When enabled: MO stays in draft and requires manual confirmation\n"
             "When disabled: MO follows Odoo's native auto-confirm logic"
    )
    
    mo_draft_mts = fields.Boolean(
        "MTS: Keep Draft",
        config_parameter='econovo_draft_mto_mo.draft_for_mts',
        default=False,
        help="Manufacturing Orders for stock replenishment (Make To Stock)\n"
             "When enabled: MO stays in draft and requires manual confirmation\n"
             "When disabled: MO follows Odoo's native auto-confirm logic"
    )
    
    mo_draft_mps = fields.Boolean(
        "MPS: Keep Draft",
        config_parameter='econovo_draft_mto_mo.draft_for_mps',
        default=False,
        help="Manufacturing Orders from Master Production Schedule\n"
             "When enabled: MO stays in draft and requires manual confirmation\n"
             "When disabled: MO follows Odoo's native auto-confirm logic"
    )
    
    mo_draft_orderpoint = fields.Boolean(
        "Orderpoint: Keep Draft",
        config_parameter='econovo_draft_mto_mo.draft_for_orderpoint',
        default=False,
        help="Manufacturing Orders from Reordering Rules (Min/Max stock rules)\n"
             "When enabled: MO stays in draft and requires manual confirmation\n"
             "When disabled: MO follows Odoo's native auto-confirm logic"
    )
