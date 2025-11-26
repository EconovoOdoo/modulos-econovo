# -*- coding: utf-8 -*-
"""Test view_only permission restrictions on stock.picking operations.

This test suite validates that users with view_only permission cannot:
- Write/edit pickings (write)
- Delete pickings (unlink)
- Validate pickings (button_validate)
- Cancel pickings (action_cancel)

Test coverage for CRITICAL security bug fix.
"""

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestViewOnlyRestrictions(TransactionCase):
    """Test suite for view_only permission enforcement on stock.picking."""

    def setUp(self):
        """Create test environment with view_only user and test picking."""
        super(TestViewOnlyRestrictions, self).setUp()
        
        # Create test warehouse
        self.warehouse = self.env['stock.warehouse'].sudo().create({
            'name': 'Test View Only Warehouse',
            'code': 'TVOWH',
        })
        
        # Create regular user with stock_user group
        self.view_only_user = self.env['res.users'].sudo().create({
            'name': 'View Only Test User',
            'login': 'viewonly_test',
            'email': 'viewonly@test.com',
            'groups_id': [(6, 0, [
                self.env.ref('stock.group_stock_user').id,
            ])],
        })
        
        # Create permission with view_only enabled
        self.permission = self.env['warehouse.user.permission'].sudo().create({
            'user_id': self.view_only_user.id,
            'warehouse_id': self.warehouse.id,
            'view_only': True,
            'full_control': False,
            'allow_as_source': False,
            'allow_as_destination': False,
        })
        
        # Create test product
        self.product = self.env['product.product'].sudo().create({
            'name': 'Test Product View Only',
            'type': 'product',
        })
        
        # Create test picking as admin
        self.picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        })
        
        # Create move line
        self.env['stock.move'].sudo().create({
            'name': 'Test Move',
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'product_uom': self.product.uom_id.id,
            'picking_id': self.picking.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        })
        
        # Confirm picking
        self.picking.action_confirm()

    def test_view_only_blocks_write(self):
        """Test that view_only permission blocks write operations."""
        with self.assertRaises(UserError) as context:
            self.picking.with_user(self.view_only_user).write({
                'note': 'This should fail'
            })
        
        self.assertIn('view_only', str(context.exception).lower())

    def test_view_only_blocks_unlink(self):
        """Test that view_only permission blocks delete operations."""
        # Create draft picking for deletion test
        draft_picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        })
        
        with self.assertRaises(UserError) as context:
            draft_picking.with_user(self.view_only_user).unlink()
        
        self.assertIn('view_only', str(context.exception).lower())

    def test_view_only_blocks_validate(self):
        """Test that view_only permission blocks validate operations."""
        with self.assertRaises(UserError) as context:
            self.picking.with_user(self.view_only_user).button_validate()
        
        self.assertIn('view_only', str(context.exception).lower())

    def test_view_only_blocks_cancel(self):
        """Test that view_only permission blocks cancel operations."""
        with self.assertRaises(UserError) as context:
            self.picking.with_user(self.view_only_user).action_cancel()
        
        self.assertIn('view_only', str(context.exception).lower())

    def test_view_only_blocks_confirm(self):
        """Test that view_only permission blocks confirm operations."""
        # Create draft picking for confirm test
        draft_picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        })
        
        # Add move line
        self.env['stock.move'].sudo().create({
            'name': 'Test Move',
            'product_id': self.product.id,
            'product_uom_qty': 5,
            'product_uom': self.product.uom_id.id,
            'picking_id': draft_picking.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        })
        
        with self.assertRaises(UserError) as context:
            draft_picking.with_user(self.view_only_user).action_confirm()
        
        self.assertIn('view_only', str(context.exception).lower())

    def test_full_control_allows_write(self):
        """Test that full_control permission allows write operations."""
        # Update permission to full_control
        self.permission.sudo().write({
            'full_control': True,
            'view_only': False,
        })
        
        # This should NOT raise an error
        try:
            self.picking.with_user(self.view_only_user).write({
                'note': 'This should work'
            })
        except UserError:
            self.fail("full_control user should be able to write")

    def test_full_control_allows_cancel(self):
        """Test that full_control permission allows cancel operations."""
        # Update permission to full_control
        self.permission.sudo().write({
            'full_control': True,
            'view_only': False,
        })
        
        # This should NOT raise an error
        try:
            self.picking.with_user(self.view_only_user).action_cancel()
        except UserError:
            self.fail("full_control user should be able to cancel")

    def test_unrestricted_group_bypasses_view_only(self):
        """Test that group_warehouse_unrestricted bypasses view_only."""
        # Add unrestricted group to user
        self.view_only_user.sudo().write({
            'groups_id': [(4, self.env.ref(
                'econovo_user_warehouse_restriction.group_warehouse_unrestricted'
            ).id)]
        })
        
        # This should NOT raise an error
        try:
            self.picking.with_user(self.view_only_user).write({
                'note': 'Unrestricted user can write'
            })
        except UserError:
            self.fail("Unrestricted group should bypass view_only")
