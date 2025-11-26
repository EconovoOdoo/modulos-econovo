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
             'Required for:\n'
             '- Delivery Orders (WH → Customer)\n'
             '- Outbound Transfers (WH1 → WH2)\n'
             '- Manufacturing consumption (WH → Production)\n\n'
             'Example: User can ship products from this warehouse to customers.'
    )
    
    allow_as_destination = fields.Boolean(
        string='Use as Destination',
        default=False,
        help='User can RECEIVE stock INTO this warehouse.\n\n'
             'Required for:\n'
             '- Receipt Orders (Vendor → WH)\n'
             '- Inbound Transfers (WH2 → WH1)\n'
             '- Manufacturing output (Production → WH)\n\n'
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
             'NOTE: User also needs "Write" permission to VALIDATE transfers.\n'
             'Without Write: User creates drafts that someone else must validate.\n\n'
             'Use case: Data entry operator creates pickings, supervisor validates.'
    )
    
    allow_write_picking = fields.Boolean(
        string='Modify/Validate Transfers',
        default=False,
        help='User can MODIFY and VALIDATE existing transfers.\n\n'
             'Allows:\n'
             '- Changing products, quantities, locations\n'
             '- Clicking "Validate" button to confirm transfers\n'
             '- Modifying move lines (detailed operations)\n\n'
             'NOTE: This is required to complete transfers (move stock).\n\n'
             'Example: User validates a delivery, moving stock from WH to customer.'
    )
    
    allow_delete_picking = fields.Boolean(
        string='Delete/Cancel Transfers',
        default=False,
        help='User can DELETE or CANCEL stock transfers.\n\n'
             'Allows:\n'
             '- Canceling transfers in draft/confirmed state\n'
             '- Deleting canceled transfers\n\n'
             'Use with caution: Deleting transfers can hide audit trails.\n\n'
             'Example: User cancels an incorrect delivery order.'
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
                    'allow_write_picking', 'allow_delete_picking', 'allow_inventory_adjustment')
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
                    record.allow_write_picking,
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
            self.allow_write_picking = False
            self.allow_delete_picking = False
            self.allow_inventory_adjustment = False
            return {
                'warning': {
                    'title': 'View Only Mode Enabled',
                    'message': 'This user can now ONLY VIEW data in this warehouse.\n'
                              'All write permissions have been disabled.'
                }
            }
    
    @api.onchange('allow_create_picking', 'allow_write_picking')
    def _onchange_picking_permissions(self):
        """Warn if user can Create but not Write (incomplete workflow)."""
        if self.allow_create_picking and not self.allow_write_picking and not self.full_control:
            return {
                'warning': {
                    'title': 'Incomplete Workflow',
                    'message': 'This user can CREATE pickings but CANNOT VALIDATE them.\n\n'
                              'Result: User creates draft transfers that someone else must validate.\n\n'
                              'This is intentional for data entry operators.\n'
                              'If user should complete transfers, enable "Modify/Validate Transfers".'
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
        if self.view_only and permission_type in ['create_picking', 'write_picking', 
                                                    'delete_picking', 'inventory']:
            return False
        
        # Check specific permission
        permission_map = {
            'source': self.allow_as_source,
            'destination': self.allow_as_destination,
            'inventory': self.allow_inventory_adjustment,
            'create_picking': self.allow_create_picking,
            'write_picking': self.allow_write_picking,
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
    
    def can_write_picking(self):
        """Check if user can modify/validate stock pickings in this warehouse."""
        return self.check_permission('write_picking')
    
    def can_delete_picking(self):
        """Check if user can delete/cancel stock pickings in this warehouse."""
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
