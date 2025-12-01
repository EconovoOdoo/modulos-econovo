# -*- coding: utf-8 -*-
###############################################################################
#
#    Jose D. Leonett
#
#    Copyright (C) 2024-TODAY Jose D. Leonett
#    Author: Jose D. Leonett (odoo@econovo.com)
#
#    This program is distributed under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3).
#
###############################################################################
from odoo import api, fields, models, _


class BypassInfoWizard(models.TransientModel):
    """Wizard to display bypass permissions information.
    
    Shows detailed explanation when a user has system-level privileges
    that bypass warehouse restrictions.
    """
    _name = 'warehouse.bypass.info.wizard'
    _description = 'Bypass Permissions Information'
    
    user_name = fields.Char(
        string='User Name',
        readonly=True,
        help='Name of the user with bypass permissions.'
    )
    
    bypass_reason = fields.Char(
        string='Bypass Reason',
        readonly=True,
        help='Type of bypass permission (System Administrator, Unrestricted Access).'
    )
    
    info_html = fields.Html(
        string='Information',
        readonly=True,
        sanitize=False,
        help='Detailed explanation about bypass permissions.'
    )
    
    @api.model
    def action_show_info(self, user_name, bypass_reason):
        """Create wizard and show modal dialog.
        
        Args:
            user_name: Name of user with bypass
            bypass_reason: Type of bypass permission
            
        Returns:
            dict: Action to open wizard dialog
        """
        # Translatable strings
        title_detected = _("System-Level Access Detected")
        user_has = _("User %s has %s privileges.")
        what_means = _("What does this mean?")
        can_access_all = _("This user can access ALL warehouses regardless of the permissions configured in the permission matrix.")
        info_only = _("The permissions you configure here are informational only and will NOT restrict this user's access.")
        auto_bypass = _("Security rules automatically grant full bypass to system administrators.")
        how_to_apply = _("How to apply these restrictions?")
        to_enforce = _("To enforce warehouse restrictions for this user:")
        go_to = _("Go to: Settings → Users & Companies → Users")
        select_user = _("Select user: %s")
        open_access = _("Open Access Rights tab")
        remove_groups = _("Remove the following groups:")
        admin_settings = _("Administration / Settings")
        unrestricted_access = _("Unrestricted Warehouse Access")
        if_present = _("(if present)")
        note_label = _("Note:")
        note_text = _("Removing system administrator access will also restrict other administrative functions.")
        
        info_html = f"""
            <div class="alert alert-warning" role="alert">
                <h4><i class="fa fa-shield"></i> {title_detected}</h4>
                <p>{user_has % (user_name, bypass_reason)}</p>
            </div>
            
            <h5><i class="fa fa-question-circle"></i> {what_means}</h5>
            <ul>
                <li>{can_access_all}</li>
                <li>{info_only}</li>
                <li>{auto_bypass}</li>
            </ul>
            
            <hr/>
            
            <h5><i class="fa fa-wrench"></i> {how_to_apply}</h5>
            <p>{to_enforce}</p>
            <ol>
                <li>{go_to}</li>
                <li>{select_user % user_name}</li>
                <li>{open_access}</li>
                <li>{remove_groups}
                    <ul>
                        <li><em>{admin_settings}</em> (base.group_system)</li>
                        <li><em>{unrestricted_access}</em> {if_present}</li>
                    </ul>
                </li>
            </ol>
            
            <div class="alert alert-info" role="alert">
                <i class="fa fa-info-circle"></i> <strong>{note_label}</strong> 
                {note_text}
            </div>
        """
        
        wizard = self.create({
            'user_name': user_name,
            'bypass_reason': bypass_reason,
            'info_html': info_html,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('System-Level Bypass Active'),
            'res_model': 'warehouse.bypass.info.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
