# -*- coding: utf-8 -*-
"""Test directional permissions (source/destination) and stock.move restrictions.

This test suite validates:
- stock.move write/unlink restrictions for view_only users
- allow_as_source permission (outbound only)
- allow_as_destination permission (inbound only)

Test coverage for CASO 3.3, 3.4, 3.5 manual testing scenarios.
"""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class TestDirectionalPermissions(TransactionCase):
    """Test suite for directional permissions and stock.move restrictions."""

    def setUp(self):
        """Create test environment with different permission scenarios."""
        super(TestDirectionalPermissions, self).setUp()
        
        # Create test warehouse
        self.warehouse = self.env['stock.warehouse'].sudo().create({
            'name': 'Test Directional Warehouse',
            'code': 'TDWH',
        })
        
        # Get standard locations
        self.location_supplier = self.env.ref('stock.stock_location_suppliers')
        self.location_customer = self.env.ref('stock.stock_location_customers')
        self.location_stock = self.warehouse.lot_stock_id
        
        # Create test product
        self.product = self.env['product.product'].sudo().create({
            'name': 'Test Product Directional',
            'type': 'product',
        })
        
        # Create view_only user for stock.move tests
        self.view_only_user = self.env['res.users'].sudo().create({
            'name': 'View Only Move Test',
            'login': 'viewonly_move_test',
            'email': 'viewonly_move@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.view_only_permission = self.env['warehouse.user.permission'].sudo().create({
            'user_id': self.view_only_user.id,
            'warehouse_id': self.warehouse.id,
            'view_only': True,
            'full_control': False,
        })
        
        # Create source-only user for CASO 3.4
        self.source_only_user = self.env['res.users'].sudo().create({
            'name': 'Source Only Test User',
            'login': 'source_only_test',
            'email': 'source_only@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.source_permission = self.env['warehouse.user.permission'].sudo().create({
            'user_id': self.source_only_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_as_source': True,
            'allow_as_destination': False,
            'allow_create_picking': True,
            'allow_modify_picking': True,
            'allow_validate_picking': True,
        })
        
        # Create destination-only user for CASO 3.5
        self.dest_only_user = self.env['res.users'].sudo().create({
            'name': 'Destination Only Test User',
            'login': 'dest_only_test',
            'email': 'dest_only@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.dest_permission = self.env['warehouse.user.permission'].sudo().create({
            'user_id': self.dest_only_user.id,
            'warehouse_id': self.warehouse.id,
            'allow_as_source': False,
            'allow_as_destination': True,
            'allow_create_picking': True,
            'allow_modify_picking': True,
            'allow_validate_picking': True,
        })

    # ========================================================================
    # CASO 3.3: stock.move restrictions for view_only users
    # ========================================================================

    def test_view_only_blocks_move_write(self):
        """Test that view_only permission blocks stock.move write operations.
        
        CASO 3.3 - Image 2: Changing quantity in move line should fail.
        """
        # Create picking with move as admin
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
        
        # Attempt to modify move as view_only user should fail
        with self.assertRaises(UserError) as context:
            move.with_user(self.view_only_user).write({
                'product_uom_qty': 20,
            })
        
        self.assertIn('view_only', str(context.exception).lower())

    def test_view_only_blocks_move_unlink(self):
        """Test that view_only permission blocks stock.move delete operations.
        
        CASO 3.3 - Image 3: Deleting move line should fail.
        """
        # Create draft picking with move
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        move = self.env['stock.move'].sudo().create({
            'name': 'Test Move Delete',
            'product_id': self.product.id,
            'product_uom_qty': 5,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Attempt to delete move as view_only user should fail
        with self.assertRaises(UserError) as context:
            move.with_user(self.view_only_user).unlink()
        
        self.assertIn('view_only', str(context.exception).lower())

    def test_view_only_blocks_move_location_change(self):
        """Test that view_only permission blocks changing move locations.
        
        CASO 3.3 - Image 1: Changing destination location should fail.
        """
        # Create picking with move
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        move = self.env['stock.move'].sudo().create({
            'name': 'Test Move Location',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        picking.action_confirm()
        
        # Attempt to change destination as view_only user should fail
        with self.assertRaises(UserError) as context:
            move.with_user(self.view_only_user).write({
                'location_dest_id': self.location_supplier.id,
            })
        
        self.assertIn('view_only', str(context.exception).lower())

    # ========================================================================
    # CASO 3.4: allow_as_source permission (outbound only)
    # ========================================================================

    def test_source_only_allows_outbound_picking(self):
        """Test that allow_as_source=True allows creating outbound pickings.
        
        CASO 3.4 - Step 3: Should be able to create DEPOS → Customer.
        """
        # This should NOT raise an error
        try:
            picking = self.env['stock.picking'].with_user(self.source_only_user).create({
                'picking_type_id': self.warehouse.out_type_id.id,
                'location_id': self.location_stock.id,
                'location_dest_id': self.location_customer.id,
            })
            
            move = self.env['stock.move'].with_user(self.source_only_user).create({
                'name': 'Outbound Move',
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'product_uom': self.product.uom_id.id,
                'picking_id': picking.id,
                'location_id': self.location_stock.id,
                'location_dest_id': self.location_customer.id,
            })
            
            # Should be able to confirm
            picking.with_user(self.source_only_user).action_confirm()
            
        except (UserError, ValidationError) as e:
            self.fail(f"Source-only user should be able to create outbound picking: {str(e)}")

    def test_source_only_blocks_inbound_picking(self):
        """Test that allow_as_source=True blocks creating inbound pickings.
        
        CASO 3.4 - Step 4: Should NOT be able to create Supplier → DEPOS.
        """
        # Create inbound picking (Supplier → Warehouse)
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.in_type_id.id,
            'location_id': self.location_supplier.id,
            'location_dest_id': self.location_stock.id,
        })
        
        # Attempt to create move should fail (constraint validation)
        with self.assertRaises(ValidationError) as context:
            self.env['stock.move'].with_user(self.source_only_user).create({
                'name': 'Inbound Move',
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'product_uom': self.product.uom_id.id,
                'picking_id': picking.id,
                'location_id': self.location_supplier.id,
                'location_dest_id': self.location_stock.id,
            })
        
        # CASO 3.4 - Step 5: Error should mention "destination" permission
        self.assertIn('destination', str(context.exception).lower())

    # ========================================================================
    # CASO 3.5: allow_as_destination permission (inbound only)
    # ========================================================================

    def test_destination_only_allows_inbound_picking(self):
        """Test that allow_as_destination=True allows creating inbound pickings.
        
        CASO 3.5 - Step 3: Should be able to create Supplier → DEPOS.
        """
        # This should NOT raise an error
        try:
            picking = self.env['stock.picking'].with_user(self.dest_only_user).create({
                'picking_type_id': self.warehouse.in_type_id.id,
                'location_id': self.location_supplier.id,
                'location_dest_id': self.location_stock.id,
            })
            
            move = self.env['stock.move'].with_user(self.dest_only_user).create({
                'name': 'Inbound Move',
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'product_uom': self.product.uom_id.id,
                'picking_id': picking.id,
                'location_id': self.location_supplier.id,
                'location_dest_id': self.location_stock.id,
            })
            
            # Should be able to confirm
            picking.with_user(self.dest_only_user).action_confirm()
            
        except (UserError, ValidationError) as e:
            self.fail(f"Destination-only user should be able to create inbound picking: {str(e)}")

    def test_destination_only_blocks_outbound_picking(self):
        """Test that allow_as_destination=True blocks creating outbound pickings.
        
        CASO 3.5 - Step 4: Should NOT be able to create DEPOS → Customer.
        """
        # Create outbound picking (Warehouse → Customer)
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Attempt to create move should fail (constraint validation)
        with self.assertRaises(ValidationError) as context:
            self.env['stock.move'].with_user(self.dest_only_user).create({
                'name': 'Outbound Move',
                'product_id': self.product.id,
                'product_uom_qty': 10,
                'product_uom': self.product.uom_id.id,
                'picking_id': picking.id,
                'location_id': self.location_stock.id,
                'location_dest_id': self.location_customer.id,
            })
        
        # CASO 3.5 - Step 5: Error should mention "source" permission
        self.assertIn('source', str(context.exception).lower())
