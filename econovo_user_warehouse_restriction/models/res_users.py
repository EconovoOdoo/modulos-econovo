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

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    """Extends res.users from user_warehouse_restriction module.
    
    This module inherits from user_warehouse_restriction (Cybrosys) and adds:
    - Transit warehouse/location support
    - Granular restriction groups (Full vs Source Only)
    - Integration with the base module's warehouse.user_ids field
    - Secure-by-default: Auto-assigns Full Restriction group to new users
    
    Security Model (Least Privilege Principle):
    -------------------------------------------
    All new internal users automatically receive the Full Restriction group,
    which restricts both source AND destination warehouse access. This ensures:
    
    1. Users start with ZERO warehouse access
    2. Access must be explicitly granted via warehouse.user_ids
    3. System administrators are excluded from auto-assignment
    4. Portal/public users are not affected
    
    Note: For cross-warehouse permissions, assign the user to multiple warehouses
    using warehouse.user_ids instead of creating custom permission fields.
    This ensures compatibility with the base module's Record Rules.
    """
    _inherit = 'res.users'
    
    # No additional fields - use warehouse.user_ids from base module for assignments
    
    def _get_default_warehouse_restriction_group(self):
        """Get the Full Restriction group ID for auto-assignment.
        
        Returns:
            int|bool: Group ID if found, False otherwise
        """
        full_group = self.env.ref(
            'econovo_user_warehouse_restriction.group_warehouse_restriction_full',
            raise_if_not_found=False
        )
        return full_group.id if full_group else False
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-assign Full Restriction group to new internal users.
        
        Implements secure-by-default principle:
        - All new internal users receive Full Restriction group
        - Portal/public users are excluded (share=True)
        - System administrators are excluded
        - Users can be granted warehouse access via warehouse.user_ids
        
        This ensures new users start with least privilege (zero access) and
        must be explicitly granted permissions.
        """
        # Get Full Restriction group ID
        full_group_id = self._get_default_warehouse_restriction_group()
        
        if full_group_id:
            system_group = self.env.ref('base.group_system', raise_if_not_found=False)
            system_group_id = system_group.id if system_group else False
            
            for vals in vals_list:
                # Only assign to internal users (not portal/public)
                if vals.get('share', False):
                    continue
                
                # Skip if user is being created as system administrator
                groups_id = vals.get('groups_id', [])
                if system_group_id and any(
                    cmd[0] in (4, 6) and (
                        system_group_id in ([cmd[1]] if cmd[0] == 4 else cmd[2])
                    )
                    for cmd in groups_id
                ):
                    _logger.debug("Skipping Full Restriction for new system admin user")
                    continue
                
                # Initialize groups_id if not present
                if 'groups_id' not in vals:
                    vals['groups_id'] = []
                
                # Add Full Restriction group (unless already present)
                if not any(
                    cmd[0] in (4, 6) and (
                        full_group_id in ([cmd[1]] if cmd[0] == 4 else cmd[2])
                    )
                    for cmd in vals['groups_id']
                ):
                    vals['groups_id'].append((4, full_group_id))
                    _logger.info(
                        f"Auto-assigned Full Restriction group to new user: "
                        f"{vals.get('login', 'unknown')}"
                    )
        
        return super(ResUsers, self).create(vals_list)


