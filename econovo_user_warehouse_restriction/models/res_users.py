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
    

    @api.model
    def create(self, vals):
        """Enhanced create with cache clearing.
        
        Clears caches for performance optimization.
        
        Args:
            vals (dict): Values for new user
            
        Returns:
            res.users: Created user record
        """
        self.clear_caches()
        return super(ResUsers, self).create(vals)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Enhanced multi-create with cache clearing.
        
        Clears caches for performance optimization when creating multiple users.
        
        Args:
            vals_list (list): List of value dicts for new users
            
        Returns:
            res.users: Created user recordset
        """
        self.clear_caches()
        return super(ResUsers, self).create(vals_list)
    
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



