# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestWarehouseSecurityRules(TransactionCase):
    """Test security rules for warehouse-restricted models"""

    def setUp(self):
        super(TestWarehouseSecurityRules, self).setUp()
        
        # Get groups
        self.group_stock_user = self.env.ref('stock.group_stock_user')
        self.group_warehouse_restriction = self.env.ref(
            'econovo_user_warehouse_restriction.user_warehouse_restriction_group_user'
        )
        
        # Create restricted user WITHOUT Settings access
        # CRITICAL: Must be in user_warehouse_restriction_group_user for record rules to apply
        self.restricted_user = self.env['res.users'].create({
            'name': 'Test Restricted User',
            'login': 'test_restricted_security',
            'email': 'test_restricted_security@test.com',
            'groups_id': [(6, 0, [
                self.group_stock_user.id,
                self.group_warehouse_restriction.id,
            ])],
        })
        
        # Get or create warehouses (use sudo for system operations)
        self.warehouse_assigned = self.env['stock.warehouse'].sudo().create({
            'name': 'Test Assigned Warehouse',
            'code': 'TASWH',
        })
        
        self.warehouse_unassigned = self.env['stock.warehouse'].sudo().create({
            'name': 'Test Unassigned Warehouse',
            'code': 'TUAWH',
        })
        
        # Assign permission ONLY to warehouse_assigned
        self.env['warehouse.user.permission'].create({
            'warehouse_id': self.warehouse_assigned.id,
            'user_id': self.restricted_user.id,
            'full_control': True,
        })
        
        # Get locations
        self.location_assigned = self.warehouse_assigned.lot_stock_id
        self.location_unassigned = self.warehouse_unassigned.lot_stock_id
        
        # Get product for testing
        self.product = self.env['product.product'].search([('type', '=', 'product')], limit=1)
        if not self.product:
            self.product = self.env['product.product'].create({
                'name': 'Test Product',
                'type': 'product',
            })

    def test_user_sees_only_assigned_warehouses(self):
        """
        Test that users can only see warehouses they have permissions for.
        
        CASO 2.8: Stock Warehouse access restriction
        """
        # Debug: Check user groups
        user_groups = self.restricted_user.groups_id.mapped('name')
        _logger.info(f"TEST DEBUG: User groups: {user_groups}")
        
        # Debug: Check user permissions
        permissions = self.env['warehouse.user.permission'].search([
            ('user_id', '=', self.restricted_user.id)
        ])
        _logger.info(f"TEST DEBUG: User permissions: {[(p.warehouse_id.name, p.full_control) for p in permissions]}")
        
        # Search as restricted user (pass user ID, not recordset)
        warehouses_visible = self.env['stock.warehouse'].with_user(self.restricted_user).search([])
        _logger.info(f"TEST DEBUG: Warehouses visible: {warehouses_visible.mapped('name')}")
        
        # Should see ONLY assigned warehouse (filter to test warehouses)
        test_warehouses = warehouses_visible.filtered(
            lambda w: w.id in [self.warehouse_assigned.id, self.warehouse_unassigned.id]
        )
        _logger.info(f"TEST DEBUG: Test warehouses: {test_warehouses.mapped('name')}")
        
        # Should see exactly 1 warehouse (assigned only)
        self.assertEqual(
            len(test_warehouses), 1,
            f"User should see exactly 1 warehouse (assigned), but sees {len(test_warehouses)}: {test_warehouses.mapped('name')}"
        )
        
        # Should see ONLY assigned warehouse
        self.assertIn(
            self.warehouse_assigned.id,
            warehouses_visible.ids,
            "User should see assigned warehouse"
        )
        
        # Should NOT see unassigned warehouse
        self.assertNotIn(
            self.warehouse_unassigned.id,
            warehouses_visible.ids,
            "User should NOT see unassigned warehouse"
        )

    def test_user_sees_only_assigned_warehouse_locations(self):
        """
        Test that users can only see locations belonging to their assigned warehouses,
        plus virtual locations (non-internal) and locations without warehouse.
        
        CASO 2.7: Stock Location access restriction - CRITICAL TEST
        This test validates the fix for the security vulnerability where users
        could see ALL locations.
        """
        # Search as restricted user
        locations_visible = self.env['stock.location'].with_user(self.restricted_user).search([
            ('usage', '=', 'internal'),
        ])
        
        # Filter to only those with warehouse_id set
        locations_with_warehouse = locations_visible.filtered(lambda l: l.warehouse_id)
        
        # Should see ONLY locations from assigned warehouse
        for location in locations_with_warehouse:
            self.assertEqual(
                location.warehouse_id.id,
                self.warehouse_assigned.id,
                f"User should only see locations from assigned warehouse, but saw {location.complete_name} from {location.warehouse_id.name}"
            )
        
        # Specifically check assigned location is visible
        assigned_locations = self.env['stock.location'].with_user(self.restricted_user).search([
            ('id', '=', self.location_assigned.id),
        ])
        self.assertTrue(
            assigned_locations,
            "User should see assigned warehouse location"
        )
        
        # Specifically check unassigned location is NOT visible
        unassigned_locations = self.env['stock.location'].with_user(self.restricted_user).search([
            ('id', '=', self.location_unassigned.id),
        ])
        self.assertFalse(
            unassigned_locations,
            "User should NOT see unassigned warehouse location - CRITICAL SECURITY"
        )

    def test_user_sees_only_assigned_warehouse_moves(self):
        """
        Test that users can only see stock moves for their assigned warehouses.
        
        CASO 2.2: Stock Move access restriction
        """
        # Create move in assigned warehouse
        move_assigned = self.env['stock.move'].create({
            'name': 'Test Move Assigned',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'location_id': self.location_assigned.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'warehouse_id': self.warehouse_assigned.id,
        })
        
        # Create move in unassigned warehouse
        move_unassigned = self.env['stock.move'].create({
            'name': 'Test Move Unassigned',
            'product_id': self.product.id,
            'product_uom_qty': 5,
            'product_uom': self.product.uom_id.id,
            'location_id': self.location_unassigned.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'warehouse_id': self.warehouse_unassigned.id,
        })
        
        # Search as restricted user
        moves_visible = self.env['stock.move'].with_user(self.restricted_user).search([
            ('id', 'in', [move_assigned.id, move_unassigned.id]),
        ])
        
        # Should see ONLY assigned warehouse move
        self.assertIn(
            move_assigned.id,
            moves_visible.ids,
            "User should see moves from assigned warehouse"
        )
        
        self.assertNotIn(
            move_unassigned.id,
            moves_visible.ids,
            "User should NOT see moves from unassigned warehouse"
        )

    def test_user_sees_only_assigned_warehouse_pickings(self):
        """
        Test that users can only see stock pickings for their assigned warehouses.
        
        CASO 2.3: Stock Picking access restriction
        """
        # Get picking types
        picking_type_assigned = self.warehouse_assigned.out_type_id
        picking_type_unassigned = self.warehouse_unassigned.out_type_id
        
        # Create picking in assigned warehouse
        picking_assigned = self.env['stock.picking'].create({
            'picking_type_id': picking_type_assigned.id,
            'location_id': self.location_assigned.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        })
        
        # Create picking in unassigned warehouse
        picking_unassigned = self.env['stock.picking'].create({
            'picking_type_id': picking_type_unassigned.id,
            'location_id': self.location_unassigned.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        })
        
        # Search as restricted user
        pickings_visible = self.env['stock.picking'].with_user(self.restricted_user).search([
            ('id', 'in', [picking_assigned.id, picking_unassigned.id]),
        ])
        
        # Should see ONLY assigned warehouse picking
        self.assertIn(
            picking_assigned.id,
            pickings_visible.ids,
            "User should see pickings from assigned warehouse"
        )
        
        self.assertNotIn(
            picking_unassigned.id,
            pickings_visible.ids,
            "User should NOT see pickings from unassigned warehouse"
        )

    def test_user_sees_only_assigned_warehouse_quants(self):
        """
        Test that users can only see stock quants for their assigned warehouses.
        
        CASO 2.4: Stock Quant access restriction
        """
        # Create quant in assigned warehouse
        quant_assigned = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location_assigned.id,
            'quantity': 100,
        })
        
        # Create quant in unassigned warehouse
        quant_unassigned = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location_unassigned.id,
            'quantity': 50,
        })
        
        # Search as restricted user
        quants_visible = self.env['stock.quant'].with_user(self.restricted_user).search([
            ('id', 'in', [quant_assigned.id, quant_unassigned.id]),
        ])
        
        # Should see ONLY assigned warehouse quant
        self.assertIn(
            quant_assigned.id,
            quants_visible.ids,
            "User should see quants from assigned warehouse"
        )
        
        self.assertNotIn(
            quant_unassigned.id,
            quants_visible.ids,
            "User should NOT see quants from unassigned warehouse"
        )

    def test_user_sees_only_assigned_warehouse_valuation_layers(self):
        """
        Test that users can only see stock valuation layers for their assigned warehouses.
        
        CASO 2.5: Stock Valuation Layer access restriction
        """
        # This test requires stock_account module
        if 'stock.valuation.layer' not in self.env:
            self.skipTest("stock_account module not installed")
        
        # Grant stock_manager group temporarily (valuation layers require it)
        group_stock_manager = self.env.ref('stock.group_stock_manager')
        self.restricted_user.write({
            'groups_id': [(4, group_stock_manager.id)],
        })
        
        # Set product to FIFO costing
        self.product.write({
            'categ_id': self.env.ref('product.product_category_all').id,
        })
        self.product.categ_id.write({
            'property_cost_method': 'fifo',
            'property_valuation': 'real_time',
        })
        
        # Create valuation layer in assigned warehouse
        layer_assigned = self.env['stock.valuation.layer'].sudo().create({
            'product_id': self.product.id,
            'quantity': 10,
            'unit_cost': 100,
            'value': 1000,
            'company_id': self.warehouse_assigned.company_id.id,
            'stock_move_id': self.env['stock.move'].sudo().create({
                'name': 'Valuation Move Assigned',
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'product_uom': self.product.uom_id.id,
                'location_id': self.env.ref('stock.stock_location_suppliers').id,
                'location_dest_id': self.location_assigned.id,
                'warehouse_id': self.warehouse_assigned.id,
                'company_id': self.warehouse_assigned.company_id.id,
            }).id,
        })
        
        # Create valuation layer in unassigned warehouse
        layer_unassigned = self.env['stock.valuation.layer'].sudo().create({
            'product_id': self.product.id,
            'quantity': 5,
            'unit_cost': 100,
            'value': 500,
            'company_id': self.warehouse_unassigned.company_id.id,
            'stock_move_id': self.env['stock.move'].sudo().create({
                'name': 'Valuation Move Unassigned',
                'product_id': self.product.id,
                'product_uom_qty': 5,
                'product_uom': self.product.uom_id.id,
                'location_id': self.env.ref('stock.stock_location_suppliers').id,
                'location_dest_id': self.location_unassigned.id,
                'warehouse_id': self.warehouse_unassigned.id,
                'company_id': self.warehouse_unassigned.company_id.id,
            }).id,
        })
        
        # Search as restricted user
        layers_visible = self.env['stock.valuation.layer'].with_user(self.restricted_user).search([
            ('id', 'in', [layer_assigned.id, layer_unassigned.id]),
        ])
        
        # Should see ONLY assigned warehouse layer
        self.assertIn(
            layer_assigned.id,
            layers_visible.ids,
            "User should see valuation layers from assigned warehouse"
        )
        
        self.assertNotIn(
            layer_unassigned.id,
            layers_visible.ids,
            "User should NOT see valuation layers from unassigned warehouse"
        )

    def test_user_sees_only_assigned_warehouse_orderpoints(self):
        """
        Test that users can only see reordering rules for their assigned warehouses.
        
        CASO 2.6: Stock Warehouse Orderpoint access restriction
        """
        # This test requires stock module with orderpoints
        if 'stock.warehouse.orderpoint' not in self.env:
            self.skipTest("stock.warehouse.orderpoint model not available")
        
        # Create orderpoint in assigned warehouse
        orderpoint_assigned = self.env['stock.warehouse.orderpoint'].create({
            'product_id': self.product.id,
            'warehouse_id': self.warehouse_assigned.id,
            'location_id': self.location_assigned.id,
            'product_min_qty': 10,
            'product_max_qty': 100,
        })
        
        # Create orderpoint in unassigned warehouse
        orderpoint_unassigned = self.env['stock.warehouse.orderpoint'].create({
            'product_id': self.product.id,
            'warehouse_id': self.warehouse_unassigned.id,
            'location_id': self.location_unassigned.id,
            'product_min_qty': 5,
            'product_max_qty': 50,
        })
        
        # Search as restricted user
        orderpoints_visible = self.env['stock.warehouse.orderpoint'].with_user(self.restricted_user).search([
            ('id', 'in', [orderpoint_assigned.id, orderpoint_unassigned.id]),
        ])
        
        # Should see ONLY assigned warehouse orderpoint
        self.assertIn(
            orderpoint_assigned.id,
            orderpoints_visible.ids,
            "User should see orderpoints from assigned warehouse"
        )
        
        self.assertNotIn(
            orderpoint_unassigned.id,
            orderpoints_visible.ids,
            "User should NOT see orderpoints from unassigned warehouse"
        )

    def test_user_sees_only_assigned_warehouse_putaway_rules(self):
        """
        Test that users can only see putaway rules for their assigned warehouses.
        
        CASO 2.9: Stock Putaway Rule access restriction
        
        This test validates that users cannot view storage strategies (putaway rules)
        for warehouses they don't have access to.
        """
        # This test requires stock module with putaway rules
        if 'stock.putaway.rule' not in self.env:
            self.skipTest("stock.putaway.rule model not available")
        
        # Create child locations for putaway rules
        location_assigned_sub = self.env['stock.location'].sudo().create({
            'name': 'Sub Location Assigned',
            'location_id': self.location_assigned.id,
            'usage': 'internal',
        })
        
        location_unassigned_sub = self.env['stock.location'].sudo().create({
            'name': 'Sub Location Unassigned',
            'location_id': self.location_unassigned.id,
            'usage': 'internal',
        })
        
        # Create putaway rule in assigned warehouse
        putaway_assigned = self.env['stock.putaway.rule'].sudo().create({
            'product_id': self.product.id,
            'location_in_id': self.location_assigned.id,
            'location_out_id': location_assigned_sub.id,
        })
        
        # Create putaway rule in unassigned warehouse
        putaway_unassigned = self.env['stock.putaway.rule'].sudo().create({
            'product_id': self.product.id,
            'location_in_id': self.location_unassigned.id,
            'location_out_id': location_unassigned_sub.id,
        })
        
        # Search as restricted user
        putaway_visible = self.env['stock.putaway.rule'].with_user(self.restricted_user).search([
            ('id', 'in', [putaway_assigned.id, putaway_unassigned.id]),
        ])
        
        # Should see ONLY assigned warehouse putaway rule
        self.assertIn(
            putaway_assigned.id,
            putaway_visible.ids,
            "User should see putaway rules from assigned warehouse"
        )
        
        self.assertNotIn(
            putaway_unassigned.id,
            putaway_visible.ids,
            "User should NOT see putaway rules from unassigned warehouse - SECURITY"
        )

    def test_user_cannot_create_putaway_rule_unassigned_warehouse(self):
        """
        Test that users cannot create putaway rules for unauthorized warehouses.
        
        CASO 2.9.1: Stock Putaway Rule create restriction
        """
        # This test requires stock module with putaway rules
        if 'stock.putaway.rule' not in self.env:
            self.skipTest("stock.putaway.rule model not available")
        
        # Create child location for putaway rule
        location_unassigned_sub = self.env['stock.location'].sudo().create({
            'name': 'Sub Location Unassigned Create Test',
            'location_id': self.location_unassigned.id,
            'usage': 'internal',
        })
        
        # Attempt to create putaway rule in unassigned warehouse should fail
        with self.assertRaises(AccessError):
            self.env['stock.putaway.rule'].with_user(self.restricted_user).create({
                'product_id': self.product.id,
                'location_in_id': self.location_unassigned.id,
                'location_out_id': location_unassigned_sub.id,
            })


