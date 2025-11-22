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


class StockWarehouse(models.Model):
    """Extends stock.warehouse with granular user-based warehouse restrictions.
    
    Permission Matrix System:
    - user_permission_ids: One2many to warehouse.user.permission
    - Flexible per-user permissions with 10 granular flags
    - Each user can have different access levels in different warehouses
    - Per-warehouse location blacklists for fine-grained control
    """
    _inherit = "stock.warehouse"
    
    user_permission_ids = fields.One2many(
        'warehouse.user.permission',
        'warehouse_id',
        string='User Permissions',
        help='Granular permission matrix: configure different access levels per user.\n\n'
             'Each user can have:\n'
             '- Full Control (complete access)\n'
             '- View Only (read-only)\n'
             '- Granular permissions (Source, Destination, Inventory, etc.)\n'
             '- Location restrictions (blacklist specific locations)\n\n'
             'Example: User A has Full Control, User B can only receive (Destination).'
    )
    


    @api.model_create_multi
    def create(self, vals_list):
        """Create warehouses with automatic admin permission assignment.
        
        Automatically assigns Full Control permissions to system administrators
        when creating new warehouses, preventing lockout scenarios.
        
        Args:
            vals_list: List of dictionaries with warehouse values
            
        Returns:
            stock.warehouse recordset
        """
        warehouses = super().create(vals_list)
        
        # Check if warehouse restriction is enabled
        restriction_enabled = self.env['ir.config_parameter'].sudo().get_param(
            'econovo_user_warehouse_restriction.group_user_warehouse_restriction',
            default=False
        )
        
        if restriction_enabled:
            # Get all system administrators
            admin_group = self.env.ref('base.group_system', raise_if_not_found=False)
            if admin_group:
                admins = self.env['res.users'].search([
                    ('groups_id', 'in', [admin_group.id]),
                    ('share', '=', False),  # Internal users only
                ])
                
                # Create permission records for admins with Full Control
                for warehouse in warehouses:
                    for admin in admins:
                        # Check if permission doesn't exist already
                        existing = self.env['warehouse.user.permission'].search([
                            ('warehouse_id', '=', warehouse.id),
                            ('user_id', '=', admin.id)
                        ], limit=1)
                        
                        if not existing:
                            self.env['warehouse.user.permission'].create({
                                'warehouse_id': warehouse.id,
                                'user_id': admin.id,
                                'full_control': True,
                                'active': True,
                            })
        
        return warehouses

    def write(self, vals):
        """Standard write method.
        
        Args:
            vals: Dictionary with field values to update
            
        Returns:
            bool: Result of super().write()
        """
        return super(StockWarehouse, self).write(vals)
    
    def action_open_users_view(self):
        """Open permission matrix configuration for this warehouse.
        
        Returns:
            dict: Action definition for opening permission matrix
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'User Permissions: {self.name}',
            'view_mode': 'tree,form',
            'res_model': 'warehouse.user.permission',
            'domain': [('warehouse_id', '=', self.id)],
            'context': {
                'default_warehouse_id': self.id,
                'tree_view_ref': 'econovo_user_warehouse_restriction.warehouse_user_permission_tree_view',
            }
        }
    

