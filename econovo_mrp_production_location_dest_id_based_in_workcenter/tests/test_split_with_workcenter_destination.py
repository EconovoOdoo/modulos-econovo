# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSplitWithWorkcenterDestination(TransactionCase):
    """Test suite for split operations with workcenter destination locations
    
    This test suite validates the behavior of split/backorder operations
    when workcenters have custom destination locations configured.
    
    Critical aspects tested:
    1. Location preservation/recomputation after split
    2. Moves synchronization with production location_dest_id
    3. Move_lines (reservations) consistency
    4. Multiple workcenters scenarios (last workcenter wins)
    5. Fallback behavior when no workcenter destinations configured
    
    Related:
    - Bug fix v17.0.1.3.0: _sync_finished_moves_location() implementation
    - Analysis: ANALISIS_SPLIT_INTERACCION.md sections 4-6
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Get warehouse and create test locations
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.env.company.id)], limit=1)
        
        cls.location_workcenter_a = cls.env['stock.location'].create({
            'name': 'Workcenter A Destination',
            'usage': 'internal',
            'location_id': cls.warehouse.lot_stock_id.id,
        })
        
        cls.location_workcenter_b = cls.env['stock.location'].create({
            'name': 'Workcenter B Destination',
            'usage': 'internal',
            'location_id': cls.warehouse.lot_stock_id.id,
        })
        
        cls.location_workcenter_c = cls.env['stock.location'].create({
            'name': 'Workcenter C Destination',
            'usage': 'internal',
            'location_id': cls.warehouse.lot_stock_id.id,
        })
        
        # Create test workcenters
        cls.workcenter_with_dest = cls.env['mrp.workcenter'].create({
            'name': 'Workcenter With Destination',
            'location_dest_id': cls.location_workcenter_a.id,
        })
        
        cls.workcenter_without_dest = cls.env['mrp.workcenter'].create({
            'name': 'Workcenter Without Destination',
        })
        
        cls.workcenter_dest_b = cls.env['mrp.workcenter'].create({
            'name': 'Workcenter Dest B',
            'location_dest_id': cls.location_workcenter_b.id,
        })
        
        cls.workcenter_dest_c = cls.env['mrp.workcenter'].create({
            'name': 'Workcenter Dest C',
            'location_dest_id': cls.location_workcenter_c.id,
        })
        
        # Create test product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product for Split',
            'type': 'product',
            'tracking': 'none',
        })
        
        # Create component for consumption (to enable reservations)
        cls.component = cls.env['product.product'].create({
            'name': 'Test Component',
            'type': 'product',
            'tracking': 'none',
        })
        
        # Add stock for component
        cls.env['stock.quant'].create({
            'product_id': cls.component.id,
            'location_id': cls.warehouse.lot_stock_id.id,
            'quantity': 1000.0,
        })
        
        # Create routing with workcenter that has destination
        cls.routing_single = cls.env['mrp.routing'].create({
            'name': 'Single Workcenter Routing',
        })
        
        cls.env['mrp.routing.workcenter'].create({
            'name': 'Operation With Destination',
            'routing_id': cls.routing_single.id,
            'workcenter_id': cls.workcenter_with_dest.id,
            'time_cycle': 10,
            'sequence': 10,
        })
        
        # Create BOM with routing (includes component for reservations)
        cls.bom_with_dest = cls.env['mrp.bom'].create({
            'product_id': cls.product.id,
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'routing_id': cls.routing_single.id,
        })
        
        # Add BOM line for component consumption
        cls.env['mrp.bom.line'].create({
            'bom_id': cls.bom_with_dest.id,
            'product_id': cls.component.id,
            'product_qty': 1.0,
        })
        
        # Create routing with multiple workcenters
        cls.routing_multi = cls.env['mrp.routing'].create({
            'name': 'Multi Workcenter Routing',
        })
        
        cls.env['mrp.routing.workcenter'].create({
            'name': 'First Operation No Dest',
            'routing_id': cls.routing_multi.id,
            'workcenter_id': cls.workcenter_without_dest.id,
            'time_cycle': 5,
            'sequence': 10,
        })
        
        cls.env['mrp.routing.workcenter'].create({
            'name': 'Second Operation Dest B',
            'routing_id': cls.routing_multi.id,
            'workcenter_id': cls.workcenter_dest_b.id,
            'time_cycle': 10,
            'sequence': 20,
        })
        
        cls.env['mrp.routing.workcenter'].create({
            'name': 'Third Operation Dest C (Last)',
            'routing_id': cls.routing_multi.id,
            'workcenter_id': cls.workcenter_dest_c.id,
            'time_cycle': 15,
            'sequence': 30,
        })
        
        # Create BOM with multi-workcenter routing
        cls.bom_multi_dest = cls.env['mrp.bom'].create({
            'product_id': cls.product.id,
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'routing_id': cls.routing_multi.id,
        })
        
        cls.env['mrp.bom.line'].create({
            'bom_id': cls.bom_multi_dest.id,
            'product_id': cls.component.id,
            'product_qty': 1.0,
        })
        
        # Create routing without any workcenter destinations
        cls.routing_no_dest = cls.env['mrp.routing'].create({
            'name': 'No Workcenter Dest Routing',
        })
        
        cls.env['mrp.routing.workcenter'].create({
            'name': 'Operation No Destination',
            'routing_id': cls.routing_no_dest.id,
            'workcenter_id': cls.workcenter_without_dest.id,
            'time_cycle': 10,
            'sequence': 10,
        })
        
        # Create BOM without workcenter destinations
        cls.bom_no_dest = cls.env['mrp.bom'].create({
            'product_id': cls.product.id,
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'routing_id': cls.routing_no_dest.id,
        })
        
        cls.env['mrp.bom.line'].create({
            'bom_id': cls.bom_no_dest.id,
            'product_id': cls.component.id,
            'product_qty': 1.0,
        })

    def test_01_split_preserves_workcenter_destination(self):
        """Test that location_dest_id is preserved/recomputed after split
        
        Validates:
        - Original MO maintains workcenter destination
        - Backorder recomputes and uses same workcenter destination
        - Both MOs have consistent location_dest_id
        - Moves are synchronized with production location
        
        Scenario:
        1. Create MO with qty=10, workcenter has location_dest_id
        2. Confirm MO (creates workorders)
        3. Split into qty=6 (original) and qty=4 (backorder)
        4. Verify both use workcenter destination
        5. Verify moves have correct location_dest_id
        """
        # Create manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 10.0,
            'bom_id': self.bom_with_dest.id,
        })
        
        # Confirm to create workorders
        production.action_confirm()
        
        # Verify initial state
        self.assertEqual(
            production.location_dest_id,
            self.location_workcenter_a,
            "Production should use workcenter destination before split"
        )
        
        self.assertTrue(
            production.workorder_ids,
            "Production should have workorders after confirmation"
        )
        
        # Get finished moves before split
        finished_moves_before = production.move_finished_ids.filtered(
            lambda m: m.product_id == production.product_id
        )
        
        self.assertTrue(
            finished_moves_before,
            "Production should have finished moves after confirmation"
        )
        
        # Execute split operation (qty=6 stays, qty=4 goes to backorder)
        split_wizard = self.env['mrp.production.split'].create({
            'production_id': production.id,
            'production_split_multi_id': False,
            'counter': 1,
        })
        
        split_wizard.split_line_ids = [(0, 0, {
            'quantity': 6.0,
            'user_id': self.env.user.id,
        })]
        
        # Execute split
        result = split_wizard.action_split()
        
        # Get the backorder MO
        backorder = self.env['mrp.production'].search([
            ('backorder_sequence', '>', 0),
            ('origin', 'like', production.name)
        ], limit=1, order='id desc')
        
        self.assertTrue(
            backorder,
            "Backorder should be created after split"
        )
        
        # CRITICAL ASSERTIONS: Verify locations
        
        # 1. Original MO maintains workcenter destination
        self.assertEqual(
            production.location_dest_id,
            self.location_workcenter_a,
            "Original MO should maintain workcenter destination after split"
        )
        
        # 2. Backorder recomputes to same workcenter destination
        self.assertEqual(
            backorder.location_dest_id,
            self.location_workcenter_a,
            "Backorder should recompute to same workcenter destination"
        )
        
        # 3. Verify quantities
        self.assertEqual(
            production.product_qty,
            6.0,
            "Original MO should have updated quantity"
        )
        
        self.assertEqual(
            backorder.product_qty,
            4.0,
            "Backorder should have remaining quantity"
        )
        
        # 4. Verify workorders exist in backorder
        self.assertTrue(
            backorder.workorder_ids,
            "Backorder should have workorders"
        )
        
        # 5. CRITICAL: Verify moves are synchronized (v17.0.1.3.0 fix)
        finished_moves_original = production.move_finished_ids.filtered(
            lambda m: m.product_id == production.product_id and m.state not in ('done', 'cancel')
        )
        
        finished_moves_backorder = backorder.move_finished_ids.filtered(
            lambda m: m.product_id == backorder.product_id and m.state not in ('done', 'cancel')
        )
        
        for move in finished_moves_original:
            self.assertEqual(
                move.location_dest_id,
                production.location_dest_id,
                f"Move {move.id} should have same location_dest_id as production (original)"
            )
        
        for move in finished_moves_backorder:
            self.assertEqual(
                move.location_dest_id,
                backorder.location_dest_id,
                f"Move {move.id} should have same location_dest_id as production (backorder)"
            )

    def test_02_split_with_multiple_workcenters_uses_last(self):
        """Test that split uses LAST workcenter destination
        
        Validates:
        - When multiple workcenters have destinations, LAST one is used
        - This applies to both original MO and backorder
        - Logic is consistent with module's _compute_locations()
        
        Scenario:
        1. Create MO with 3 workcenters:
           - WC1: no destination
           - WC2: destination B
           - WC3: destination C (LAST, should be used)
        2. Split MO
        3. Verify both MOs use location C (last workcenter)
        """
        # Create manufacturing order with multi-workcenter routing
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 10.0,
            'bom_id': self.bom_multi_dest.id,
        })
        
        production.action_confirm()
        
        # Verify uses LAST workcenter destination (C, not B)
        self.assertEqual(
            production.location_dest_id,
            self.location_workcenter_c,
            "Production should use LAST workcenter destination (C) before split"
        )
        
        # Execute split
        split_wizard = self.env['mrp.production.split'].create({
            'production_id': production.id,
            'production_split_multi_id': False,
            'counter': 1,
        })
        
        split_wizard.split_line_ids = [(0, 0, {
            'quantity': 7.0,
            'user_id': self.env.user.id,
        })]
        
        split_wizard.action_split()
        
        # Get backorder
        backorder = self.env['mrp.production'].search([
            ('backorder_sequence', '>', 0),
            ('origin', 'like', production.name)
        ], limit=1, order='id desc')
        
        # CRITICAL ASSERTIONS: Both should use location C (last workcenter)
        
        self.assertEqual(
            production.location_dest_id,
            self.location_workcenter_c,
            "Original MO should use LAST workcenter destination (C) after split"
        )
        
        self.assertEqual(
            backorder.location_dest_id,
            self.location_workcenter_c,
            "Backorder should use LAST workcenter destination (C)"
        )
        
        # Verify moves are synchronized
        for move in production.move_finished_ids.filtered(lambda m: m.product_id == production.product_id):
            self.assertEqual(
                move.location_dest_id,
                self.location_workcenter_c,
                "Original MO moves should use location C"
            )
        
        for move in backorder.move_finished_ids.filtered(lambda m: m.product_id == backorder.product_id):
            self.assertEqual(
                move.location_dest_id,
                self.location_workcenter_c,
                "Backorder moves should use location C"
            )

    def test_03_split_without_workcenter_destination_uses_fallback(self):
        """Test fallback to picking_type when no workcenter destination
        
        Validates:
        - When workcenters don't have destinations, uses picking_type default
        - Fallback logic works correctly after split
        - No NULL violations occur
        
        Scenario:
        1. Create MO with workcenter WITHOUT destination
        2. Split MO
        3. Verify both use picking_type default location
        """
        # Create manufacturing order without workcenter destinations
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 10.0,
            'bom_id': self.bom_no_dest.id,
        })
        
        production.action_confirm()
        
        # Get expected fallback location
        fallback_location = production.picking_type_id.default_location_dest_id
        
        # Verify uses fallback before split
        self.assertEqual(
            production.location_dest_id,
            fallback_location,
            "Production should use picking_type default when no workcenter destination"
        )
        
        # Execute split
        split_wizard = self.env['mrp.production.split'].create({
            'production_id': production.id,
            'production_split_multi_id': False,
            'counter': 1,
        })
        
        split_wizard.split_line_ids = [(0, 0, {
            'quantity': 4.0,
            'user_id': self.env.user.id,
        })]
        
        split_wizard.action_split()
        
        # Get backorder
        backorder = self.env['mrp.production'].search([
            ('backorder_sequence', '>', 0),
            ('origin', 'like', production.name)
        ], limit=1, order='id desc')
        
        # CRITICAL ASSERTIONS: Both should use fallback
        
        self.assertEqual(
            production.location_dest_id,
            fallback_location,
            "Original MO should use fallback after split"
        )
        
        self.assertEqual(
            backorder.location_dest_id,
            fallback_location,
            "Backorder should use fallback location"
        )
        
        # Verify no NULL violations
        self.assertTrue(
            production.location_src_id,
            "Original MO location_src_id should not be NULL"
        )
        
        self.assertTrue(
            backorder.location_src_id,
            "Backorder location_src_id should not be NULL"
        )
        
        self.assertTrue(
            production.location_dest_id,
            "Original MO location_dest_id should not be NULL"
        )
        
        self.assertTrue(
            backorder.location_dest_id,
            "Backorder location_dest_id should not be NULL"
        )

    def test_04_split_moves_location_synchronization(self):
        """Test that moves are synchronized when location changes (v17.0.1.3.0 fix)
        
        This test validates the critical fix implemented in v17.0.1.3.0:
        _sync_finished_moves_location() method ensures moves are synchronized
        with production.location_dest_id after split operations.
        
        Validates:
        - Moves have correct location_dest_id after split
        - Move synchronization happens automatically
        - No manual intervention required
        
        Scenario:
        1. Create MO with workcenter destination
        2. Confirm (creates moves with location A)
        3. Split MO
        4. Verify backorder moves have correct location_dest_id
        5. Verify original MO moves remain correct
        """
        # Create manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 10.0,
            'bom_id': self.bom_with_dest.id,
        })
        
        production.action_confirm()
        
        # Get original moves
        finished_moves_original = production.move_finished_ids.filtered(
            lambda m: m.product_id == production.product_id
        )
        
        # Verify moves have correct location before split
        for move in finished_moves_original:
            self.assertEqual(
                move.location_dest_id,
                self.location_workcenter_a,
                "Move should have workcenter destination before split"
            )
        
        # Execute split
        split_wizard = self.env['mrp.production.split'].create({
            'production_id': production.id,
            'production_split_multi_id': False,
            'counter': 1,
        })
        
        split_wizard.split_line_ids = [(0, 0, {
            'quantity': 6.0,
            'user_id': self.env.user.id,
        })]
        
        split_wizard.action_split()
        
        # Get backorder
        backorder = self.env['mrp.production'].search([
            ('backorder_sequence', '>', 0),
            ('origin', 'like', production.name)
        ], limit=1, order='id desc')
        
        # CRITICAL ASSERTIONS: Verify move synchronization (v17.0.1.3.0)
        
        # 1. Original MO moves should maintain correct location
        finished_moves_after = production.move_finished_ids.filtered(
            lambda m: m.product_id == production.product_id and m.state not in ('done', 'cancel')
        )
        
        for move in finished_moves_after:
            self.assertEqual(
                move.location_dest_id,
                production.location_dest_id,
                "Original MO move should be synchronized with production location_dest_id"
            )
            self.assertEqual(
                move.location_dest_id,
                self.location_workcenter_a,
                "Original MO move should have workcenter destination"
            )
        
        # 2. Backorder moves should have correct location (synchronized automatically)
        backorder_moves = backorder.move_finished_ids.filtered(
            lambda m: m.product_id == backorder.product_id and m.state not in ('done', 'cancel')
        )
        
        for move in backorder_moves:
            self.assertEqual(
                move.location_dest_id,
                backorder.location_dest_id,
                "Backorder move should be synchronized with production location_dest_id"
            )
            self.assertEqual(
                move.location_dest_id,
                self.location_workcenter_a,
                "Backorder move should have workcenter destination"
            )
        
        # 3. Verify no inconsistencies exist
        self.assertEqual(
            production.location_dest_id,
            self.location_workcenter_a,
            "Production should have workcenter destination"
        )
        
        self.assertEqual(
            backorder.location_dest_id,
            self.location_workcenter_a,
            "Backorder should have workcenter destination"
        )

    def test_05_split_with_reservations_consistency(self):
        """Test that reservations (move_lines) maintain consistency after split
        
        Validates:
        - Move_lines (stock.move.line) have correct location_dest_id
        - Reservations are synchronized along with moves
        - Both move and move_line have consistent locations
        
        Scenario:
        1. Create MO with component (to create reservations)
        2. Confirm and reserve components
        3. Split MO
        4. Verify move_lines have correct location_dest_id in both MOs
        5. Verify consistency between move and move_line locations
        """
        # Create manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 10.0,
            'bom_id': self.bom_with_dest.id,
        })
        
        production.action_confirm()
        
        # Reserve components (creates move_lines)
        production.action_assign()
        
        # Verify reservations exist
        component_moves = production.move_raw_ids
        self.assertTrue(
            component_moves,
            "Production should have component moves"
        )
        
        # Get finished moves with potential reservations
        finished_moves = production.move_finished_ids.filtered(
            lambda m: m.product_id == production.product_id
        )
        
        # Execute split
        split_wizard = self.env['mrp.production.split'].create({
            'production_id': production.id,
            'production_split_multi_id': False,
            'counter': 1,
        })
        
        split_wizard.split_line_ids = [(0, 0, {
            'quantity': 6.0,
            'user_id': self.env.user.id,
        })]
        
        split_wizard.action_split()
        
        # Get backorder
        backorder = self.env['mrp.production'].search([
            ('backorder_sequence', '>', 0),
            ('origin', 'like', production.name)
        ], limit=1, order='id desc')
        
        # CRITICAL ASSERTIONS: Verify move_lines consistency
        
        # 1. Verify finished moves and move_lines in original MO
        for move in finished_moves.filtered(lambda m: m.state not in ('done', 'cancel')):
            self.assertEqual(
                move.location_dest_id,
                production.location_dest_id,
                "Move should match production location_dest_id"
            )
            
            # Check move_lines consistency
            for move_line in move.move_line_ids.filtered(lambda ml: ml.state not in ('done', 'cancel')):
                self.assertEqual(
                    move_line.location_dest_id,
                    move.location_dest_id,
                    "Move_line should match move location_dest_id"
                )
                self.assertEqual(
                    move_line.location_dest_id,
                    production.location_dest_id,
                    "Move_line should match production location_dest_id"
                )
        
        # 2. Verify finished moves and move_lines in backorder
        backorder_moves = backorder.move_finished_ids.filtered(
            lambda m: m.product_id == backorder.product_id
        )
        
        for move in backorder_moves.filtered(lambda m: m.state not in ('done', 'cancel')):
            self.assertEqual(
                move.location_dest_id,
                backorder.location_dest_id,
                "Backorder move should match production location_dest_id"
            )
            
            # Check move_lines consistency
            for move_line in move.move_line_ids.filtered(lambda ml: ml.state not in ('done', 'cancel')):
                self.assertEqual(
                    move_line.location_dest_id,
                    move.location_dest_id,
                    "Backorder move_line should match move location_dest_id"
                )
                self.assertEqual(
                    move_line.location_dest_id,
                    backorder.location_dest_id,
                    "Backorder move_line should match production location_dest_id"
                )
        
        # 3. Verify both MOs use workcenter destination
        self.assertEqual(
            production.location_dest_id,
            self.location_workcenter_a,
            "Original MO should use workcenter destination"
        )
        
        self.assertEqual(
            backorder.location_dest_id,
            self.location_workcenter_a,
            "Backorder should use workcenter destination"
        )
        
        # 4. Verify no NULL locations exist
        self.assertTrue(
            all(move.location_dest_id for move in finished_moves),
            "All original MO moves should have location_dest_id"
        )
        
        self.assertTrue(
            all(move.location_dest_id for move in backorder_moves),
            "All backorder moves should have location_dest_id"
        )
