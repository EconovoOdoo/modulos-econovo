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
