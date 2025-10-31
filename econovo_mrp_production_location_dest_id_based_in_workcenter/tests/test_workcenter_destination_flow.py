# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWorkcenterDestinationFlow(TransactionCase):
    """Test suite for the normal flow of workcenter destination functionality
    
    This test suite validates the core functionality of the module in typical
    manufacturing scenarios, ensuring that destination locations are correctly
    determined and applied throughout the production lifecycle.
    """

    def setUp(self):
        """Set up test data for workcenter destination flow tests"""
        super(TestWorkcenterDestinationFlow, self).setUp()
        
        # Get warehouse and basic locations
        self.warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        self.stock_location = self.warehouse.lot_stock_id
        
        # Create custom destination locations for workcenters
        self.wc_location_1 = self.env['stock.location'].create({
            'name': 'Workcenter 1 Output',
            'usage': 'internal',
            'location_id': self.stock_location.id,
        })
        
        self.wc_location_2 = self.env['stock.location'].create({
            'name': 'Workcenter 2 Output',
            'usage': 'internal',
            'location_id': self.stock_location.id,
        })
        
        self.wc_location_final = self.env['stock.location'].create({
            'name': 'Final Assembly Area',
            'usage': 'internal',
            'location_id': self.stock_location.id,
        })
        
        # Create workcenters with custom destinations
        self.workcenter_cutting = self.env['mrp.workcenter'].create({
            'name': 'Cutting Station',
            'location_dest_id': self.wc_location_1.id,
            'resource_calendar_id': self.env.ref('resource.resource_calendar_std').id,
        })
        
        self.workcenter_assembly = self.env['mrp.workcenter'].create({
            'name': 'Assembly Station',
            'location_dest_id': self.wc_location_2.id,
            'resource_calendar_id': self.env.ref('resource.resource_calendar_std').id,
        })
        
        self.workcenter_finishing = self.env['mrp.workcenter'].create({
            'name': 'Finishing Station',
            'location_dest_id': self.wc_location_final.id,
            'resource_calendar_id': self.env.ref('resource.resource_calendar_std').id,
        })
        
        # Create workcenter without custom destination (for fallback testing)
        self.workcenter_no_dest = self.env['mrp.workcenter'].create({
            'name': 'Generic Station',
            'resource_calendar_id': self.env.ref('resource.resource_calendar_std').id,
        })
        
        # Create products
        self.product_final = self.env['product.product'].create({
            'name': 'Final Product',
            'type': 'product',
        })
        
        self.product_component = self.env['product.product'].create({
            'name': 'Component A',
            'type': 'product',
        })
        
        # Create initial stock for components
        self.env['stock.quant'].create({
            'product_id': self.product_component.id,
            'location_id': self.stock_location.id,
            'quantity': 100.0,
        })
        
        # Create BOM operations
        self.operation_cutting = self.env['mrp.routing.workcenter'].create({
            'name': 'Cut Material',
            'workcenter_id': self.workcenter_cutting.id,
            'time_cycle': 10,
            'sequence': 10,
        })
        
        self.operation_assembly = self.env['mrp.routing.workcenter'].create({
            'name': 'Assemble Parts',
            'workcenter_id': self.workcenter_assembly.id,
            'time_cycle': 20,
            'sequence': 20,
        })
        
        self.operation_finishing = self.env['mrp.routing.workcenter'].create({
            'name': 'Finish Product',
            'workcenter_id': self.workcenter_finishing.id,
            'time_cycle': 15,
            'sequence': 30,
        })
        
        # Create BOM with multiple operations
        self.bom_multi = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_final.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'operation_ids': [(6, 0, [
                self.operation_cutting.id,
                self.operation_assembly.id,
                self.operation_finishing.id,
            ])],
        })
        
        # Add component to BOM
        self.env['mrp.bom.line'].create({
            'bom_id': self.bom_multi.id,
            'product_id': self.product_component.id,
            'product_qty': 2.0,
            'operation_id': self.operation_assembly.id,
        })
        
        # Get manufacturing picking type
        self.picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'),
            ('warehouse_id', '=', self.warehouse.id),
        ], limit=1)


    def test_01_basic_workcenter_destination_assignment(self):
        """Test basic flow: MO with single workcenter uses its destination"""
        
        # Create simple BOM with only finishing operation
        bom_simple = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_final.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'operation_ids': [(6, 0, [self.operation_finishing.id])],
        })
        
        # Create manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product_final.id,
            'bom_id': bom_simple.id,
            'product_qty': 5.0,
            'location_src_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type.id,
        })
        
        # Trigger compute methods
        production._compute_locations()
        production._compute_workcenter_location_dest()
        
        # Verify: Production uses workcenter destination
        self.assertEqual(
            production.location_dest_id,
            self.wc_location_final,
            "Production should use workcenter destination location"
        )
        self.assertEqual(
            production.workcenter_location_dest_id,
            self.wc_location_final,
            "Workcenter location should be properly computed"
        )
        
        # Verify finished moves have correct destination
        finished_moves = production.move_finished_ids.filtered(
            lambda m: m.product_id == self.product_final
        )
        self.assertTrue(finished_moves, "Should have finished product moves")
        for move in finished_moves:
            self.assertEqual(
                move.location_dest_id,
                self.wc_location_final,
                "Finished move should have workcenter destination"
            )


    def test_02_multiple_workcenters_uses_last_destination(self):
        """Test flow with multiple workcenters: Uses LAST workcenter destination"""
        
        # Create manufacturing order with multi-operation BOM
        production = self.env['mrp.production'].create({
            'product_id': self.product_final.id,
            'bom_id': self.bom_multi.id,
            'product_qty': 10.0,
            'location_src_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type.id,
        })
        
        # Trigger compute methods
        production._compute_locations()
        production._compute_workcenter_location_dest()
        
        # Verify: Uses last workcenter destination (finishing station)
        self.assertEqual(
            production.location_dest_id,
            self.wc_location_final,
            "Production should use LAST workcenter destination (Finishing Station)"
        )
        
        # Verify workcenter_location_dest_id computed field
        self.assertEqual(
            production.workcenter_location_dest_id,
            self.wc_location_final,
            "Computed field should show last workcenter destination"
        )
        
        # Verify workorders exist
        self.assertEqual(
            len(production.workorder_ids),
            3,
            "Should have 3 workorders (cutting, assembly, finishing)"
        )
        
        # Verify finished moves destination
        finished_moves = production.move_finished_ids.filtered(
            lambda m: m.product_id == self.product_final
        )
        for move in finished_moves:
            self.assertEqual(
                move.location_dest_id,
                self.wc_location_final,
                "Finished move destination should match production destination"
            )


    def test_03_fallback_to_picking_type_default(self):
        """Test fallback: MO without workcenter destination uses picking type default"""
        
        # Create BOM with workcenter that has NO custom destination
        operation_no_dest = self.env['mrp.routing.workcenter'].create({
            'name': 'Generic Operation',
            'workcenter_id': self.workcenter_no_dest.id,
            'time_cycle': 10,
            'sequence': 10,
        })
        
        bom_no_dest = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_final.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'operation_ids': [(6, 0, [operation_no_dest.id])],
        })
        
        # Ensure picking type has default destination
        picking_type_dest = self.env['stock.location'].create({
            'name': 'Picking Type Default Output',
            'usage': 'internal',
            'location_id': self.stock_location.id,
        })
        self.picking_type.write({
            'default_location_dest_id': picking_type_dest.id,
        })
        
        # Create manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product_final.id,
            'bom_id': bom_no_dest.id,
            'product_qty': 3.0,
            'location_src_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type.id,
        })
        
        # Trigger compute methods
        production._compute_locations()
        production._compute_workcenter_location_dest()
        
        # Verify: Falls back to picking type destination
        self.assertEqual(
            production.location_dest_id,
            picking_type_dest,
            "Production should fallback to picking type default destination"
        )
        self.assertFalse(
            production.workcenter_location_dest_id,
            "Should have no workcenter destination computed"
        )


    def test_04_complete_production_flow_with_workcenter_destination(self):
        """Test complete production flow: Create, confirm, produce, and validate moves"""
        
        # Create manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product_final.id,
            'bom_id': self.bom_multi.id,
            'product_qty': 5.0,
            'location_src_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type.id,
        })
        
        # Trigger compute to ensure locations are set
        production._compute_locations()
        production._compute_workcenter_location_dest()
        
        # Verify initial state
        self.assertEqual(production.state, 'draft', "Should start in draft state")
        self.assertEqual(
            production.location_dest_id,
            self.wc_location_final,
            "Should have workcenter destination set"
        )
        
        # Confirm production order
        production.action_confirm()
        self.assertEqual(production.state, 'confirmed', "Should be confirmed")
        
        # Check components are reserved
        raw_moves = production.move_raw_ids.filtered(
            lambda m: m.product_id == self.product_component
        )
        self.assertTrue(raw_moves, "Should have component moves")
        
        # Verify raw moves source location
        for move in raw_moves:
            self.assertEqual(
                move.location_id,
                self.stock_location,
                "Raw moves should come from stock location"
            )
        
        # Verify finished moves destination (critical test)
        finished_moves = production.move_finished_ids.filtered(
            lambda m: m.product_id == self.product_final
        )
        self.assertTrue(finished_moves, "Should have finished moves")
        for move in finished_moves:
            self.assertEqual(
                move.location_dest_id,
                self.wc_location_final,
                "Finished moves should go to workcenter destination"
            )
            self.assertEqual(
                move.location_id,
                production.location_src_id,
                "Finished moves should come from production location"
            )
        
        # Produce quantity
        production.qty_producing = production.product_qty
        
        # Validate production
        production.button_mark_done()
        
        # Verify final state
        self.assertEqual(production.state, 'done', "Production should be done")
        
        # Verify moves are done and destination is correct
        for move in finished_moves:
            self.assertEqual(move.state, 'done', "Finished moves should be done")
            self.assertEqual(
                move.location_dest_id,
                self.wc_location_final,
                "Finished moves destination should remain workcenter location"
            )
        
        # Verify stock levels
        quants = self.env['stock.quant'].search([
            ('product_id', '=', self.product_final.id),
            ('location_id', '=', self.wc_location_final.id),
        ])
        self.assertTrue(quants, "Should have stock in final location")
        total_qty = sum(quants.mapped('quantity'))
        self.assertEqual(
            total_qty,
            5.0,
            "Should have produced 5 units in workcenter destination"
        )


    def test_05_location_synchronization_after_changes(self):
        """Test that location synchronization works when workcenter changes"""
        
        # Create production
        production = self.env['mrp.production'].create({
            'product_id': self.product_final.id,
            'bom_id': self.bom_multi.id,
            'product_qty': 8.0,
            'location_src_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type.id,
        })
        
        # Initial compute
        production._compute_locations()
        production._compute_workcenter_location_dest()
        
        # Verify initial destination (should be final workcenter)
        initial_dest = production.location_dest_id
        self.assertEqual(
            initial_dest,
            self.wc_location_final,
            "Initial destination should be final workcenter location"
        )
        
        # Get finished moves
        finished_moves = production.move_finished_ids.filtered(
            lambda m: m.product_id == self.product_final
        )
        
        # Verify moves have correct initial destination
        for move in finished_moves:
            self.assertEqual(
                move.location_dest_id,
                self.wc_location_final,
                "Moves should initially have final workcenter destination"
            )
        
        # Simulate a change: Remove last operation's workcenter destination
        # In real scenario, this could happen via UI or during split operations
        self.workcenter_finishing.write({'location_dest_id': False})
        
        # Recompute locations (simulates what happens during various operations)
        production._compute_locations()
        production._compute_workcenter_location_dest()
        
        # Verify new destination (should now be assembly workcenter, the previous last one)
        self.assertEqual(
            production.location_dest_id,
            self.wc_location_2,
            "Destination should change to previous workcenter with destination"
        )
        
        # Verify moves are synchronized
        finished_moves.invalidate_recordset()  # Refresh from DB
        for move in finished_moves:
            self.assertEqual(
                move.location_dest_id,
                self.wc_location_2,
                "Moves should be synchronized to new destination"
            )


    def test_06_helper_method_get_workcenter_destination_info(self):
        """Test the helper method that provides workcenter destination information"""
        
        # Create production with multiple workcenters
        production = self.env['mrp.production'].create({
            'product_id': self.product_final.id,
            'bom_id': self.bom_multi.id,
            'product_qty': 5.0,
            'location_src_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type.id,
        })
        
        # Get workcenter destination info
        info = production._get_workcenter_destination_info()
        
        # Verify we have information for all workcenters with destinations
        self.assertEqual(
            len(info),
            3,
            "Should have info for 3 workcenters with destinations"
        )
        
        # Verify each info entry has required keys
        required_keys = ['workcenter', 'operation', 'destination']
        for entry in info:
            for key in required_keys:
                self.assertIn(key, entry, f"Info entry should have '{key}' key")
        
        # Verify workcenter names
        workcenter_names = [entry['workcenter'].name for entry in info]
        self.assertIn('Cutting Station', workcenter_names)
        self.assertIn('Assembly Station', workcenter_names)
        self.assertIn('Finishing Station', workcenter_names)
        
        # Verify destinations
        destinations = [entry['destination'] for entry in info]
        self.assertIn(self.wc_location_1, destinations)
        self.assertIn(self.wc_location_2, destinations)
        self.assertIn(self.wc_location_final, destinations)


    def test_07_production_without_bom_operations(self):
        """Test production with BOM that has no operations (edge case)"""
        
        # Create simple BOM without operations
        bom_no_ops = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_final.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
        })
        
        # Add component
        self.env['mrp.bom.line'].create({
            'bom_id': bom_no_ops.id,
            'product_id': self.product_component.id,
            'product_qty': 1.0,
        })
        
        # Set picking type default destination
        default_dest = self.env['stock.location'].create({
            'name': 'Default Manufacturing Output',
            'usage': 'internal',
            'location_id': self.stock_location.id,
        })
        self.picking_type.write({
            'default_location_dest_id': default_dest.id,
        })
        
        # Create production
        production = self.env['mrp.production'].create({
            'product_id': self.product_final.id,
            'bom_id': bom_no_ops.id,
            'product_qty': 2.0,
            'location_src_id': self.stock_location.id,
            'location_dest_id': self.stock_location.id,
            'picking_type_id': self.picking_type.id,
        })
        
        # Trigger compute
        production._compute_locations()
        production._compute_workcenter_location_dest()
        
        # Verify: Should use picking type default (no workcenters)
        self.assertEqual(
            production.location_dest_id,
            default_dest,
            "Should use picking type default when no operations"
        )
        self.assertFalse(
            production.workcenter_location_dest_id,
            "Should have no workcenter destination"
        )
        self.assertFalse(
            production.workorder_ids,
            "Should have no workorders"
        )


    def test_08_sync_finished_moves_location_method(self):
        """Test the _sync_finished_moves_location method directly"""
        
        # Create production
        production = self.env['mrp.production'].create({
            'product_id': self.product_final.id,
            'bom_id': self.bom_multi.id,
            'product_qty': 5.0,
            'location_src_id': self.stock_location.id,
            'location_dest_id': self.wc_location_1.id,  # Set to different location initially
            'picking_type_id': self.picking_type.id,
        })
        
        # Get finished moves
        finished_moves = production.move_finished_ids.filtered(
            lambda m: m.product_id == self.product_final
        )
        
        # Verify initial state (moves should have wc_location_1)
        for move in finished_moves:
            self.assertEqual(
                move.location_dest_id,
                self.wc_location_1,
                "Initial move destination should be wc_location_1"
            )
        
        # Change production destination
        production.location_dest_id = self.wc_location_final
        
        # Call sync method
        production._sync_finished_moves_location()
        
        # Verify moves are updated
        finished_moves.invalidate_recordset()
        for move in finished_moves:
            self.assertEqual(
                move.location_dest_id,
                self.wc_location_final,
                "Moves should be synchronized to new location"
            )
        
        # Confirm production and create reservations
        production.action_confirm()
        
        # Change location again
        production.location_dest_id = self.wc_location_2
        production._sync_finished_moves_location()
        
        # Verify move_lines are also synchronized
        finished_moves.invalidate_recordset()
        for move in finished_moves:
            self.assertEqual(
                move.location_dest_id,
                self.wc_location_2,
                "Moves should be updated to wc_location_2"
            )
            
            # Check move lines if they exist
            for move_line in move.move_line_ids:
                self.assertEqual(
                    move_line.location_dest_id,
                    self.wc_location_2,
                    "Move lines should also be synchronized"
                )
