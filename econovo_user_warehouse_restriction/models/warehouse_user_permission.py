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
from odoo.exceptions import ValidationError


class WarehouseUserPermission(models.Model):
    """Granular warehouse permissions per user.
    
    This model replaces the group-based inheritance system (Unrestricted, Source Only, Full)
    with a flexible permission matrix where each user can have different access levels
    in each warehouse.
    
    Key Features:
    - Per-warehouse configuration (not global)
    - Multiple permission modes: Full Control, View Only, Granular
    - Warehouse-level permissions: Source, Destination, Inventory Adjustment
    - Operation-level permissions: Create, Write, Delete Pickings
    - Location-level restrictions: Blacklist specific locations
    - Transit location access control
    
    Example Use Cases:
    - User A: Full Control in WH1, View Only in WH2, No access to WH3
    - User B: Can send from WH1 (source) but not receive (destination)
    - User C: Can adjust inventory but cannot create pickings
    - User D: Access to all locations EXCEPT WH1/QC and WH1/Quarantine
    """
    _name = 'warehouse.user.permission'
    _description = 'Granular Warehouse Permissions per User'
    _rec_name = 'user_id'
    _order = 'warehouse_id, user_id'
    
    # ========================================================================
    # CORE RELATIONSHIPS
    # ========================================================================
    
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        required=True,
        ondelete='cascade',
        index=True,
        help='Warehouse for which these permissions apply.'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True,
        domain="[('share', '=', False)]",
        help='User to whom these permissions are granted. Only internal users.'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='warehouse_id.company_id',
        store=True,
        readonly=True,
        help='Company of the warehouse (automatically set).'
    )
    
    # ========================================================================
    # BYPASS DETECTION (informational fields)
    # ========================================================================
    
    has_bypass_permissions = fields.Boolean(
        string='Has Bypass Permissions',
        compute='_compute_bypass_permissions',
        store=False,
        help='Indicates if this user has system-level privileges that bypass '
             'all warehouse restrictions (e.g., System Administrator).'
    )
    
    bypass_info = fields.Char(
        string='Bypass Status',
        compute='_compute_bypass_permissions',
        store=False,
        help='Information about bypass permissions active for this user.'
    )
    
    # ========================================================================
    # SPECIAL MODES (mutually exclusive with granular permissions)
    # ========================================================================
    
    full_control = fields.Boolean(
        string='Full Control',
        default=False,
        help='User has COMPLETE access to this warehouse.\n\n'
             'When enabled:\n'
             '- All granular permissions below are IGNORED\n'
             '- User can perform ANY operation in this warehouse\n'
             '- Blocked locations are IGNORED\n\n'
             'Use for: Warehouse managers, administrators'
    )
    
    view_only = fields.Boolean(
        string='View Only (Read-Only)',
        default=False,
        help='User can ONLY VIEW data in this warehouse.\n\n'
             'When enabled:\n'
             '- Cannot create, modify, or delete anything\n'
             '- Can see stock levels, pickings, moves, etc.\n'
             '- All write permissions below are BLOCKED\n\n'
             'Use for: Auditors, analysts, read-only consultants'
    )
    
    # ========================================================================
    # WAREHOUSE-LEVEL PERMISSIONS (what warehouses user can access)
    # ========================================================================
    
    allow_as_source = fields.Boolean(
        string='Use as Source',
        default=False,
        help='User can TAKE/SEND stock FROM this warehouse.\n\n'
             'This permission FILTERS which locations appear in source dropdowns.\n\n'
             'Required for:\n'
             '- Delivery Orders (WH → Customer)\n'
             '- Outbound Transfers (WH1 → WH2)\n'
             '- Manufacturing consumption (WH → Production)\n\n'
             '⚠️ IMPORTANT: This permission alone does NOT allow operations!\n'
             'You must ALSO enable operation permissions below:\n'
             '- "Create Transfers" to create new pickings\n'
             '- "Modify Transfers" to edit existing pickings\n'
             '- "Validate Transfers" to confirm/complete pickings\n\n'
             'Example: User can ship products from this warehouse to customers.'
    )
    
    allow_as_destination = fields.Boolean(
        string='Use as Destination',
        default=False,
        help='User can RECEIVE stock INTO this warehouse.\n\n'
             'This permission FILTERS which locations appear in destination dropdowns.\n\n'
             'Required for:\n'
             '- Receipt Orders (Vendor → WH)\n'
             '- Inbound Transfers (WH2 → WH1)\n'
             '- Manufacturing output (Production → WH)\n\n'
             '⚠️ IMPORTANT: This permission alone does NOT allow operations!\n'
             'You must ALSO enable operation permissions below:\n'
             '- "Create Transfers" to create new pickings\n'
             '- "Modify Transfers" to edit existing pickings\n'
             '- "Validate Transfers" to confirm/complete pickings\n\n'
             'Example: User can receive products from vendors into this warehouse.'
    )
    
    allow_inventory_adjustment = fields.Boolean(
        string='Inventory Adjustments',
        default=False,
        help='User can adjust stock quantities DIRECTLY (bypasses source/destination validation).\n\n'
             'Allows:\n'
             '- Increment/decrement stock without transfer\n'
             '- Cycle counts and physical inventory\n'
             '- Scrap and loss operations\n\n'
             '⚠️ WARNING: This is a sensitive permission. User can add/remove stock freely.\n'
             '⚠️ Grant only to trusted users: supervisors, warehouse managers, accountants.\n\n'
             'Example: User can adjust stock from 100 → 95 units to reflect shrinkage.'
    )
    
    # ========================================================================
    # OPERATION-LEVEL PERMISSIONS (what operations user can perform)
    # ========================================================================
    
    allow_create_picking = fields.Boolean(
        string='Create Transfers',
        default=False,
        help='User can CREATE new stock pickings/transfers.\n\n'
             'Allows creating:\n'
             '- Delivery orders\n'
             '- Receipt orders\n'
             '- Internal transfers\n\n'
             '⚠️ PREREQUISITE: User needs "Use as Source" and/or "Use as Destination"\n'
             'to see the warehouse locations in the dropdowns.\n\n'
             'NOTE: This permission is INDEPENDENT from Modify and Validate.\n'
             '- Without Modify: User cannot edit the picking after creation\n'
             '- Without Validate: User creates drafts that someone else must process\n\n'
             'Use case: Data entry operator creates pickings, supervisor validates.'
    )
    
    allow_modify_picking = fields.Boolean(
        string='Modify Transfers',
        default=False,
        help='User can MODIFY existing transfers.\n\n'
             'Allows:\n'
             '- Changing products, quantities, locations\n'
             '- Modifying move lines (detailed operations)\n'
             '- Editing notes and other fields\n\n'
             'NOTE: This permission is INDEPENDENT from Create and Validate.\n'
             '- Can modify pickings created by others\n'
             '- Does NOT allow creating new pickings (needs Create permission)\n'
             '- Does NOT allow validating transfers (needs Validate permission)\n\n'
             'Use case: Warehouse operator adjusts quantities before supervisor validates.'
    )
    
    allow_validate_picking = fields.Boolean(
        string='Validate Transfers',
        default=False,
        help='User can VALIDATE (confirm) transfers.\n\n'
             'Allows:\n'
             '- Clicking "Validate" button to confirm transfers\n'
             '- Completing the stock movement\n\n'
             'NOTE: This is required to complete transfers (move stock).\n'
             'Can be granted separately from Modify permission.\n\n'
             'Use case: Supervisor validates prepared transfers without editing them.'
    )
    
    allow_cancel_picking = fields.Boolean(
        string='Cancel Transfers',
        default=False,
        help='User can CANCEL stock transfers.\n\n'
             'Allows:\n'
             '- Canceling transfers in draft/confirmed state\n'
             '- Reverting transfers to canceled status\n\n'
             'NOTE: Does NOT allow deleting transfers.\n'
             'Canceled transfers remain visible for audit trail.\n\n'
             'Use case: User can cancel incorrect orders but cannot hide them.'
    )
    
    allow_delete_picking = fields.Boolean(
        string='Delete Transfers',
        default=False,
        help='User can DELETE stock transfers.\n\n'
             'Allows:\n'
             '- Deleting canceled transfers permanently\n'
             '- Removing transfers from the system\n\n'
             '⚠️ WARNING: Use with caution!\n'
             'Deleting transfers removes audit trails permanently.\n'
             'Consider granting Cancel permission instead.\n\n'
             'Use case: Administrator cleans up test data or duplicates.'
    )
    
    # ========================================================================
    # LOCATION-LEVEL RESTRICTIONS (granular access within warehouse)
    # ========================================================================
    
    blocked_location_ids = fields.Many2many(
        'stock.location',
        'warehouse_permission_blocked_location_rel',
        'permission_id',
        'location_id',
        string='Blocked Locations (Blacklist)',
        domain="[('warehouse_id', '=', warehouse_id)]",
        help='Locations within this warehouse that the user CANNOT access.\n\n'
             'BLACKLIST approach: User can access ALL locations in the warehouse EXCEPT these.\n\n'
             'Use cases:\n'
             '- Restrict access to Quality Control area (WH/Stock/QC)\n'
             '- Block high-value items location (WH/Stock/High Value)\n'
             '- Prevent access to quarantine zone (WH/Stock/Quarantine)\n'
             '- Segregate hazardous materials area (WH/Stock/Hazmat)\n\n'
             'Example: Operator has access to WH1 but NOT to WH1/QC or WH1/Quarantine.\n\n'
             'NOTE: Ignored if "Full Control" is enabled.'
    )
    
    allow_transit = fields.Boolean(
        string='Access Transit Locations',
        default=True,
        help='User can use locations marked as Transit/Shared (is_transit_location=True).\n\n'
             'When enabled:\n'
             '- User can send/receive through shared transit locations\n'
             '- Required for inter-warehouse transfers via transit zones\n\n'
             'When disabled:\n'
             '- User cannot use ANY transit location\n'
             '- Blocks inter-warehouse workflows requiring transit\n\n'
             'Example: User1 (WH1) → Transit Dock → User2 (WH2)\n\n'
             'Default: Enabled (most users need transit access for transfers).'
    )
    
    # ========================================================================
    # METADATA
    # ========================================================================
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Uncheck to temporarily disable these permissions without deleting the record.'
    )
    
    # ========================================================================
    # SQL CONSTRAINTS
    # ========================================================================
    
    _sql_constraints = [
        (
            'unique_user_warehouse',
            'UNIQUE(user_id, warehouse_id)',
            'A user can only have ONE permission record per warehouse! '
            'Please edit the existing permission instead of creating a duplicate.'
        ),
    ]
    
    # ========================================================================
    # COMPUTE METHODS
    # ========================================================================
    
    @api.depends('user_id')
    def _compute_bypass_permissions(self):
        """Detect if user has system-level bypass permissions.
        
        Users with base.group_system or group_warehouse_unrestricted
        bypass all warehouse restrictions via security rules.
        """
        admin_group = self.env.ref('base.group_system', raise_if_not_found=False)
        unrestricted_group = self.env.ref(
            'econovo_user_warehouse_restriction.group_warehouse_unrestricted',
            raise_if_not_found=False
        )
        
        for record in self:
            has_bypass = False
            bypass_reason = ''
            
            if record.user_id:
                user_groups = record.user_id.groups_id
                
                if admin_group and admin_group in user_groups:
                    has_bypass = True
                    bypass_reason = 'System Administrator'
                elif unrestricted_group and unrestricted_group in user_groups:
                    has_bypass = True
                    bypass_reason = 'Unrestricted Access'
            
            record.has_bypass_permissions = has_bypass
            record.bypass_info = bypass_reason if has_bypass else ''
    
    @api.depends('warehouse_id.company_id')
    def _compute_company_id(self):
        """Ensure company is always synced with warehouse."""
        for record in self:
            record.company_id = record.warehouse_id.company_id
    
    # ========================================================================
    # CONSTRAINTS AND VALIDATIONS
    # ========================================================================
    
    @api.constrains('full_control', 'view_only', 'allow_create_picking', 
                    'allow_modify_picking', 'allow_validate_picking', 'allow_cancel_picking',
                    'allow_delete_picking', 'allow_inventory_adjustment')
    def _check_special_modes_consistency(self):
        """Validate that special modes are used correctly.
        
        Rules:
        1. view_only CANNOT be combined with any write permission
        2. full_control and view_only are mutually exclusive
        """
        for record in self:
            # Rule 1: View Only blocks all write permissions
            if record.view_only:
                write_permissions = [
                    record.allow_create_picking,
                    record.allow_modify_picking,
                    record.allow_validate_picking,
                    record.allow_cancel_picking,
                    record.allow_delete_picking,
                    record.allow_inventory_adjustment,
                ]
                if any(write_permissions):
                    raise ValidationError(
                        f"User '{record.user_id.name}' in warehouse '{record.warehouse_id.name}':\n\n"
                        f"'View Only' mode is incompatible with write permissions.\n\n"
                        f"Please either:\n"
                        f"- Disable 'View Only' to allow write operations, OR\n"
                        f"- Disable all write permissions (Create/Write/Delete Picking, Inventory Adjustments)"
                    )
            
            # Rule 2: Full Control and View Only are mutually exclusive
            if record.full_control and record.view_only:
                raise ValidationError(
                    f"User '{record.user_id.name}' in warehouse '{record.warehouse_id.name}':\n\n"
                    f"'Full Control' and 'View Only' cannot both be enabled.\n\n"
                    f"Please choose ONE:\n"
                    f"- Full Control: User has complete access\n"
                    f"- View Only: User can only read data"
                )
    
    @api.constrains('user_id', 'warehouse_id', 'full_control', 'allow_as_source',
                    'allow_as_destination', 'allow_inventory_adjustment', 'allow_create_picking',
                    'allow_modify_picking', 'allow_validate_picking', 'allow_cancel_picking',
                    'allow_delete_picking')
    def _check_delegator_privilege_escalation(self):
        """Prevent privilege escalation by delegated permission managers.
        
        Users in group_warehouse_permission_delegator can create permissions
        for OTHER users in warehouses where they have Full Control, but:
        1. Cannot create permissions for themselves
        2. Cannot grant more permissions than they have
        3. Cannot modify permissions they didn't create (handled by record rules)
        
        This check is bypassed for:
        - System Administrators (base.group_system)
        - Users with Warehouse Restriction Manager role (group_warehouse_restriction_manager)
        """
        delegator_group = self.env.ref(
            'econovo_user_warehouse_restriction.group_warehouse_permission_delegator',
            raise_if_not_found=False
        )
        manager_group = self.env.ref(
            'econovo_user_warehouse_restriction.user_warehouse_restriction_group_manager',
            raise_if_not_found=False
        )
        admin_group = self.env.ref('base.group_system', raise_if_not_found=False)
        
        if not delegator_group:
            return
        
        current_user = self.env.user
        
        # Skip check for administrators and warehouse restriction managers
        if admin_group and admin_group in current_user.groups_id:
            return
        if manager_group and manager_group in current_user.groups_id:
            return
        
        # Only apply checks if current user is a delegator (not full admin)
        if delegator_group not in current_user.groups_id:
            return
        
        for record in self:
            # Rule 1: Cannot create/modify permissions for yourself
            if record.user_id == current_user:
                raise ValidationError(
                    "Permission Denied: Self-Assignment\n\n"
                    "You cannot create or modify permissions for yourself.\n"
                    "This restriction prevents privilege escalation.\n\n"
                    "Please contact a system administrator to modify your own permissions."
                )
            
            # Rule 2: Check if delegator has Full Control on this warehouse
            delegator_permission = self.sudo().search([
                ('user_id', '=', current_user.id),
                ('warehouse_id', '=', record.warehouse_id.id),
                ('full_control', '=', True),
                ('active', '=', True),
            ], limit=1)
            
            if not delegator_permission:
                raise ValidationError(
                    f"Permission Denied: Unauthorized Warehouse\n\n"
                    f"You cannot manage permissions for warehouse '{record.warehouse_id.name}'.\n\n"
                    f"Delegated managers can only create/edit permissions in warehouses "
                    f"where they have 'Full Control' access.\n\n"
                    f"Please contact a system administrator for this warehouse."
                )
            
            # Rule 3: Cannot grant Full Control (only admins can)
            if record.full_control:
                raise ValidationError(
                    "Permission Denied: Full Control Grant\n\n"
                    "Only system administrators can grant 'Full Control' access.\n\n"
                    "As a delegated manager, you can grant:\n"
                    "- Source/Destination access\n"
                    "- Inventory Adjustment access\n"
                    "- Picking operation permissions (Create/Modify/Validate/Cancel/Delete)\n"
                    "- Location restrictions\n\n"
                    "Please contact a system administrator to grant Full Control."
                )
    
    # ========================================================================
    # ONCHANGE METHODS (UI feedback and auto-adjustments)
    # ========================================================================
    
    @api.onchange('full_control')
    def _onchange_full_control(self):
        """When Full Control is enabled, clear blocked locations (they don't apply)."""
        if self.full_control:
            self.blocked_location_ids = [(5, 0, 0)]  # Clear all blocked locations
            return {
                'warning': {
                    'title': 'Full Control Enabled',
                    'message': 'This user now has COMPLETE access to this warehouse.\n'
                              'All granular permissions and location restrictions are ignored.'
                }
            }
    
    @api.onchange('view_only')
    def _onchange_view_only(self):
        """When View Only is enabled, disable all write permissions."""
        if self.view_only:
            self.allow_create_picking = False
            self.allow_modify_picking = False
            self.allow_validate_picking = False
            self.allow_cancel_picking = False
            self.allow_delete_picking = False
            self.allow_inventory_adjustment = False
            return {
                'warning': {
                    'title': 'View Only Mode Enabled',
                    'message': 'This user can now ONLY VIEW data in this warehouse.\n'
                              'All write permissions have been disabled.'
                }
            }
    
    @api.onchange('allow_create_picking', 'allow_modify_picking', 'allow_validate_picking')
    def _onchange_picking_permissions(self):
        """Warn if user can Create but not Validate (incomplete workflow)."""
        if self.allow_create_picking and not self.allow_validate_picking and not self.full_control:
            return {
                'warning': {
                    'title': 'Incomplete Workflow',
                    'message': 'This user can CREATE pickings but CANNOT VALIDATE them.\n\n'
                              'Result: User creates draft transfers that someone else must validate.\n\n'
                              'This is intentional for data entry operators.\n'
                              'If user should complete transfers, enable "Validate Transfers".'
                }
            }
    
    # ========================================================================
    # HELPER METHODS (permission checking)
    # ========================================================================
    
    def check_permission(self, permission_type):
        """Check if user has a specific permission in this warehouse.
        
        Args:
            permission_type (str): One of: 'source', 'destination', 'inventory',
                                  'create_picking', 'write_picking', 'delete_picking'
        
        Returns:
            bool: True if permission is granted, False otherwise
        
        Note:
            - full_control bypasses all checks (returns True)
            - view_only blocks all write permissions (returns False for writes)
        """
        self.ensure_one()
        
        # Full Control bypasses everything
        if self.full_control:
            return True
        
        # View Only blocks all write operations
        if self.view_only and permission_type in ['create_picking', 'modify_picking', 
                                                    'validate_picking', 'cancel_picking',
                                                    'delete_picking', 'inventory']:
            return False
        
        # Check specific permission
        permission_map = {
            'source': self.allow_as_source,
            'destination': self.allow_as_destination,
            'inventory': self.allow_inventory_adjustment,
            'create_picking': self.allow_create_picking,
            'modify_picking': self.allow_modify_picking,
            'validate_picking': self.allow_validate_picking,
            'cancel_picking': self.allow_cancel_picking,
            'delete_picking': self.allow_delete_picking,
        }
        
        return permission_map.get(permission_type, False)
    
    def has_source_permission(self):
        """Check if user can use this warehouse as SOURCE (send stock from here)."""
        return self.check_permission('source')
    
    def has_destination_permission(self):
        """Check if user can use this warehouse as DESTINATION (receive stock here)."""
        return self.check_permission('destination')
    
    def has_inventory_permission(self):
        """Check if user can perform inventory adjustments in this warehouse."""
        return self.check_permission('inventory')
    
    def can_create_picking(self):
        """Check if user can create stock pickings in this warehouse."""
        return self.check_permission('create_picking')
    
    def can_modify_picking(self):
        """Check if user can modify stock pickings in this warehouse."""
        return self.check_permission('modify_picking')
    
    def can_validate_picking(self):
        """Check if user can validate stock pickings in this warehouse."""
        return self.check_permission('validate_picking')
    
    def can_cancel_picking(self):
        """Check if user can cancel stock pickings in this warehouse."""
        return self.check_permission('cancel_picking')
    
    def can_delete_picking(self):
        """Check if user can delete stock pickings in this warehouse."""
        return self.check_permission('delete_picking')
    
    def is_location_blocked(self, location):
        """Check if a specific location is blocked for this user.
        
        Args:
            location (stock.location): Location to check
        
        Returns:
            bool: True if location is blocked, False if accessible
        
        Note:
            - full_control ignores blocked locations (returns False)
            - Transit locations (is_transit_location=True) bypass blacklist if allow_transit=True
        """
        self.ensure_one()
        
        # Full Control bypasses location restrictions
        if self.full_control:
            return False
        
        # Transit locations bypass if allow_transit is enabled
        if location.is_transit_location and self.allow_transit:
            return False
        
        # Check if location is in blacklist
        return location in self.blocked_location_ids
    
    # ========================================================================
    # UI ACTIONS
    # ========================================================================
    
    def action_show_bypass_info(self):
        """Show informational wizard about bypass permissions.
        
        Returns:
            dict: Action to open wizard modal dialog
        """
        self.ensure_one()
        
        if not self.has_bypass_permissions:
            return {}
        
        # Use wizard modal for clean, professional display
        return self.env['warehouse.bypass.info.wizard'].action_show_info(
            user_name=self.user_id.name,
            bypass_reason=self.bypass_info
        )
