# -*- coding: utf-8 -*-
"""
Installation hooks for econovo_user_warehouse_restriction module.

Author: Jose D. Leonett
Website: https://github.com/josedleonett
License: AGPL-3
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Post-installation hook for econovo_user_warehouse_restriction.
    
    Initializes the module after installation:
    - Removes obsolete groups (Source Only, Full) from previous versions
    - Assigns restriction group to all existing users (except admins)
    - Creates Full Control permission records for all system administrators
    - Prevents admin lockout on warehouses
    
    Args:
        env: Odoo environment context
    """
    _logger.info("=" * 80)
    _logger.info("econovo_user_warehouse_restriction: Starting post_init_hook")
    _logger.info("=" * 80)
    
    _cleanup_obsolete_groups(env)
    _assign_restriction_group_to_users(env)
    _initialize_admin_permissions(env)
    
    _logger.info("=" * 80)
    _logger.info("post_init_hook completed successfully")
    _logger.info("=" * 80)


def _cleanup_obsolete_groups(env):
    """
    Remove obsolete security groups from previous module versions.
    
    Removes groups that are no longer used:
    - group_warehouse_restriction_source_only (replaced by permission matrix)
    - group_warehouse_restriction_full (replaced by permission matrix)
    
    These groups were from the old architecture and should not appear in user settings.
    
    Args:
        env: Odoo environment context
    """
    _logger.info("Cleaning up obsolete security groups...")
    
    obsolete_group_xmlids = [
        'econovo_user_warehouse_restriction.group_warehouse_restriction_source_only',
        'econovo_user_warehouse_restriction.group_warehouse_restriction_full',
    ]
    
    for xmlid in obsolete_group_xmlids:
        try:
            # Find the group record via XML ID
            group = env.ref(xmlid, raise_if_not_found=False)
            if group:
                group_name = group.name
                user_count = len(group.users)
                
                _logger.info(f"Found obsolete group: {group_name} (assigned to {user_count} users)")
                
                # Remove the group (this also removes all user assignments)
                group.unlink()
                
                _logger.info(f"Deleted obsolete group: {group_name}")
            else:
                _logger.info(f"Group {xmlid} not found (already deleted or never existed)")
        except Exception as e:
            _logger.warning(f"Error deleting group {xmlid}: {str(e)}")
    
    _logger.info("Obsolete group cleanup complete")


def _assign_restriction_group_to_users(env):
    """
    Assign warehouse restriction groups to all existing inventory users.
    
    Two groups are assigned:
    1. user_warehouse_restriction_group_user (base restriction)
    2. user_warehouse_restriction_group_restricted (for "Own Records" rule)
    
    System administrators are excluded from the restricted group,
    allowing them to see all permission records.
    
    Args:
        env: Odoo environment context
    """
    _logger.info("Assigning restriction groups to existing users...")
    
    # Get the restriction groups
    restriction_group = env.ref(
        'econovo_user_warehouse_restriction.user_warehouse_restriction_group_user',
        raise_if_not_found=False
    )
    restricted_group = env.ref(
        'econovo_user_warehouse_restriction.user_warehouse_restriction_group_restricted',
        raise_if_not_found=False
    )
    
    if not restriction_group or not restricted_group:
        _logger.warning("Restriction groups not found, skipping group assignment")
        return
    
    # Get system admin group for exclusion check
    admin_group = env.ref('base.group_system', raise_if_not_found=False)
    
    # Get all internal users with inventory access (but not portal/public)
    inventory_users = env['res.users'].search([
        ('share', '=', False),  # Internal users only
        ('groups_id', 'in', [env.ref('stock.group_stock_user').id]),
        ('id', '!=', env.ref('base.user_admin').id),  # Exclude OdooBot/Admin
        ('id', '!=', env.ref('base.user_root').id),
    ])
    
    if not inventory_users:
        _logger.info("No inventory users found to assign restriction groups")
        return
    
    _logger.info(f"Found {len(inventory_users)} inventory user(s)")
    
    # Assign restriction groups
    assigned_count = 0
    for user in inventory_users:
        is_admin = admin_group and admin_group in user.groups_id
        groups_to_add = []
        
        # Always assign base restriction group to non-admins
        if not is_admin and restriction_group not in user.groups_id:
            groups_to_add.append(restriction_group.id)
        
        # Assign restricted group ONLY to non-admins
        if not is_admin and restricted_group not in user.groups_id:
            groups_to_add.append(restricted_group.id)
        
        if groups_to_add:
            user.write({'groups_id': [(4, gid) for gid in groups_to_add]})
            assigned_count += 1
            _logger.info(
                f"Assigned restriction groups to user: {user.name} "
                f"(Admin: {is_admin}, Groups: {len(groups_to_add)})"
            )
    
    _logger.info(f"Restriction group assignment complete: {assigned_count} user(s) updated")



def _initialize_admin_permissions(env):
    """
    Create Full Control permissions for all system administrators.
    
    This prevents admin lockout when enabling warehouse restrictions.
    All existing warehouses will be accessible to admins with full_control=True.
    
    Args:
        env: Odoo environment context
    """
    _logger.info("Initializing admin permissions...")
    
    # Get system administrators
    admin_group = env.ref('base.group_system', raise_if_not_found=False)
    if not admin_group:
        _logger.warning("System admin group not found, skipping admin permission initialization")
        return
    
    admins = env['res.users'].search([
        ('groups_id', 'in', [admin_group.id]),
        ('share', '=', False),  # Internal users only
    ])
    
    if not admins:
        _logger.warning("No system administrators found")
        return
    
    _logger.info(f"Found {len(admins)} system administrator(s)")
    
    # Get all warehouses
    warehouses = env['stock.warehouse'].search([])
    _logger.info(f"Found {len(warehouses)} warehouse(s)")
    
    # Create permission records
    created_count = 0
    for warehouse in warehouses:
        for admin in admins:
            # Check if permission already exists
            existing = env['warehouse.user.permission'].search([
                ('warehouse_id', '=', warehouse.id),
                ('user_id', '=', admin.id)
            ], limit=1)
            
            if not existing:
                env['warehouse.user.permission'].create({
                    'warehouse_id': warehouse.id,
                    'user_id': admin.id,
                    'full_control': True,
                    'active': True,
                })
                created_count += 1
                _logger.info(
                    f"Created Full Control permission: "
                    f"User '{admin.name}' -> Warehouse '{warehouse.name}'"
                )
    
    _logger.info(f"Admin permission initialization complete: {created_count} permission(s) created")
