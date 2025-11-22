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
    - Creates Full Control permission records for all system administrators
    - Prevents admin lockout on warehouses
    
    Args:
        env: Odoo environment context
    """
    _logger.info("=" * 80)
    _logger.info("econovo_user_warehouse_restriction: Starting post_init_hook")
    _logger.info("=" * 80)
    
    _initialize_admin_permissions(env)
    
    _logger.info("=" * 80)
    _logger.info("post_init_hook completed successfully")
    _logger.info("=" * 80)


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
                    f"User '{admin.name}' → Warehouse '{warehouse.name}'"
                )
    
    _logger.info(f"Admin permission initialization complete: {created_count} permission(s) created")

