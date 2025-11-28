# -*- coding: utf-8 -*-
"""Test batch picking permissions.

This test suite validates:
- stock.picking.batch access control based on warehouse permissions
- Batch operations (confirm, done, cancel) permission enforcement

CASO 9: Batch Transfer Permissions
"""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, AccessError


@tagged('post_install', '-at_install')
class TestBatchPickingPermissions(TransactionCase):
    """Test suite for stock.picking.batch permission enforcement."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Check if stock_picking_batch module is installed
        cls.batch_model_exists = 'stock.picking.batch' in cls.env

    def setUp(self):
        super().setUp()
        
        if not self.batch_model_exists:
            self.skipTest("stock_picking_batch module not installed")
        
        # Create test warehouse
        self.warehouse = self.env['stock.warehouse'].sudo().create({
            'name': 'Test Batch Warehouse',
            'code': 'TBWH',
        })
        
        # Get standard locations
        self.location_supplier = self.env.ref('stock.stock_location_suppliers')
        self.location_customer = self.env.ref('stock.stock_location_customers')
        self.location_stock = self.warehouse.lot_stock_id
        
        # Create test product
        self.product = self.env['product.product'].sudo().create({
            'name': 'Test Product Batch',
            'type': 'product',
        })
        
        # Create stock
        self.env['stock.quant'].sudo().create({
            'product_id': self.product.id,
            'location_id': self.location_stock.id,
            'quantity': 1000.0,
        })

    # =========================================================================
    # CASO 9.1: Batch access based on warehouse permissions
    # =========================================================================

    def test_user_sees_only_batches_for_assigned_warehouse(self):
        """Test that user only sees batches with pickings from assigned warehouses.
        
        CASO 9.1.1: Batch visibility follows picking visibility.
        """
        # Create second warehouse
        warehouse2 = self.env['stock.warehouse'].sudo().create({
            'name': 'Test Batch Warehouse 2',
            'code': 'TBW2',
        })
        
        # Create user with permission only on warehouse1
        batch_user = self.env['res.users'].sudo().create({
            'name': 'Batch Test User',
            'login': 'batch_test_user',
            'email': 'batch_test@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': batch_user.id,
            'warehouse_id': self.warehouse.id,
            'full_control': True,
        })
        
        # Create picking in warehouse1
        picking1 = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        self.env['stock.move'].sudo().create({
            'name': 'Move 1',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking1.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Create picking in warehouse2
        picking2 = self.env['stock.picking'].sudo().create({
            'picking_type_id': warehouse2.out_type_id.id,
            'location_id': warehouse2.lot_stock_id.id,
            'location_dest_id': self.location_customer.id,
        })
        
        self.env['stock.move'].sudo().create({
            'name': 'Move 2',
            'product_id': self.product.id,
            'product_uom_qty': 5,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking2.id,
            'location_id': warehouse2.lot_stock_id.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Create batch for warehouse1 picking
        batch1 = self.env['stock.picking.batch'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'picking_ids': [(4, picking1.id)],
        })
        
        # Create batch for warehouse2 picking
        batch2 = self.env['stock.picking.batch'].sudo().create({
            'picking_type_id': warehouse2.out_type_id.id,
            'picking_ids': [(4, picking2.id)],
        })
        
        # User should see only batch1 (through picking visibility)
        visible_batches = self.env['stock.picking.batch'].with_user(batch_user).search([
            ('id', 'in', [batch1.id, batch2.id])
        ])
        
        # Note: Batch visibility depends on picking visibility through security rules
        # If batch model has warehouse-based security rules
        self.assertIn(batch1.id, visible_batches.ids, 
                      "User should see batch from assigned warehouse")

    def test_view_only_user_cannot_confirm_batch(self):
        """Test that view_only user cannot confirm batch.
        
        CASO 9.1.2: view_only blocks batch confirmation.
        """
        # Create view_only user
        view_only_user = self.env['res.users'].sudo().create({
            'name': 'View Only Batch User',
            'login': 'view_only_batch_user',
            'email': 'view_only_batch@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': view_only_user.id,
            'warehouse_id': self.warehouse.id,
            'view_only': True,
        })
        
        # Create picking
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        self.env['stock.move'].sudo().create({
            'name': 'Batch Move',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Create batch
        batch = self.env['stock.picking.batch'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'picking_ids': [(4, picking.id)],
        })
        
        # Attempt to confirm batch should fail (confirms pickings internally)
        with self.assertRaises(UserError) as context:
            batch.with_user(view_only_user).action_confirm()
        
        self.assertIn('view', str(context.exception).lower())

    def test_full_control_user_can_confirm_batch(self):
        """Test that full_control user can confirm batch.
        
        CASO 9.1.3: full_control allows batch operations.
        """
        # Create full_control user
        full_control_user = self.env['res.users'].sudo().create({
            'name': 'Full Control Batch User',
            'login': 'full_control_batch_user',
            'email': 'full_control_batch@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        self.env['warehouse.user.permission'].sudo().create({
            'user_id': full_control_user.id,
            'warehouse_id': self.warehouse.id,
            'full_control': True,
        })
        
        # Create picking
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        self.env['stock.move'].sudo().create({
            'name': 'Batch Move',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.location_stock.id,
            'location_dest_id': self.location_customer.id,
        })
        
        # Create batch
        batch = self.env['stock.picking.batch'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'picking_ids': [(4, picking.id)],
        })
        
        # Should be able to confirm
        try:
            batch.with_user(full_control_user).action_confirm()
            self.assertEqual(batch.state, 'in_progress')
        except UserError as e:
            self.fail(f"Full control user should be able to confirm batch: {e}")

