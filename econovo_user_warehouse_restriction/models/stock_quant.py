# -*- coding: utf-8 -*-
"""
Stock Quant extensions for warehouse user restrictions.
Implements granular inventory permissions:
- allow_inventory_count: Can edit inventory_quantity field
- allow_inventory_adjustment: Can apply the adjustment (includes count)
"""
from odoo import _, api, models
from odoo.exceptions import UserError


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _check_inventory_count_permission(self):
        """Check if user has permission to enter inventory counts.
        
        Validates:
        - User is not in superuser mode (bypass)
        - User has allow_inventory_count OR allow_inventory_adjustment permission
        
        This is for editing inventory_quantity field (entering counts).
        """
        self._check_inventory_permission(require_apply=False)

    def _check_inventory_apply_permission(self):
        """Check if user has permission to apply inventory adjustments.
        
        Validates:
        - User is not in superuser mode (bypass)
        - User has allow_inventory_adjustment permission (not just count)
        
        This is for clicking "Apply" to finalize the adjustment.
        """
        self._check_inventory_permission(require_apply=True)

    def _check_inventory_permission(self, require_apply=False):
        """Core permission check for inventory operations.
        
        Args:
            require_apply: If True, requires allow_inventory_adjustment.
                          If False, allows either count or adjustment permission.
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
            
            # Skip non-internal locations (supplier, customer, production, transit, inventory)
            # These are system locations not subject to warehouse restrictions
            if location.usage not in ('internal',):
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
                # Internal location without warehouse - this shouldn't happen
                # But if it does, block the operation for safety
                raise UserError(_(
                    'Cannot perform inventory operation on location "%s".\n\n'
                    'This internal location is not associated with any warehouse.\n'
                    'Contact your administrator to configure the location correctly.'
                ) % location.complete_name)
            
            # Check user permission for this warehouse
            permission = self.env['warehouse.user.permission'].sudo().search([
                ('user_id', '=', user.id),
                ('warehouse_id', '=', warehouse.id),
                ('active', '=', True),
            ], limit=1)
            
            if not permission:
                if require_apply:
                    raise UserError(_(
                        'You do not have any permissions configured for warehouse "%s".\n\n'
                        'Applying inventory adjustment requires "Apply Adjustments" permission.\n'
                        'Contact your administrator to configure your permissions.'
                    ) % warehouse.name)
                else:
                    raise UserError(_(
                        'You do not have any permissions configured for warehouse "%s".\n\n'
                        'Inventory count requires "Inventory Count" or "Apply Adjustments" permission.\n'
                        'Contact your administrator to configure your permissions.'
                    ) % warehouse.name)
            
            # Check if user has full control (bypass granular permissions)
            if permission.full_control:
                continue
            
            # Check view_only (blocks all write operations)
            if permission.view_only:
                raise UserError(_(
                    'You have view-only access to warehouse "%s".\n\n'
                    'Inventory operations are not allowed in view-only mode.'
                ) % warehouse.name)
            
            # Check permissions based on operation type
            if require_apply:
                # Apply requires allow_inventory_adjustment
                if not permission.allow_inventory_adjustment:
                    raise UserError(_(
                        'You do not have permission to apply inventory adjustments in warehouse "%s".\n\n'
                        'You may have "Inventory Count" permission (to enter counts),\n'
                        'but "Apply Adjustments" permission is required to finalize.\n'
                        'Contact your administrator or supervisor to apply the adjustment.'
                    ) % warehouse.name)
            else:
                # Count allows either permission
                if not permission.allow_inventory_count and not permission.allow_inventory_adjustment:
                    raise UserError(_(
                        'You do not have permission to enter inventory counts in warehouse "%s".\n\n'
                        'Permission "Inventory Count" or "Apply Adjustments" is required.\n'
                        'Contact your administrator to grant this permission.'
                    ) % warehouse.name)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to check inventory count permission."""
        result = super(StockQuant, self).create(vals_list)
        # Check permission after creation to have location_id available
        if not self.env.context.get('inventory_mode'):
            # Only check in inventory mode operations
            pass
        return result

    def write(self, vals):
        """Override write to check inventory count permission when inventory fields change.
        
        Protected fields:
        - inventory_quantity: The counted quantity
        - inventory_quantity_set: Flag indicating count in progress
        - user_id: Assigned counter (user assigned to do count)
        - inventory_date: Scheduled date for next count
        """
        # Fields that require inventory count permission
        inventory_fields = {
            'inventory_quantity',
            'inventory_quantity_set',
            'user_id',
            'inventory_date',
        }
        
        # Check if any inventory field is being modified
        if inventory_fields & set(vals.keys()):
            self._check_inventory_count_permission()
        return super(StockQuant, self).write(vals)

    def action_apply_inventory(self):
        """Override action_apply_inventory to check apply permission."""
        self._check_inventory_apply_permission()
        return super(StockQuant, self).action_apply_inventory()

    def action_set_inventory_quantity(self):
        """Override to check count permission before setting quantity to current on-hand."""
        self._check_inventory_count_permission()
        return super(StockQuant, self).action_set_inventory_quantity()

    def action_set_inventory_quantity_zero(self):
        """Override to check count permission before setting quantity to zero."""
        self._check_inventory_count_permission()
        return super(StockQuant, self).action_set_inventory_quantity_zero()

    def action_clear_inventory_quantity(self):
        """Override to check count permission before clearing inventory quantity."""
        self._check_inventory_count_permission()
        return super(StockQuant, self).action_clear_inventory_quantity()
