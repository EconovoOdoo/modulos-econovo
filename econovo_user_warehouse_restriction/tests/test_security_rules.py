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
        
        # Create restricted user WITHOUT Settings access
        self.restricted_user = self.env['res.users'].create({
            'name': 'Test Restricted User',
            'login': 'test_restricted_security',
            'email': 'test_restricted_security@test.com',
            'groups_id': [(6, 0, [self.group_stock_user.id])],
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
