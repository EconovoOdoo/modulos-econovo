# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase


class TestEconovoMrpProductionLocationDestIdBasedInWorkcenter(TransactionCase):
    """Test the Econovo MRP Production Location Dest ID Based in Workcenter functionality"""

    def setUp(self):
        super().setUp()
        
        # Create test locations
        self.warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        self.custom_dest_location = self.env['stock.location'].create({
            'name': 'Custom Destination',
            'usage': 'internal',
            'location_id': self.warehouse.lot_stock_id.id,
        })
        
        # Create test workcenter with custom destination
        self.workcenter = self.env['mrp.workcenter'].create({
            'name': 'Test Workcenter',
            'location_dest_id': self.custom_dest_location.id,
        })
        
        # Create test product
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
        })
        
        # Create simple BOM with routing
        self.bom = self.env['mrp.bom'].create({
            'product_id': self.product.id,
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
        })
        
        # Create routing with our test workcenter
        self.routing = self.env['mrp.routing'].create({
            'name': 'Test Routing',
        })
        
        self.operation = self.env['mrp.routing.workcenter'].create({
            'name': 'Test Operation',
            'routing_id': self.routing.id,
            'workcenter_id': self.workcenter.id,
            'time_cycle': 10,
            'sequence': 10,
        })
        
        self.bom.routing_id = self.routing.id

    def test_workcenter_has_custom_destination(self):
        """Test that workcenter shows it has a custom destination"""
        self.assertTrue(self.workcenter.has_custom_destination)
        
        # Test workcenter without custom destination
        workcenter_no_dest = self.env['mrp.workcenter'].create({
            'name': 'Workcenter No Dest',
        })
        self.assertFalse(workcenter_no_dest.has_custom_destination)

    def test_production_uses_workcenter_destination(self):
        """Test that production order uses workcenter destination location"""
        
        # Create production order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        
        # Check that the production uses the workcenter's custom destination
        self.assertEqual(
            production.location_dest_id,
            self.custom_dest_location,
            "Production should use workcenter's custom destination location"
        )
        
        # Check the computed field shows the workcenter destination
        self.assertEqual(
            production.workcenter_location_dest_id,
            self.custom_dest_location,
            "Workcenter destination field should show the custom location"
        )

    def test_production_fallback_to_default_destination(self):
        """Test that production falls back to default when no workcenter destination"""
        
        # Create workcenter without custom destination
        workcenter_no_dest = self.env['mrp.workcenter'].create({
            'name': 'Workcenter No Dest',
        })
        
        # Create routing and operation with this workcenter
        routing_no_dest = self.env['mrp.routing'].create({
            'name': 'Routing No Dest',
        })
        
        operation_no_dest = self.env['mrp.routing.workcenter'].create({
            'name': 'Operation No Dest',
            'routing_id': routing_no_dest.id,
            'workcenter_id': workcenter_no_dest.id,
            'time_cycle': 10,
            'sequence': 10,
        })
        
        # Create BOM with this routing
        bom_no_dest = self.env['mrp.bom'].create({
            'product_id': self.product.id,
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'routing_id': routing_no_dest.id,
        })
        
        # Create production order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': bom_no_dest.id,
        })
        
        # Should use default destination from picking type
        default_dest = production.picking_type_id.default_location_dest_id
        self.assertEqual(
            production.location_dest_id,
            default_dest,
            "Production should use default destination when no workcenter destination"
        )
        
        # Workcenter destination field should be empty
        self.assertFalse(
            production.workcenter_location_dest_id,
            "Workcenter destination field should be empty"
        )

    def test_multiple_workcenters_uses_last_destination(self):
        """Test that when multiple workcenters have destinations, the LAST one is used"""
        
        # Create additional test locations
        self.first_dest_location = self.env['stock.location'].create({
            'name': 'First Destination',
            'usage': 'internal',
            'location_id': self.warehouse.lot_stock_id.id,
        })
        
        self.last_dest_location = self.env['stock.location'].create({
            'name': 'Last Destination', 
            'usage': 'internal',
            'location_id': self.warehouse.lot_stock_id.id,
        })
        
        # Create multiple workcenters with destinations
        self.first_workcenter = self.env['mrp.workcenter'].create({
            'name': 'First Workcenter',
            'location_dest_id': self.first_dest_location.id,
        })
        
        self.last_workcenter = self.env['mrp.workcenter'].create({
            'name': 'Last Workcenter',
            'location_dest_id': self.last_dest_location.id,
        })
        
        # Create routing with multiple operations
        multi_routing = self.env['mrp.routing'].create({
            'name': 'Multi Workcenter Routing',
        })
        
        # First operation (sequence 10)
        self.env['mrp.routing.workcenter'].create({
            'name': 'First Operation',
            'routing_id': multi_routing.id,
            'workcenter_id': self.first_workcenter.id,
            'time_cycle': 10,
            'sequence': 10,
        })
        
        # Last operation (sequence 20) 
        self.env['mrp.routing.workcenter'].create({
            'name': 'Last Operation',
            'routing_id': multi_routing.id,
            'workcenter_id': self.last_workcenter.id,
            'time_cycle': 15,
            'sequence': 20,
        })
        
        # Create BOM with multi-workcenter routing
        multi_bom = self.env['mrp.bom'].create({
            'product_id': self.product.id,
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'routing_id': multi_routing.id,
        })
        
        # Create production order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': multi_bom.id,
        })
        
        # Should use the LAST workcenter's destination (not the first)
        self.assertEqual(
            production.location_dest_id,
            self.last_dest_location,
            "Production should use the LAST workcenter's destination location"
        )
        
        # Check the computed field shows the last workcenter destination
        self.assertEqual(
            production.workcenter_location_dest_id,
            self.last_dest_location,
            "Workcenter destination field should show the LAST workcenter's location"
        )

    def test_merge_manufacturing_orders_without_null_violation(self):
        """Test that merging manufacturing orders doesn't cause NULL violation on location_src_id
        
        This test validates the fix for the bug where action_merge() caused:
        psycopg2.errors.NotNullViolation: el valor null para la columna «location_src_id» 
        de la relación «mrp_production» viola la restricción not null
        
        Root cause: When merging MOs, workorders don't exist yet in the new merged MO,
        so _compute_locations() must fall back to picking_type/warehouse defaults.
        The fix ensures fallback_loc is always computed, preventing NULL values.
        """
        
        # Create first production order with workcenter routing
        production_1 = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 5.0,
            'bom_id': self.bom.id,
        })
        
        # Create second production order with same product/BOM
        production_2 = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 3.0,
            'bom_id': self.bom.id,
        })
        
        # Confirm both production orders to create workorders
        production_1.action_confirm()
        production_2.action_confirm()
        
        # Verify both have workorders with workcenter destinations BEFORE merge
        self.assertTrue(
            production_1.workorder_ids,
            "Production 1 should have workorders after confirmation"
        )
        self.assertTrue(
            production_2.workorder_ids,
            "Production 2 should have workorders after confirmation"
        )
        self.assertEqual(
            production_1.location_dest_id,
            self.custom_dest_location,
            "Production 1 should use workcenter destination before merge"
        )
        self.assertEqual(
            production_2.location_dest_id,
            self.custom_dest_location,
            "Production 2 should use workcenter destination before merge"
        )
        
        # Store original IDs for verification
        production_ids = production_1 | production_2
        
        # CRITICAL TEST: Merge the production orders
        # This should NOT raise NotNullViolation on location_src_id
        try:
            merged_production = production_ids.action_merge()
            merge_succeeded = True
        except Exception as e:
            merge_succeeded = False
            merge_error = str(e)
        
        # Assert merge succeeded without NULL violation
        self.assertTrue(
            merge_succeeded,
            f"Merge should succeed without errors. Got error: {merge_error if not merge_succeeded else 'None'}"
        )
        
        # Get the merged production record
        if isinstance(merged_production, dict):
            # action_merge returns action dict, extract production from context
            merged_prod_id = merged_production.get('res_id')
            merged_prod = self.env['mrp.production'].browse(merged_prod_id)
        else:
            merged_prod = merged_production
        
        # Verify locations are NOT NULL (critical assertion for the fix)
        self.assertTrue(
            merged_prod.location_src_id,
            "Merged production MUST have location_src_id (not NULL)"
        )
        self.assertTrue(
            merged_prod.location_dest_id,
            "Merged production MUST have location_dest_id (not NULL)"
        )
        
        # Verify quantities were properly merged
        expected_qty = 5.0 + 3.0  # production_1 + production_2
        self.assertEqual(
            merged_prod.product_qty,
            expected_qty,
            f"Merged production should have combined quantity of {expected_qty}"
        )
        
        # After action_confirm on merged MO, workorders are created
        # and locations should update to workcenter destinations
        merged_prod.action_confirm()
        
        # Verify workorders exist after confirmation
        self.assertTrue(
            merged_prod.workorder_ids,
            "Merged production should have workorders after confirmation"
        )
        
        # Verify destination location updated to workcenter destination
        # (validates that workcenter functionality is preserved after merge)
        self.assertEqual(
            merged_prod.location_dest_id,
            self.custom_dest_location,
            "Merged production should use workcenter destination after workorders created"
        )
        
        # Verify the computed field is correct
        self.assertEqual(
            merged_prod.workcenter_location_dest_id,
            self.custom_dest_location,
            "Workcenter destination field should be correctly computed"
        )
