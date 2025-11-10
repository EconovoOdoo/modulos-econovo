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
from odoo import api, fields, models


class StockWarehouse(models.Model):
    """Extends stock.warehouse to add additional security rules for Econovo.
    
    This extension overrides the base module's write() method to allow
    administrators to configure warehouse access without the restrictive
    self-removal validation, while maintaining security for regular users.
    
    It also provides automatic user assignment during module installation.
    """
    _inherit = "stock.warehouse"
    
    is_transit_warehouse = fields.Boolean(
        string="Transit/Shared Warehouse",
        default=False,
        help="If enabled, this warehouse is accessible by all users for transit operations, "
             "even if they are not explicitly assigned to it.\n\n"
             "Useful for inter-warehouse transfers where users need to send/receive stock "
             "through a shared transit location without having direct access to other warehouses.\n\n"
             "Example: User1 (WH1) → Transit WH → User2 (WH2)"
    )

    def write(self, vals):
        """Override to allow bypassing the self-removal validation during 
        module installation or when user has system privileges.
        
        The base user_warehouse_restriction module prevents users from removing
        themselves from warehouse.user_ids. This is problematic for:
        - Initial module installation (no users assigned yet)
        - Administrator configuration (need flexibility)
        - Automated processes
        
        This override allows bypass when:
        1. User is administrator (base.group_system)
        2. Context flag 'skip_user_validation' is set
        3. Running in superuser mode
        4. During installation/upgrade (install_mode context)
        
        For regular users without these privileges, the base module's
        validation still applies for security.
        """
        current_user = self.env.user
        
        # Determine if we should bypass the base module's validation
        bypass_validation = (
            self.env.su or  # Superuser mode (internal Odoo operations)
            current_user.has_group('base.group_system') or  # Administrator
            self._context.get('skip_user_validation') or  # Explicit flag
            self._context.get('install_mode')  # Module installation/upgrade
        )
        
        if bypass_validation:
            # Call the original Model.write to bypass any overridden
            # validation implemented by other modules (e.g. user_warehouse_restriction).
            # Using models.Model.write ensures we execute the core write
            # and avoid the base module's self-removal check.
            return models.Model.write(self, vals)
        
        # Normal flow - base module validation applies for regular users
        return super(StockWarehouse, self).write(vals)

    @api.model
    def _assign_installer_to_warehouses(self):
        """Assign current user to all warehouses during module installation.
        
        This method is called automatically during module installation via
        data/warehouse_user_assignment.xml to prevent ValidationError when
        the base module tries to validate warehouse access.
        
        Without this, installing the module on a database with existing
        warehouses would fail because:
        1. No users are assigned to warehouses yet
        2. Record rules block access to warehouses
        3. Base module validation prevents configuration
        
        By auto-assigning the installer (usually admin), we ensure:
        - Smooth installation process
        - At least one user has access to configure further
        - No manual intervention needed post-install
        """
        current_user = self.env.user
        
        # Only run if user is administrator
        if not current_user.has_group('base.group_system'):
            return
        
        # Get all warehouses using context flag to bypass validation
        warehouses = self.with_context(
            skip_user_validation=True
        ).search([])

        # Add current user to all warehouses if not already present
        for warehouse in warehouses:
            if current_user not in warehouse.user_ids:
                # Ensure the write is executed with the bypass context so
                # the base module's validation does not block the install.
                warehouse.with_context(skip_user_validation=True).write({
                    'user_ids': [(4, current_user.id)]
                })
