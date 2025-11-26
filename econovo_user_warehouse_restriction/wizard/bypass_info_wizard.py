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
from odoo import api, fields, models


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
        info_html = f"""
            <div class="alert alert-warning" role="alert">
                <h4><i class="fa fa-shield"></i> System-Level Access Detected</h4>
                <p>User <strong>{user_name}</strong> has 
                <strong>{bypass_reason}</strong> privileges.</p>
            </div>
            
            <h5><i class="fa fa-question-circle"></i> What does this mean?</h5>
            <ul>
                <li>This user can access <strong>ALL warehouses</strong> regardless of 
                the permissions configured in the permission matrix.</li>
                <li>The permissions you configure here are <strong>informational only</strong> 
                and will NOT restrict this user's access.</li>
                <li>Security rules automatically grant full bypass to system administrators.</li>
            </ul>
            
            <hr/>
            
            <h5><i class="fa fa-wrench"></i> How to apply these restrictions?</h5>
            <p>To enforce warehouse restrictions for this user:</p>
            <ol>
                <li>Go to: <strong>Settings → Users &amp; Companies → Users</strong></li>
                <li>Select user: <strong>{user_name}</strong></li>
                <li>Open <strong>Access Rights</strong> tab</li>
                <li>Remove the following groups:
                    <ul>
                        <li><em>Administration / Settings</em> (base.group_system)</li>
                        <li><em>Unrestricted Warehouse Access</em> (if present)</li>
                    </ul>
                </li>
            </ol>
            
            <div class="alert alert-info" role="alert">
                <i class="fa fa-info-circle"></i> <strong>Note:</strong> 
                Removing system administrator access will also restrict other 
                administrative functions.
            </div>
        """
        
        wizard = self.create({
            'user_name': user_name,
            'bypass_reason': bypass_reason,
            'info_html': info_html,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'System-Level Bypass Active',
            'res_model': 'warehouse.bypass.info.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
