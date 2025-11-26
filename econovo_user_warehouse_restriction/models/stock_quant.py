# -*- coding: utf-8 -*-
"""
Stock Quant extensions for warehouse user restrictions.
Implements allow_inventory_adjustment permission checks.
"""
from odoo import _, api, models
from odoo.exceptions import UserError


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _check_inventory_adjustment_permission(self):
        """Check if user has permission to make inventory adjustments.
        
        Validates:
        - User is not in superuser mode (bypass)
        - User has allow_inventory_adjustment permission for the warehouse
        """
        if self.env.su:
            return
        
        user = self.env.user
        
        # Check if user is in unrestricted group
        unrestricted_group = self.env.ref(
            'econovo_user_warehouse_restriction.group_warehouse_unrestricted',
            raise_if_not_found=False
        )
        if unrestricted_group and user.has_group(
            'econovo_user_warehouse_restriction.group_warehouse_unrestricted'
        ):
            return
        
        for quant in self:
            location = quant.location_id
            if not location:
                continue
            
            # Get warehouse from location
            warehouse = location.warehouse_id
            if not warehouse:
                # Try to get warehouse from parent locations
                parent = location.location_id
                while parent and not warehouse:
                    warehouse = parent.warehouse_id
                    parent = parent.location_id
            
            if not warehouse:
                continue
            
            # Check user permission for this warehouse
            permission = self.env['warehouse.user.permission'].sudo().search([
                ('user_id', '=', user.id),
                ('warehouse_id', '=', warehouse.id),
                ('active', '=', True),
            ], limit=1)
            
            if not permission:
                raise UserError(_(
                    'You do not have any permissions configured for warehouse "%s".\n\n'
                    'Inventory adjustment requires "allow_inventory_adjustment" permission.\n'
                    'Contact your administrator to configure your permissions.'
                ) % warehouse.name)
            
            # Check if user has full control (bypass granular permissions)
            if permission.full_control:
                continue
            
            # Check view_only (blocks all write operations)
            if permission.view_only:
                raise UserError(_(
                    'You have view-only access to warehouse "%s".\n\n'
                    'Inventory adjustments are not allowed in view-only mode.'
                ) % warehouse.name)
            
            # Check allow_inventory_adjustment
            if not permission.allow_inventory_adjustment:
                raise UserError(_(
                    'You do not have permission to make inventory adjustments in warehouse "%s".\n\n'
                    'Permission "allow_inventory_adjustment" is disabled for this warehouse.\n'
                    'Contact your administrator to grant this permission.'
                ) % warehouse.name)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to check inventory adjustment permission."""
        result = super(StockQuant, self).create(vals_list)
        # Check permission after creation to have location_id available
        if not self.env.context.get('inventory_mode'):
            # Only check in inventory mode operations
            pass
        return result

    def write(self, vals):
        """Override write to check inventory adjustment permission when quantity changes."""
        # Only check permission if quantity is being modified
        if 'inventory_quantity' in vals or 'inventory_quantity_set' in vals:
            self._check_inventory_adjustment_permission()
        return super(StockQuant, self).write(vals)

    def action_apply_inventory(self):
        """Override action_apply_inventory to check permission."""
        self._check_inventory_adjustment_permission()
        return super(StockQuant, self).action_apply_inventory()
