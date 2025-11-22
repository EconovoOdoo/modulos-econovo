# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Vishnu K P (odoo@cybrosys.com)
#
#    Consolidated into econovo_user_warehouse_restriction by:
#    Jose D. Leonett (odoo@econovo.com)
#
#    This program is distributed under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3).
#
###############################################################################
from odoo import api, models


class StockPicking(models.Model):
    """Extends stock.picking to apply domain restrictions on location fields.
    
    v2.0 Architecture (Permission Matrix):
    - Filters locations based on warehouse.user.permission records
    - Respects blocked_location_ids (per-warehouse blacklist)
    - Considers allow_as_source and allow_as_destination permissions
    
    v1.0 Architecture (deprecated):
    - Filtered based on warehouse.user_ids Many2many
    - Global restriction (no per-warehouse granularity)
    
    Note: This only affects the domain (dropdown options). Record Rules
    handle the actual access control at database level.
    """
    _inherit = 'stock.picking'

    @api.onchange('location_id', 'location_dest_id')
    def _onchange_location_id(self):
        """Apply domain restrictions to location fields using permission matrix.
        
        v2.0 Logic:
        - Get user's permission records (warehouse.user.permission)
        - Filter locations based on:
          * allow_as_source (for location_id)
          * allow_as_destination (for location_dest_id)
          * blocked_location_ids (exclude blacklisted locations)
        
        Returns:
            dict: Domain definition for location fields with permission matrix filters
        """
        user = self.env.user
        
        # Bypass for superuser/unrestricted users
        if self.env.su or user.has_group('econovo_user_warehouse_restriction.group_warehouse_unrestricted'):
            return {}
        
        # Get user's permission records
        permissions = self.env['warehouse.user.permission'].search([
            ('user_id', '=', user.id)
        ])
        
        if not permissions:
            # No permissions = No access (block all locations)
            return {
                'domain': {
                    'location_id': [('id', '=', False)],  # Empty domain
                    'location_dest_id': [('id', '=', False)]  # Empty domain
                }
            }
        
        # ================================================================
        # SOURCE LOCATION DOMAIN (location_id)
        # ================================================================
        
        # Get warehouses where user has source permission
        source_warehouses = permissions.filtered(
            lambda p: p.allow_as_source or p.full_control
        ).mapped('warehouse_id')
        
        # Get blocked locations for source warehouses
        blocked_source_locations = permissions.filtered(
            lambda p: p.allow_as_source or p.full_control
        ).mapped('blocked_location_ids')
        
        source_domain = [
            ('warehouse_id', 'in', source_warehouses.ids),
            ('id', 'not in', blocked_source_locations.ids)
        ]
        
        # ================================================================
        # DESTINATION LOCATION DOMAIN (location_dest_id)
        # ================================================================
        
        # Get warehouses where user has destination permission
        dest_warehouses = permissions.filtered(
            lambda p: p.allow_as_destination or p.full_control
        ).mapped('warehouse_id')
        
        # Get blocked locations for destination warehouses
        blocked_dest_locations = permissions.filtered(
            lambda p: p.allow_as_destination or p.full_control
        ).mapped('blocked_location_ids')
        
        dest_domain = [
            ('warehouse_id', 'in', dest_warehouses.ids),
            ('id', 'not in', blocked_dest_locations.ids)
        ]
        
        return {
            'domain': {
                'location_id': source_domain,
                'location_dest_id': dest_domain
            }
        }
