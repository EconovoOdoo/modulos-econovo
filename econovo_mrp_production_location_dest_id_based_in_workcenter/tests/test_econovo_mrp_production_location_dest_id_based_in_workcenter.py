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
