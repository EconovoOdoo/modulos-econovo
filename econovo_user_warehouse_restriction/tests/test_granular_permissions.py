# -*- coding: utf-8 -*-
"""Test granular picking permissions (create, write, unlink, validate, cancel).

This test suite validates:
- allow_create_picking permission
- allow_write_picking permission
- allow_unlink_picking permission
- allow_validate_picking permission
- allow_cancel_picking permission

Test coverage for CASO 4.1-4.5 manual testing scenarios.
"""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestGranularPickingPermissions(TransactionCase):
    """Test suite for granular picking operation permissions."""

    def setUp(self):
        """Create test environment with different permission scenarios."""
        super(TestGranularPickingPermissions, self).setUp()
        
        # Create test warehouse
        self.warehouse = self.env['stock.warehouse'].sudo().create({
            'name': 'Test Granular Warehouse',
            'code': 'TGWH',
        })
        
        # Get standard locations
        self.location_supplier = self.env.ref('stock.stock_location_suppliers')
        self.location_customer = self.env.ref('stock.stock_location_customers')
        self.location_stock = self.warehouse.lot_stock_id
        
        # Create test product
        self.product = self.env['product.product'].sudo().create({
            'name': 'Test Product Granular',
            'type': 'product',
        })

    # ========================================================================
    # CASO 4.1: allow_create_picking permission tests
    # ========================================================================

    def test_create_only_user_can_create_picking(self):
        """Test that user with only allow_create_picking can create pickings.
        
        CASO 4.1.1: User should be able to create new picking.
        """
        # Create user with only create permission
        create_only_user = self.env['res.users'].sudo().create({
            'name': 'Create Only Test User',
            'login': 'create_only_test',
            'email': 'create_only@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': create_only_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_create_picking': True,
            'allow_write_picking': False,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Should be able to create picking
        try:
            picking = self.env['stock.picking'].with_user(create_only_user).create({
                'picking_type_id': self.warehouse.out_type_id.id,
                'location_id': self.location_stock.id,
                'location_dest_id': self.location_customer.id,
            })
            
            self.assertTrue(picking, "User with allow_create_picking should be able to create picking")
            
        except UserError as e:
            self.fail(f"User with allow_create_picking should be able to create picking: {str(e)}")

    def test_create_only_user_cannot_write_picking(self):
        """Test that user with only allow_create_picking cannot modify pickings.
        
        CASO 4.1.2: User should NOT be able to modify existing picking.
        """
        # Create user with only create permission
        create_only_user = self.env['res.users'].sudo().create({
            'name': 'Create Only Write Test User',
            'login': 'create_only_write_test',
            'email': 'create_only_write@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': create_only_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_create_picking': True,
            'allow_write_picking': False,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create picking as admin
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Attempt to modify should fail
        with self.assertRaises(UserError) as context:
            picking.with_user(create_only_user).write({
                'note': 'Modified by create-only user',
            })
        
        self.assertIn('allow_write_picking', str(context.exception).lower())

    def test_create_only_user_cannot_validate_picking(self):
        """Test that user with only allow_create_picking cannot validate pickings.
        
        CASO 4.1.3: User should NOT be able to validate picking (needs allow_write_picking).
        """
        # Create user with only create permission
        create_only_user = self.env['res.users'].sudo().create({
            'name': 'Create Only Validate Test User',
            'login': 'create_only_validate_test',
            'email': 'create_only_validate@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': create_only_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_create_picking': True,
            'allow_write_picking': False,  # Validation requires this
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create and confirm picking as admin
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        self.env['stock.move'].sudo().create({
            'name': 'Test Move',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        picking.action_confirm()
        
        # Attempt to validate should fail
        with self.assertRaises(UserError) as context:
            picking.with_user(create_only_user).button_validate()
        
        self.assertIn('allow_write_picking', str(context.exception).lower())

    # ========================================================================
    # CASO 4.2: allow_write_picking Permission Tests
    # ========================================================================

    def test_write_permission_allows_modify(self):
        """Test that user with allow_write_picking can modify pickings.
        
        CASO 4.2.1: User should be able to write to existing picking.
        """
        # Create user with write permission
        write_user = self.env['res.users'].sudo().create({
            'name': 'Write Permission Test User',
            'login': 'write_permission_test',
            'email': 'write_permission@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': write_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_create_picking': True,
            'allow_write_picking': True,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create picking as admin
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Should be able to modify
        try:
            picking.with_user(write_user).write({
                'origin': 'Modified by write user',
            })
            self.assertEqual(picking.origin, 'Modified by write user')
        except UserError as e:
            self.fail(f"User with allow_write_picking should be able to modify: {str(e)}")

    def test_write_permission_allows_validate(self):
        """Test that user with allow_write_picking can validate pickings.
        
        CASO 4.2.2: User should be able to validate picking.
        """
        # Create user with write permission
        write_user = self.env['res.users'].sudo().create({
            'name': 'Write Validate Test User',
            'login': 'write_validate_test',
            'email': 'write_validate@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': write_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_create_picking': True,
            'allow_write_picking': True,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create stock quant first to have available stock
        self.env['stock.quant'].sudo().create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'quantity': 100.0,
        })
        
        # Create and confirm picking with move
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        move = self.env['stock.move'].sudo().create({
            'name': 'Test Move',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        picking.action_confirm()
        picking.action_assign()
        
        # Set quantities done directly on move
        move.sudo().quantity = 10.0
        
        # Should be able to validate
        try:
            picking.with_user(write_user).button_validate()
            self.assertEqual(picking.state, 'done')
        except UserError as e:
            self.fail(f"User with allow_write_picking should be able to validate: {str(e)}")

    def test_no_write_permission_blocks_modify(self):
        """Test that user without allow_write_picking cannot modify pickings.
        
        CASO 4.2.3: User should NOT be able to write to picking.
        """
        # Create user without write permission
        no_write_user = self.env['res.users'].sudo().create({
            'name': 'No Write Permission Test User',
            'login': 'no_write_permission_test',
            'email': 'no_write_permission@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': no_write_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_create_picking': True,
            'allow_write_picking': False,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create picking as admin
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Should NOT be able to modify
        with self.assertRaises(UserError) as context:
            picking.with_user(no_write_user).write({
                'note': 'Attempt to modify',
            })
        
        self.assertIn('allow_write_picking', str(context.exception).lower())

    def test_delete_only_user_can_delete_picking(self):
        """Test that user with only allow_delete_picking can delete pickings.
        
        CASO 4.3.1: User should be able to delete (unlink) a picking.
        """
        # Create user with only delete permission
        delete_user = self.env['res.users'].sudo().create({
            'name': 'Delete Only Test User',
            'login': 'delete_only_test',
            'email': 'delete_only@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': delete_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_delete_picking': True,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create a picking with sudo
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Should be able to delete
        picking.with_user(delete_user).unlink()
        self.assertFalse(picking.exists())

    def test_delete_permission_allows_cancel(self):
        """Test that user with allow_delete_picking can cancel pickings.
        
        CASO 4.3.2: User should be able to cancel a picking.
        """
        # Create user with delete permission
        delete_user = self.env['res.users'].sudo().create({
            'name': 'Delete Cancel Test User',
            'login': 'delete_cancel_test',
            'email': 'delete_cancel@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': delete_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_delete_picking': True,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create and confirm a picking
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        move = self.env['stock.move'].sudo().create({
            'name': 'Test Move',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        picking.action_confirm()
        
        # Should be able to cancel
        picking.with_user(delete_user).action_cancel()
        self.assertEqual(picking.state, 'cancel')

    def test_no_delete_permission_blocks_delete(self):
        """Test that user without allow_delete_picking cannot delete pickings.
        
        CASO 4.3.3: User without permission should be blocked from deleting.
        """
        # Create user without delete permission
        no_delete_user = self.env['res.users'].sudo().create({
            'name': 'No Delete Test User',
            'login': 'no_delete_test',
            'email': 'no_delete@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': no_delete_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_delete_picking': False,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create a picking
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Should not be able to delete
        with self.assertRaises(UserError) as context:
            picking.with_user(no_delete_user).unlink()
        
        # Should get UserError mentioning allow_delete_picking
        self.assertIn('allow_delete_picking', str(context.exception).lower())

    # =========================================================================
    # CASO 4.4: allow_inventory_adjustment permission
    # =========================================================================

    def test_inventory_adjustment_permission_allows_adjust(self):
        """Test that user with allow_inventory_adjustment can adjust inventory.
        
        CASO 4.4.1: User should be able to adjust inventory quantities.
        """
        # Create user with inventory adjustment permission
        inv_user = self.env['res.users'].sudo().create({
            'name': 'Inventory Adjust Test User',
            'login': 'inv_adjust_test',
            'email': 'inv_adjust@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': inv_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_inventory_adjustment': True,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create a quant
        quant = self.env['stock.quant'].sudo().create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'quantity': 100.0,
        })
        
        # Should be able to adjust inventory
        quant.with_user(inv_user).write({
            'inventory_quantity': 90.0,
        })
        
        self.assertEqual(quant.inventory_quantity, 90.0)

    def test_no_inventory_adjustment_permission_blocks_adjust(self):
        """Test that user without allow_inventory_adjustment cannot adjust inventory.
        
        CASO 4.4.2: User without permission should be blocked.
        """
        # Create user without inventory adjustment permission
        no_inv_user = self.env['res.users'].sudo().create({
            'name': 'No Inventory Adjust Test User',
            'login': 'no_inv_adjust_test',
            'email': 'no_inv_adjust@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': no_inv_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_inventory_adjustment': False,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create a quant
        quant = self.env['stock.quant'].sudo().create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'quantity': 100.0,
        })
        
        # Should not be able to adjust inventory
        with self.assertRaises(UserError) as context:
            quant.with_user(no_inv_user).write({
                'inventory_quantity': 90.0,
            })
        
        # Should get UserError mentioning allow_inventory_adjustment
        self.assertIn('allow_inventory_adjustment', str(context.exception).lower())

    def test_view_only_blocks_inventory_adjustment(self):
        """Test that view_only user cannot adjust inventory.
        
        CASO 4.4.3: View-only user should be blocked from adjusting inventory.
        """
        # Create user with view_only
        view_only_user = self.env['res.users'].sudo().create({
            'name': 'View Only Inventory Test User',
            'login': 'view_only_inv_test',
            'email': 'view_only_inv@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': view_only_user.id,
            'warehouse_id': self.warehouse.id,
            'view_only': True,
            # view_only blocks all write operations including inventory adjustment
        })
        
        # Create a quant
        quant = self.env['stock.quant'].sudo().create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'quantity': 100.0,
        })
        
        # Should not be able to adjust inventory due to view_only
        with self.assertRaises(UserError) as context:
            quant.with_user(view_only_user).write({
                'inventory_quantity': 90.0,
            })
        
        # Should get UserError mentioning view-only
        self.assertIn('view-only', str(context.exception).lower())

    # =========================================================================
    # CASO 4.5: allow_transit permission
    # =========================================================================

    def test_transit_permission_allows_transit_location(self):
        """Test that user with allow_transit can use transit locations.
        
        CASO 4.5.1: User should be able to use transit locations.
        """
        # Create a transit location
        transit_location = self.env['stock.location'].sudo().create({
            'name': 'Test Transit Location',
            'usage': 'transit',
            'location_id': self.env.ref('stock.stock_location_locations').id,
        })
        
        # Create user with transit permission
        transit_user = self.env['res.users'].sudo().create({
            'name': 'Transit Test User',
            'login': 'transit_test',
            'email': 'transit@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': transit_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_transit': True,
            'allow_as_source': True,
            'allow_as_destination': True,
            'allow_create_picking': True,
            'allow_write_picking': True,
        })
        
        # Create quant at stock location
        self.env['stock.quant'].sudo().create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'quantity': 100.0,
        })
        
        # Create picking to transit location
        picking = self.env['stock.picking'].with_user(transit_user).create({
            'picking_type_id': self.warehouse.int_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': transit_location.id,
        })
        
        # Verify picking was created successfully
        self.assertTrue(picking.exists())
        self.assertEqual(picking.location_dest_id, transit_location)

    def test_no_transit_permission_blocks_transit_location(self):
        """Test that user without allow_transit cannot bypass blocked transit locations.
        
        CASO 4.5.2: When transit location is in blacklist and allow_transit=False,
        user should be blocked from accessing it.
        """
        # Create a transit location within warehouse
        transit_location = self.env['stock.location'].sudo().create({
            'name': 'Test Transit in WH',
            'usage': 'transit',
            'location_id': self.location_stock.id,
        })
        
        # Create user without transit permission and transit location in blacklist
        no_transit_user = self.env['res.users'].sudo().create({
            'name': 'No Transit Test User',
            'login': 'no_transit_test',
            'email': 'no_transit@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': no_transit_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_transit': False,
            'allow_as_source': True,
            'allow_as_destination': True,
            'allow_create_picking': True,
            'allow_write_picking': True,
            'blocked_location_ids': [(4, transit_location.id)],  # Block the transit location
        })
        
        # Create quant at stock location
        self.env['stock.quant'].sudo().create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'quantity': 100.0,
        })
        
        # Try to create move to blocked transit location
        # Without allow_transit, the transit bypass doesn't work
        with self.assertRaises(Exception):
            self.env['stock.move'].with_user(no_transit_user).create({
                'name': 'Test Move to Blocked Transit',
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'product_uom': self.product.uom_id.id,
                'location_id': self.location_stock.id,
                'location_dest_id': transit_location.id,
            })

    def test_transit_permission_default_true(self):
        """Test that allow_transit defaults to True.
        
        CASO 4.5.3: Default should be True as most users need transit access.
        """
        # Create user
        test_user = self.env['res.users'].sudo().create({
            'name': 'Default Transit Test User',
            'login': 'default_transit_test',
            'email': 'default_transit@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        # Create permission without specifying allow_transit
        permission = self.env['warehouse.user.permission'].sudo().create({
            'user_id': test_user.id,
            'warehouse_id': self.warehouse.id,
        })
        
        # Default should be True
        self.assertTrue(permission.allow_transit)

    # =========================================================================
    # CASO 4.6: Integration tests - Combined permission scenarios
    # =========================================================================

    def test_full_control_bypasses_all_granular_permissions(self):
        """Test that full_control bypasses all granular permission checks.
        
        CASO 4.6.1: User with full_control should be able to do everything.
        """
        # Create user with full_control
        full_control_user = self.env['res.users'].sudo().create({
            'name': 'Full Control Test User',
            'login': 'full_control_test',
            'email': 'full_control@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': full_control_user.id,
            'warehouse_id': self.warehouse.id,
            'full_control': True,
            # All granular permissions are False
            'allow_create_picking': False,
            'allow_write_picking': False,
            'allow_delete_picking': False,
            'allow_inventory_adjustment': False,
        })
        
        # Should be able to create picking despite allow_create_picking=False
        picking = self.env['stock.picking'].with_user(full_control_user).create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        self.assertTrue(picking.exists())
        
        # Should be able to modify picking despite allow_write_picking=False
        picking.with_user(full_control_user).write({'origin': 'Full Control Test'})
        self.assertEqual(picking.origin, 'Full Control Test')
        
        # Should be able to delete picking despite allow_delete_picking=False
        picking.with_user(full_control_user).unlink()
        self.assertFalse(picking.exists())

    def test_create_write_workflow(self):
        """Test create + write workflow for typical user.
        
        CASO 4.6.2: User with create and write permissions can complete full workflow.
        """
        # Create user with create and write permissions
        workflow_user = self.env['res.users'].sudo().create({
            'name': 'Workflow Test User',
            'login': 'workflow_test',
            'email': 'workflow@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': workflow_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_create_picking': True,
            'allow_write_picking': True,
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create stock
        self.env['stock.quant'].sudo().create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'quantity': 100.0,
        })
        
        # Step 1: Create picking
        picking = self.env['stock.picking'].with_user(workflow_user).create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Step 2: Add move
        move = self.env['stock.move'].with_user(workflow_user).create({
            'name': 'Workflow Test Move',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Step 3: Confirm and assign
        picking.with_user(workflow_user).action_confirm()
        picking.with_user(workflow_user).action_assign()
        
        # Step 4: Set quantity and validate
        move.sudo().quantity = 10.0
        picking.with_user(workflow_user).button_validate()
        
        self.assertEqual(picking.state, 'done')

    def test_create_only_cannot_complete_workflow(self):
        """Test that create-only user cannot complete full workflow.
        
        CASO 4.6.3: User with only create permission cannot validate.
        """
        # Create user with only create permission
        create_only_user = self.env['res.users'].sudo().create({
            'name': 'Create Only Workflow Test User',
            'login': 'create_only_workflow_test',
            'email': 'create_only_workflow@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': create_only_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_create_picking': True,
            'allow_write_picking': False,  # Cannot write/validate
            'allow_as_source': True,
            'allow_as_destination': True,
        })
        
        # Create stock
        self.env['stock.quant'].sudo().create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'quantity': 100.0,
        })
        
        # Step 1: Create picking (should work)
        picking = self.env['stock.picking'].with_user(create_only_user).create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        self.assertTrue(picking.exists())
        
        # Step 2: Add move with sudo (for test setup)
        move = self.env['stock.move'].sudo().create({
            'name': 'Create Only Test Move',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Step 3: Confirm with sudo
        picking.sudo().action_confirm()
        picking.sudo().action_assign()
        move.sudo().quantity = 10.0
        
        # Step 4: Try to validate (should fail)
        with self.assertRaises(UserError) as context:
            picking.with_user(create_only_user).button_validate()
        
        self.assertIn('allow_write_picking', str(context.exception).lower())


