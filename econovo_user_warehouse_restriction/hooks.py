# -*- coding: utf-8 -*-
"""
Installation and update hooks for econovo_user_warehouse_restriction module.

Author: Jose D. Leonett
Website: https://github.com/josedleonett
License: AGPL-3
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Post-installation hook to assign Full Restriction group to all existing internal users.
    
    Implements secure-by-default principle (least privilege):
    - All internal users receive Full Restriction group on module installation
    - Portal/public users are excluded
    - System administrators (base.group_system) are excluded
    - Users can be selectively granted warehouse access via warehouse.user_ids
    
    This ensures new installations start with maximum security, requiring explicit
    permission grants rather than relying on implicit unrestricted access.
    
    Args:
        env: Odoo environment context
    """
    _logger.info("=" * 80)
    _logger.info("econovo_user_warehouse_restriction: Starting post_init_hook")
    _logger.info("=" * 80)
    
    # Get Full Restriction group
    full_group = env.ref(
        'econovo_user_warehouse_restriction.group_warehouse_restriction_full',
        raise_if_not_found=False
    )
    
    if not full_group:
        _logger.error("Full Restriction group not found! Security defaults not applied.")
        return
    
    # Get system admin group to exclude from auto-assignment
    system_group = env.ref('base.group_system', raise_if_not_found=False)
    
    # Build domain for internal users only
    domain = [
        ('share', '=', False),  # Internal users only
        ('id', '!=', env.ref('base.user_admin').id),  # Exclude admin user
    ]
    
    # Exclude users who already have the Full Restriction group
    domain.append(('groups_id', 'not in', [full_group.id]))
    
    # Get internal users to restrict
    users_to_restrict = env['res.users'].search(domain)
    
    _logger.info(f"Found {len(users_to_restrict)} internal users to assign Full Restriction")
    
    assigned_count = 0
    skipped_count = 0
    
    for user in users_to_restrict:
        # Skip system administrators (they should manage their own access)
        if system_group and system_group in user.groups_id:
            _logger.debug(f"Skipping system admin user: {user.login}")
            skipped_count += 1
            continue
        
        try:
            # Assign Full Restriction group
            # This automatically includes Source Only + Base groups via inheritance
            user.write({'groups_id': [(4, full_group.id)]})
            assigned_count += 1
            _logger.debug(f"Assigned Full Restriction to user: {user.login}")
        
        except Exception as e:
            _logger.error(f"Failed to assign Full Restriction to {user.login}: {str(e)}")
            continue
    
    _logger.info("=" * 80)
    _logger.info(f"Post-init hook completed:")
    _logger.info(f"  - Users assigned Full Restriction: {assigned_count}")
    _logger.info(f"  - System admins skipped: {skipped_count}")
    _logger.info(f"  - Total users processed: {len(users_to_restrict)}")
    _logger.info("=" * 80)
    _logger.info("SECURITY NOTE: All restricted users have NO warehouse access by default.")
    _logger.info("ACTION REQUIRED: Add users to warehouse.user_ids to grant access.")
    _logger.info("=" * 80)
