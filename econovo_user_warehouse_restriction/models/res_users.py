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
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    """Extends res.users with warehouse-based access restrictions.
    
    Permission Matrix Architecture:
    - warehouse_permission_ids: One2many to warehouse.user.permission
    - Granular per-warehouse permissions (10 flags per warehouse)
    - Flexible permission matrix replacing rigid group-based inheritance
    
    Core Features:
    - Cache clearing on create/write for performance
    - Secure-by-default: Auto-assigns restriction group to new users
    - Least privilege principle: Users start with ZERO warehouse access
    - System administrators excluded from auto-assignment
    - Portal/public users excluded
    
    Note: Use warehouse.user_permission records to grant granular access.
    """
    _inherit = 'res.users'
    
    warehouse_permission_ids = fields.One2many(
        comodel_name='warehouse.user.permission',
        inverse_name='user_id',
        string='Warehouse Permissions',
        help='Granular permission matrix per warehouse.\n\n'
             'Each record defines specific permissions for one warehouse.'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Enhanced multi-create with automatic restriction group assignment.
        
        Automatically assigns warehouse restriction group to new inventory users.
        System administrators are excluded from auto-assignment.
        
        Args:
            vals_list (list): List of value dicts for new users
            
        Returns:
            res.users: Created user recordset
        """
        # Create users first
        users = super(ResUsers, self).create(vals_list)
        
        # Get restriction group
        restriction_group = self.env.ref(
            'econovo_user_warehouse_restriction.user_warehouse_restriction_group_user',
            raise_if_not_found=False
        )
        
        if restriction_group:
            # Get system admin group
            admin_group = self.env.ref('base.group_system', raise_if_not_found=False)
            inventory_group = self.env.ref('stock.group_stock_user', raise_if_not_found=False)
            
            for user in users:
                # Only assign to internal users with inventory access
                # Exclude system administrators
                is_internal = not user.share
                has_inventory = inventory_group and inventory_group in user.groups_id
                is_admin = admin_group and admin_group in user.groups_id
                
                if is_internal and has_inventory and not is_admin:
                    # Auto-assign restriction group
                    if restriction_group not in user.groups_id:
                        user.write({'groups_id': [(4, restriction_group.id)]})
                        _logger.info(
                            f"Auto-assigned warehouse restriction group to new user: {user.name}"
                        )
        
        self.clear_caches()
        return users
    
    def write(self, vals):
        """Enhanced write with cache clearing.
        
        Clears caches for performance optimization after user updates.
        
        Args:
            vals (dict): Values to write
            
        Returns:
            bool: True if write succeeded
        """
        self.clear_caches()
        return super(ResUsers, self).write(vals)



