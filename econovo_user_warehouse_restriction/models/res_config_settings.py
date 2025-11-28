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
import logging
from odoo import api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """Adds warehouse restriction settings to Inventory configuration.
    
    Provides a boolean setting to enable/disable warehouse restrictions
    globally. When enabled, automatically assigns the current user to
    all warehouses to prevent lockout.
    """
    _inherit = 'res.config.settings'

    group_user_warehouse_restriction = fields.Boolean(
        string="Restrict Stock Warehouse",
        implied_group='econovo_user_warehouse_restriction.user_warehouse_restriction_group_user',
        help="Enable to restrict warehouses and locations to specific users.\n\n"
             "When enabled, users must be explicitly assigned to warehouses via "
             "warehouse.user_ids to access inventory operations."
    )

    @api.onchange('group_user_warehouse_restriction')
    def _onchange_group_user_warehouse_restriction(self):
        """Auto-assign current user to all warehouses when restriction is enabled.
        
        This prevents the user from being locked out of all warehouses when
        enabling the restriction setting for the first time.
        
        Behavior:
        - When restriction enabled: Assigns current user to ALL warehouses (all companies)
        - When restriction disabled: Clears user assignments from ALL warehouses
        
        CRITICAL: Must search warehouses across ALL companies, not just current context.
        Otherwise, if user enables restriction with only Company A selected, they will
        NOT be assigned to Company B warehouses, causing lockout when switching companies.
        
        Note: Temporarily disables operation_type_rule to avoid access issues
        during the update process.
        """
        # Temporarily disable operation type rule to avoid access issues
        rule = self.env.ref(
            'econovo_user_warehouse_restriction.operation_type_rule_users',
            raise_if_not_found=False
        )
        if rule:
            rule.active = False
        
        try:
            # CRITICAL: Search ALL warehouses regardless of current company context
            # This prevents lockout when user switches companies after enabling restriction
            warehouses = self.env['stock.warehouse'].with_context(active_test=False).search([
                '|', ('company_id', '=', False), ('company_id', 'in', self.env.user.company_ids.ids)
            ])
            
            for warehouse in warehouses:
                if self.group_user_warehouse_restriction:
                    # Assign current user to each warehouse
                    if not warehouse.user_ids:
                        warehouse.user_ids = [(6, 0, [self.env.user.id])]
                else:
                    # Clear allowed users for each warehouse
                    warehouse.user_ids = [(5, 0, 0)]
        
        except AccessError as e:
            _logger.warning(f"Access error occurred while updating warehouses: {e}")
        
        finally:
            # Re-enable the rule
            if rule:
                rule.active = True
