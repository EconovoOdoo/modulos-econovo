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
from odoo import api, models
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    """Extends stock.move to add warehouse transfer validation.
    
    Validates that users with warehouse restrictions cannot transfer stock
    to warehouses they don't have access to, unless:
    - They have the 'allow_cross_warehouse_transfers' permission
    - The destination is a transit warehouse or location
    - They belong to the 'Source Only' restriction group
    """
    _inherit = 'stock.move'
    
    @api.constrains('location_id', 'location_dest_id')
    def _check_warehouse_transfer_permission(self):
        """Validates warehouse transfer permissions for restricted users.
        
        This constraint ensures that users with warehouse restrictions
        cannot bypass security by selecting unauthorized destinations in transfers.
        
        Raises:
            ValidationError: When user attempts unauthorized cross-warehouse transfer
        """
        for move in self:
            user = self.env.user
            
            # Skip validation for users with cross-warehouse permission
            if user.allow_cross_warehouse_transfers:
                continue
            
            # Skip validation for superuser and system admins
            if self.env.su or user.has_group('base.group_system'):
                continue
            
            # Skip validation if user belongs to Source Only restriction group
            if user.has_group('econovo_user_warehouse_restriction.group_warehouse_restriction_source_only'):
                continue
            
            # Skip validation if user does not have warehouse restriction enabled
            if not user.has_group('user_warehouse_restriction.user_warehouse_restriction_group_user'):
                continue
            
            # Get source and destination warehouses
            source_warehouse = move.location_id.warehouse_id
            dest_warehouse = move.location_dest_id.warehouse_id
            
            # Get user's allowed warehouses
            allowed_warehouses = self.env['stock.warehouse'].search([
                ('user_ids', 'in', user.id)
            ])
            
            # Validate SOURCE warehouse access (unless it's a transit location)
            if source_warehouse and source_warehouse not in allowed_warehouses:
                # Allow if source is a transit warehouse
                if not source_warehouse.is_transit_warehouse:
                    # Allow if source is a transit location
                    if not move.location_id.is_transit_location:
                        raise ValidationError(
                            f"You do not have permission to transfer stock from warehouse '{source_warehouse.name}'.\n\n"
                            f"Your allowed warehouses are: {', '.join(allowed_warehouses.mapped('name'))}\n\n"
                            f"If you need access to additional warehouses, please contact your system administrator."
                        )
            
            # Validate DESTINATION warehouse access (unless it's a transit location)
            if dest_warehouse and dest_warehouse not in allowed_warehouses:
                # Allow if destination is a transit warehouse
                if not dest_warehouse.is_transit_warehouse:
                    # Allow if destination is a transit location
                    if not move.location_dest_id.is_transit_location:
                        raise ValidationError(
                            f"You do not have permission to transfer stock to warehouse '{dest_warehouse.name}'.\n\n"
                            f"Your allowed warehouses are: {', '.join(allowed_warehouses.mapped('name'))}\n\n"
                            f"If you need access to additional warehouses, please contact your system administrator."
                        )
