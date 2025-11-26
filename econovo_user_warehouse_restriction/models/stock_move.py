# -*- coding: utf-8 -*-
###############################################################################
#
#    Jose D. Leonett
#
#    Copyright (C) 2024-TODAY Jose D. Leonett
#    Author: Jose D. Leonett (odoo@econovo.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from odoo import api, models, _
from odoo.exceptions import ValidationError, UserError


class StockMove(models.Model):
    """Extends stock.move to add warehouse transfer validation.
    
    v2.0 Architecture (Permission Matrix):
    - Validates transfers using warehouse.user.permission records
    - Hierarchical validation: Warehouse access → Location blacklist → Operation permissions
    - Granular control: 10 permission flags per user/warehouse
    
    v1.0 Architecture (deprecated):
    - Validated using group inheritance (Source Only, Full)
    - Global location blacklist (user.location_ids)
    - Binary restriction levels
    
    Validation Rules (v2.0):
    1. Check warehouse access (allow_as_source, allow_as_destination)
    2. Check location blacklist (blocked_location_ids, allow_transit bypass)
    3. Check operation permissions (allow_create_picking, allow_write_picking)
    
    Superuser/Admin Bypass:
    - env.su: Automatic bypass
    - group_warehouse_unrestricted: Explicit bypass (assigned to base.group_system)
    """
    _inherit = 'stock.move'

    def _check_view_only_permission(self):
        """Check if user has view_only permission for this move's warehouse.
        
        Similar to stock.picking._check_view_only_permission but for stock.move.
        Validates against both source and destination warehouses.
        
        Raises:
            UserError: If user only has view_only permission (no write access)
        """
        user = self.env.user
        
        # Bypass for superuser/unrestricted users
        if self.env.su or user.has_group('econovo_user_warehouse_restriction.group_warehouse_unrestricted'):
            return
        
        for move in self:
            # Get warehouses from move locations
            source_warehouse = move.location_id.warehouse_id
            dest_warehouse = move.location_dest_id.warehouse_id
            
            # Check both warehouses
            warehouses_to_check = []
            if source_warehouse:
                warehouses_to_check.append(source_warehouse)
            if dest_warehouse and dest_warehouse != source_warehouse:
                warehouses_to_check.append(dest_warehouse)
            
            for warehouse in warehouses_to_check:
                # Get user's permission for this warehouse
                permission = self.env['warehouse.user.permission'].search([
                    ('user_id', '=', user.id),
                    ('warehouse_id', '=', warehouse.id)
                ], limit=1)
                
                if permission and permission.view_only and not permission.full_control:
                    raise UserError(_(
                        'You do not have permission to modify warehouse "%s".\n\n'
                        'Permission "view_only" is enabled for this warehouse.\n'
                        'Contact your administrator to grant write access.'
                    ) % warehouse.name)

    def write(self, vals):
        """Override write to check view_only permission."""
        self._check_view_only_permission()
        return super(StockMove, self).write(vals)

    def unlink(self):
        """Override unlink to check view_only permission."""
        self._check_view_only_permission()
        return super(StockMove, self).unlink()
    
    @api.constrains('location_id', 'location_dest_id')
    def _check_warehouse_transfer_permission(self):
        """Validates warehouse transfer permissions using permission matrix.
        
        v2.0 Validation Logic:
        - Uses warehouse.user.permission records instead of groups
        - Hierarchical: Warehouse access → Location blacklist → Operation
        - Per-warehouse granular control (10 flags)
        
        Validation Steps:
        1. Get user's permission record for source/destination warehouses
        2. Check allow_as_source permission (if source warehouse exists)
        3. Check allow_as_destination permission (if destination warehouse exists)
        4. Validate location blacklist (blocked_location_ids)
        5. Allow transit bypass (if allow_transit=True)
        
        Special Cases:
        - Transit locations: Bypass if allow_transit=True in permission
        - No warehouse: Allow (e.g., supplier → customer locations)
        - Full Control: Auto-grant all permissions (full_control=True)
        - View Only: Block all writes (view_only=True)
        
        Raises:
            ValidationError: When user attempts unauthorized transfer
        """
        PermissionModel = self.env['warehouse.user.permission']
        
        for move in self:
            user = self.env.user
            
            # ================================================================
            # BYPASS CONDITIONS
            # ================================================================
            
            # Skip validation for superuser
            if self.env.su:
                continue
            
            # Skip validation for users with unrestricted bypass group
            # This group is auto-assigned to base.group_system (administrators)
            if user.has_group('econovo_user_warehouse_restriction.group_warehouse_unrestricted'):
                continue
            
            # ================================================================
            # WAREHOUSE IDENTIFICATION
            # ================================================================
            
            source_warehouse = move.location_id.warehouse_id
            dest_warehouse = move.location_dest_id.warehouse_id
            
            # ================================================================
            # SOURCE WAREHOUSE VALIDATION
            # ================================================================
            
            if source_warehouse:
                # Get permission record for source warehouse
                source_permission = PermissionModel.search([
                    ('user_id', '=', user.id),
                    ('warehouse_id', '=', source_warehouse.id)
                ], limit=1)
                
                if not source_permission:
                    # No permission record = No access
                    raise ValidationError(
                        f"You do not have permission to transfer stock FROM warehouse '{source_warehouse.name}'.\n\n"
                        f"No permission record found for this warehouse.\n"
                        f"Contact your administrator to grant access."
                    )
                
                # Check if user has source permission
                if not source_permission.has_source_permission():
                    raise ValidationError(
                        f"You do not have permission to use warehouse '{source_warehouse.name}' as SOURCE.\n\n"
                        f"Permission 'allow_as_source' is disabled for this warehouse.\n"
                        f"Contact your administrator to grant source access."
                    )
                
                # Check location blacklist (unless transit bypass applies)
                if source_permission.is_location_blocked(move.location_id):
                    # Check if transit bypass applies
                    if move.location_id.is_transit_location and source_permission.allow_transit:
                        # Transit bypass - allow access
                        pass
                    else:
                        raise ValidationError(
                            f"You do not have permission to access location '{move.location_id.complete_name}'.\n\n"
                            f"This location is in your blacklist for warehouse '{source_warehouse.name}'.\n"
                            f"Contact your administrator to remove the restriction."
                        )
            
            # ================================================================
            # DESTINATION WAREHOUSE VALIDATION
            # ================================================================
            
            if dest_warehouse:
                # Get permission record for destination warehouse
                dest_permission = PermissionModel.search([
                    ('user_id', '=', user.id),
                    ('warehouse_id', '=', dest_warehouse.id)
                ], limit=1)
                
                if not dest_permission:
                    # No permission record = No access
                    raise ValidationError(
                        f"You do not have permission to transfer stock TO warehouse '{dest_warehouse.name}'.\n\n"
                        f"No permission record found for this warehouse.\n"
                        f"Contact your administrator to grant access."
                    )
                
                # Check if user has destination permission
                if not dest_permission.has_destination_permission():
                    raise ValidationError(
                        f"You do not have permission to use warehouse '{dest_warehouse.name}' as DESTINATION.\n\n"
                        f"Permission 'allow_as_destination' is disabled for this warehouse.\n"
                        f"Contact your administrator to grant destination access."
                    )
                
                # Check location blacklist (unless transit bypass applies)
                if dest_permission.is_location_blocked(move.location_dest_id):
                    # Check if transit bypass applies
                    if move.location_dest_id.is_transit_location and dest_permission.allow_transit:
                        # Transit bypass - allow access
                        pass
                    else:
                        raise ValidationError(
                            f"You do not have permission to access location '{move.location_dest_id.complete_name}'.\n\n"
                            f"This location is in your blacklist for warehouse '{dest_warehouse.name}'.\n"
                            f"Contact your administrator to remove the restriction."
                        )
