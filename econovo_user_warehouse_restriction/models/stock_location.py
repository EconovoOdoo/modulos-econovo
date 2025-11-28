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


class StockLocation(models.Model):
    """Extends stock.location to add transit/shared location flag.
    
    Transit locations are accessible by all users regardless of their
    warehouse assignments, enabling flexible stock movement workflows
    through shared spaces.
    """
    _inherit = "stock.location"
    
    is_transit_location = fields.Boolean(
        string="Transit/Shared Location",
        default=False,
        help="If enabled, this location is accessible by all users for transit operations, "
             "regardless of their warehouse assignments.\n\n"
             "Useful for creating shared spaces where users from different warehouses "
             "can temporarily store or transfer stock without requiring access to each other's warehouses.\n\n"
             "CRITICAL: Must enable this for transit locations. Without it, stock move lines "
             "will be filtered out by Record Rules when picking locations reference transit areas.\n\n"
             "Example: A shared dock location where User1 drops off stock for User2 to pick up."
    )
    
    blocked_user_permission_count = fields.Integer(
        string="Blocked By Users",
        compute='_compute_blocked_user_permission_count',
        help="Number of user permissions that have this location blocked."
    )
    
    @api.depends_context('uid')
    def _compute_blocked_user_permission_count(self):
        """Count permissions that have this location in their blocked list."""
        Permission = self.env['warehouse.user.permission']
        for location in self:
            location.blocked_user_permission_count = Permission.search_count([
                ('blocked_location_ids', 'in', location.id)
            ])
    
    def action_view_blocked_users(self):
        """Open view showing user permissions that block this location."""
        self.ensure_one()
        permissions = self.env['warehouse.user.permission'].search([
            ('blocked_location_ids', 'in', self.id)
        ])
        return {
            'name': f"Users Blocked from: {self.display_name}",
            'type': 'ir.actions.act_window',
            'res_model': 'warehouse.user.permission',
            'view_mode': 'tree,form',
            'views': [
                (self.env.ref('econovo_user_warehouse_restriction.warehouse_user_permission_tree_view').id, 'tree'),
                (self.env.ref('econovo_user_warehouse_restriction.warehouse_user_permission_form_view').id, 'form'),
            ],
            'domain': [('id', 'in', permissions.ids)],
            'context': {
                'default_blocked_location_ids': [(4, self.id)],
            },
            'target': 'current',
        }
    
    def action_add_to_blocked_locations(self):
        """Open wizard to add this location to existing user permissions' blocked list."""
        self.ensure_one()
        return {
            'name': f"Block Location: {self.display_name}",
            'type': 'ir.actions.act_window',
            'res_model': 'warehouse.user.permission',
            'view_mode': 'tree',
            'domain': [
                ('warehouse_id', '=', self.warehouse_id.id),
                ('blocked_location_ids', 'not in', self.id),
                ('full_control', '=', False),
            ],
            'context': {
                'location_to_block': self.id,
                'tree_view_ref': 'econovo_user_warehouse_restriction.view_warehouse_user_permission_block_location_tree',
            },
            'target': 'new',
            'help': '<p class="o_view_nocontent_smiling_face">'
                    'No users available to block this location.'
                    '</p><p>All users either already have this location blocked or have Full Control.</p>',
        }