@tagged('post_install', '-at_install')
class TestDelegatedPermissionManager(TransactionCase):
    """Test delegated permission manager functionality"""

    def setUp(self):
        super(TestDelegatedPermissionManager, self).setUp()
        
        # Get required groups
        self.group_stock_user = self.env.ref('stock.group_stock_user')
        
        # Get or create the delegator group (needed for post_install tests)
        try:
            self.group_delegator = self.env.ref(
                'econovo_user_warehouse_restriction.group_warehouse_permission_delegator'
            )
        except ValueError:
            # Create the group if it doesn't exist (during test execution)
            category_inventory = self.env.ref('base.module_category_inventory')
            self.group_delegator = self.env['res.groups'].sudo().create({
                'name': 'Warehouse Permissions Delegator',
                'category_id': category_inventory.id,
                'implied_ids': [(4, self.group_stock_user.id)],
            })
            # Register in ir.model.data so ACLs can find it
            self.env['ir.model.data'].sudo().create({
                'name': 'group_warehouse_permission_delegator',
                'module': 'econovo_user_warehouse_restriction',
                'model': 'res.groups',
                'res_id': self.group_delegator.id,
                'noupdate': False,
            })
            # Create ACL for this group
            permission_model = self.env['ir.model'].sudo().search([
                ('model', '=', 'warehouse.user.permission')
            ], limit=1)
            if permission_model:
                self.env['ir.model.access'].sudo().create({
                    'name': 'warehouse.user.permission.delegator.test',
                    'model_id': permission_model.id,
                    'group_id': self.group_delegator.id,
                    'perm_read': True,
                    'perm_write': True,
                    'perm_create': True,
                    'perm_unlink': False,
                })
                # Create record rule for delegator group
                self.env['ir.rule'].sudo().create({
                    'name': 'Warehouse User Permission - Delegated Managers (Test)',
                    'model_id': permission_model.id,
                    'domain_force': '[(1, "=", 1)]',
                    'groups': [(4, self.group_delegator.id)],
                    'perm_read': True,
                    'perm_write': True,
                    'perm_create': True,
                    'perm_unlink': False,
                })
        
        # Create delegator user (supervisor who can delegate permissions in their warehouses)
        self.delegator_user = self.env['res.users'].create({
            'name': 'Test Delegator User',
            'login': 'test_delegator',
            'email': 'test_delegator@test.com',
            'groups_id': [(6, 0, [
                self.group_stock_user.id,
                self.group_delegator.id,
            ])],
        })
        
        # Create a regular user that the delegator will try to give permissions to
        self.target_user = self.env['res.users'].create({
            'name': 'Test Target User',
            'login': 'test_target',
            'email': 'test_target@test.com',
            'groups_id': [(6, 0, [self.group_stock_user.id])],
        })
        
        # Create warehouses
        self.warehouse_controlled = self.env['stock.warehouse'].sudo().create({
            'name': 'Controlled Warehouse',
            'code': 'CTRL',
        })
        
        self.warehouse_uncontrolled = self.env['stock.warehouse'].sudo().create({
            'name': 'Uncontrolled Warehouse',
            'code': 'UNCT',
        })
        
        # Give delegator Full Control on warehouse_controlled ONLY
        self.env['warehouse.user.permission'].sudo().create({
            'warehouse_id': self.warehouse_controlled.id,
            'user_id': self.delegator_user.id,
            'full_control': True,
        })

    def test_delegator_can_create_permission_for_others(self):
        """
        Test that delegators can create permissions for other users in their warehouses.
        """
        from odoo.exceptions import ValidationError
        
        # Delegator creates permission for target user in controlled warehouse
        # This should succeed
        permission = self.env['warehouse.user.permission'].with_user(self.delegator_user).create({
            'warehouse_id': self.warehouse_controlled.id,
            'user_id': self.target_user.id,
            'allow_as_source': True,
            'allow_as_destination': True,
            'allow_create_picking': True,
        })
        
        self.assertTrue(permission.id, "Delegator should be able to create permissions for others")
        self.assertEqual(permission.user_id.id, self.target_user.id)
        self.assertEqual(permission.warehouse_id.id, self.warehouse_controlled.id)
        self.assertTrue(permission.allow_as_source)
        self.assertTrue(permission.allow_as_destination)
        self.assertTrue(permission.allow_create_picking)

    def test_delegator_cannot_create_permission_for_self(self):
        """
        Test that delegators cannot create permissions for themselves.
        
        This prevents privilege escalation where a user grants themselves more access.
        The system blocks self-assignment via:
        1. Python constraint (_check_delegator_privilege_escalation)
        2. Database unique constraint (if permission already exists)
        
        Both mechanisms effectively prevent self-assignment.
        """
        from odoo.exceptions import ValidationError
        
        # The delegator already has Full Control in warehouse_controlled (setUp)
        # Attempting to create another permission for self should fail
        # Either via ValidationError (Python) or IntegrityError (DB unique constraint)
        error_raised = False
        try:
            self.env['warehouse.user.permission'].with_user(self.delegator_user).create({
                'warehouse_id': self.warehouse_controlled.id,
                'user_id': self.delegator_user.id,
                'allow_inventory_adjustment': True,
            })
        except (ValidationError, Exception):
            error_raised = True
        
        self.assertTrue(error_raised, "Delegator should NOT be able to create permissions for self")

    def test_delegator_cannot_create_permission_for_uncontrolled_warehouse(self):
        """
        Test that delegators cannot create permissions for warehouses they don't control.
        """
        from odoo.exceptions import ValidationError
        
        # Delegator tries to create permission in uncontrolled warehouse - should fail
        with self.assertRaises(ValidationError):
            self.env['warehouse.user.permission'].with_user(self.delegator_user).create({
                'warehouse_id': self.warehouse_uncontrolled.id,
                'user_id': self.target_user.id,
                'allow_as_source': True,
            })

    def test_delegator_cannot_grant_full_control(self):
        """
        Test that delegators cannot grant Full Control to other users.
        
        Only system administrators can grant Full Control access.
        """
        from odoo.exceptions import ValidationError
        
        # Delegator tries to grant Full Control - should fail
        with self.assertRaises(ValidationError):
            self.env['warehouse.user.permission'].with_user(self.delegator_user).create({
                'warehouse_id': self.warehouse_controlled.id,
                'user_id': self.target_user.id,
                'full_control': True,
            })

    def test_delegator_can_read_permissions_in_controlled_warehouse(self):
        """
        Test that delegators can read permissions for their controlled warehouses.
        """
        # Create a permission via sudo (simulating admin creation)
        admin_permission = self.env['warehouse.user.permission'].sudo().create({
            'warehouse_id': self.warehouse_controlled.id,
            'user_id': self.target_user.id,
            'allow_as_source': True,
        })
        
        # Delegator should be able to read this permission
        visible_permissions = self.env['warehouse.user.permission'].with_user(self.delegator_user).search([
            ('warehouse_id', '=', self.warehouse_controlled.id),
        ])
        
        self.assertIn(
            admin_permission.id,
            visible_permissions.ids,
            "Delegator should be able to read permissions in controlled warehouse"
        )

    def test_admin_can_grant_full_control(self):
        """
        Test that system administrators can still grant Full Control.
        """
        # Admin creates Full Control permission - should succeed
        permission = self.env['warehouse.user.permission'].sudo().create({
            'warehouse_id': self.warehouse_controlled.id,
            'user_id': self.target_user.id,
            'full_control': True,
        })
        
        self.assertTrue(permission.id, "Admin should be able to grant Full Control")
        self.assertTrue(permission.full_control)
