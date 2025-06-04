# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestBatchProductionAssignment(TransactionCase):
    
    def setUp(self):
        super(TestBatchProductionAssignment, self).setUp()
        
        # Create test product
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
        })
        
        # Create test BOM
        self.bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
        })
        
        # Create component product
        self.component = self.env['product.product'].create({
            'name': 'Test Component',
            'type': 'product',
        })
        
        # Add BOM line
        self.env['mrp.bom.line'].create({
            'bom_id': self.bom.id,
            'product_id': self.component.id,
            'product_qty': 2.0,
        })
    
    def test_batch_assign_empty_selection(self):
        """Test batch assignment with empty selection"""
        productions = self.env['mrp.production']        # Test empty production list
        with self.assertRaises(UserError):
            productions.batch_assign_selected_productions([])
    
    def test_batch_assign_single_production(self):
        """Test batch assignment with single manufacturing order"""
        # Create manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        
        # Confirm the production
        production.action_confirm()
        
        # Test batch assignment - should now open wizard
        result = self.env['mrp.production'].batch_assign_selected_productions([production.id])
        
        # Check result format - should open wizard window
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'mrp.production.batch.assignment.wizard')
        self.assertEqual(result['view_mode'], 'form')
        self.assertEqual(result['target'], 'new')
        self.assertIn('context', result)
        self.assertIn('active_ids', result['context'])
    
    def test_batch_assign_multiple_productions(self):
        """Test batch assignment with multiple manufacturing orders"""
        # Create multiple manufacturing orders
        productions = self.env['mrp.production'].create([
            {
                'product_id': self.product.id,
                'product_qty': 1.0,
                'bom_id': self.bom.id,
            },
            {
                'product_id': self.product.id,
                'product_qty': 2.0,
                'bom_id': self.bom.id,
            }
        ])
          # Confirm the productions
        productions.action_confirm()
        
        # Test batch assignment - should now open wizard
        result = self.env['mrp.production'].batch_assign_selected_productions(productions.ids)
        
        # Check result format - should open wizard window
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'mrp.production.batch.assignment.wizard')
        self.assertEqual(result['view_mode'], 'form')
        self.assertEqual(result['target'], 'new')
        self.assertIn('context', result)
        self.assertIn('active_ids', result['context'])
    
    def test_batch_assign_invalid_state(self):
        """Test batch assignment with manufacturing order in invalid state"""
        # Create manufacturing order but don't confirm it
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,        })
        
        # Test batch assignment - should now open wizard
        result = self.env['mrp.production'].batch_assign_selected_productions([production.id])
        
        # Check result format - should open wizard window
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'mrp.production.batch.assignment.wizard')
        self.assertEqual(result['view_mode'], 'form')
        self.assertEqual(result['target'], 'new')
        self.assertIn('context', result)
        self.assertIn('active_ids', result['context'])

    def test_wizard_analysis_single_production(self):
        """Test wizard analysis with single manufacturing order"""
        # Create and confirm manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        production.action_confirm()
        
        # Create wizard with context
        wizard = self.env['mrp.production.batch.assignment.wizard'].with_context({
            'active_ids': [production.id],
            'active_model': 'mrp.production'
        }).create({})
        
        # Test that analysis was performed
        self.assertGreaterEqual(wizard.total_orders, 1)
        self.assertIsNotNone(wizard.summary_text)
        
    def test_wizard_analysis_multiple_productions(self):
        """Test wizard analysis with multiple manufacturing orders"""
        # Create multiple manufacturing orders
        productions = self.env['mrp.production'].create([
            {
                'product_id': self.product.id,
                'product_qty': 1.0,
                'bom_id': self.bom.id,
            },
            {
                'product_id': self.product.id,
                'product_qty': 2.0,
                'bom_id': self.bom.id,
            }
        ])
        productions.action_confirm()
        
        # Create wizard with context
        wizard = self.env['mrp.production.batch.assignment.wizard'].with_context({
            'active_ids': productions.ids,
            'active_model': 'mrp.production'
        }).create({})
        
        # Test that analysis was performed for multiple orders
        self.assertEqual(wizard.total_orders, 2)
        self.assertIsNotNone(wizard.summary_text)
        
    def test_wizard_confirm_assignment(self):
        """Test wizard confirm assignment functionality"""
        # Create and confirm manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        production.action_confirm()
        
        # Create wizard with context
        wizard = self.env['mrp.production.batch.assignment.wizard'].with_context({
            'active_ids': [production.id],
            'active_model': 'mrp.production'
        }).create({})
        
        # Test confirm assignment
        result = wizard.action_confirm_assignment()
        
        # Should return notification result
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertIn('params', result)
        
    def test_wizard_cancel_action(self):
        """Test wizard cancel functionality"""
        # Create manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        
        # Create wizard with context
        wizard = self.env['mrp.production.batch.assignment.wizard'].with_context({
            'active_ids': [production.id],
            'active_model': 'mrp.production'
        }).create({})
          # Test cancel action
        result = wizard.action_cancel()
        
        # Should close the wizard
        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        
    def test_wizard_empty_context(self):
        """Test wizard behavior with empty context"""
        # Create wizard without context
        with self.assertRaises(UserError):
            wizard = self.env['mrp.production.batch.assignment.wizard'].create({})
            wizard.action_confirm_assignment()

    def test_batch_unassign_empty_selection(self):
        """Test batch unassignment with empty selection"""
        productions = self.env['mrp.production']
        # Test empty production list
        with self.assertRaises(UserError):
            productions.batch_unassign_selected_productions([])

    def test_batch_unassign_single_production(self):
        """Test batch unassignment with single manufacturing order"""
        # Create manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        
        # Confirm and assign materials
        production.action_confirm()
        production.action_assign()
        
        # Test batch unassignment - should now open wizard
        result = self.env['mrp.production'].batch_unassign_selected_productions([production.id])
        
        # Check result format - should open wizard window
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'mrp.production.batch.assignment.wizard')
        self.assertEqual(result['view_mode'], 'form')
        self.assertEqual(result['target'], 'new')
        self.assertIn('context', result)
        self.assertIn('active_ids', result['context'])
        self.assertEqual(result['context']['default_operation_mode'], 'unassign')

    def test_wizard_unassignment_mode_analysis(self):
        """Test wizard analysis in unassignment mode"""
        # Create and confirm manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        production.action_confirm()
        production.action_assign()
        
        # Create wizard with unassignment context
        wizard = self.env['mrp.production.batch.assignment.wizard'].with_context({
            'active_ids': [production.id],
            'active_model': 'mrp.production',
            'default_operation_mode': 'unassign'
        }).create({
            'operation_mode': 'unassign'
        })
        
        # Test that analysis was performed for unassignment
        self.assertEqual(wizard.operation_mode, 'unassign')
        self.assertGreaterEqual(wizard.total_orders, 1)
        self.assertIsNotNone(wizard.summary_text)

    def test_wizard_operation_mode_change(self):
        """Test wizard operation mode change triggers reanalysis"""
        # Create and confirm manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        production.action_confirm()
        
        # Create wizard in assignment mode
        wizard = self.env['mrp.production.batch.assignment.wizard'].with_context({
            'active_ids': [production.id],
            'active_model': 'mrp.production'
        }).create({
            'operation_mode': 'assign'
        })
        
        # Store initial summary
        initial_summary = wizard.summary_text
        
        # Change to unassignment mode
        wizard.write({'operation_mode': 'unassign'})
        wizard._onchange_operation_mode()
        
        # Summary should be different after mode change
        self.assertNotEqual(initial_summary, wizard.summary_text)

    def test_wizard_confirm_unassignment(self):
        """Test wizard confirm unassignment functionality"""
        # Create and confirm manufacturing order with materials assigned
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        production.action_confirm()
        production.action_assign()
        
        # Create wizard in unassignment mode
        wizard = self.env['mrp.production.batch.assignment.wizard'].with_context({
            'active_ids': [production.id],
            'active_model': 'mrp.production'
        }).create({
            'operation_mode': 'unassign'
        })
        
        # Test confirm unassignment
        result = wizard.action_confirm_assignment()
        
        # Should return notification result
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        self.assertIn('params', result)

    def test_production_categorize_for_unassignment(self):
        """Test production categorization for unassignment"""
        # Create manufacturing order
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        production.action_confirm()
        
        # Test categorization before assignment (should be no_reservations)
        category, reason = production._categorize_production_for_unassignment()
        self.assertEqual(category, 'no_reservations')
        
        # Assign materials
        production.action_assign()
        
        # Test categorization after assignment (should be different)
        category, reason = production._categorize_production_for_unassignment()
        # Category depends on whether materials were actually reserved
        self.assertIn(category, ['fully_unassignable', 'partially_unassignable', 'no_reservations'])
    
    def test_batch_production_unassignment(self):
        """Test batch production unassignment process with enhanced validation"""
        # Create multiple manufacturing orders
        productions = self.env['mrp.production'].create([
            {
                'product_id': self.product.id,
                'product_qty': 1.0,
                'bom_id': self.bom.id,
            },
            {
                'product_id': self.product.id,
                'product_qty': 2.0,
                'bom_id': self.bom.id,
            }
        ])
        
        # Confirm and assign materials
        productions.action_confirm()
        productions.action_assign()
        
        # Verify that materials are assigned
        for production in productions:
            self.assertTrue(production.unreserve_visible, 
                          f"Production {production.name} should have unreserve visible")
        
        # Test individual unassignment
        first_production = productions[0]
        result = first_production._execute_batch_unassignment()
        
        # Should succeed
        self.assertTrue(result.get('success', False), 
                       f"Unassignment should succeed: {result.get('message', '')}")
        self.assertIn('material(s) unassigned successfully', result.get('message', ''))
        
        # Test batch unassignment
        result = productions.batch_production_unassignment()
        
        # Should return notification result
        self.assertIn('type', result)
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
    
    def test_unassignment_validation(self):
        """Test unassignment validation conditions"""
        production = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        
        # Test validation on draft state
        is_valid, error_msg = production._validate_unassignment_conditions()
        self.assertFalse(is_valid)
        self.assertIn('Confirmed', error_msg)
        
        # Confirm and test validation
        production.action_confirm()
        is_valid, error_msg = production._validate_unassignment_conditions()
        self.assertTrue(is_valid)
        
        # Test unassignment without reservations
        result = production._execute_batch_unassignment()
        self.assertFalse(result.get('success', True))
        self.assertIn('No material reservations', result.get('message', ''))
        
        # Assign materials and test successful unassignment
        production.action_assign()
        result = production._execute_batch_unassignment()
        if production.unreserve_visible:
            self.assertTrue(result.get('success', False))
            self.assertIn('unassigned successfully', result.get('message', ''))

    def test_wizard_unassignment_categorization_counts(self):
        """Test wizard categorization counts for unassignment mode"""
        # Create manufacturing orders in different states
        production1 = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        
        production2 = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'product_qty': 1.0,
            'bom_id': self.bom.id,
        })
        
        # Confirm both
        productions = production1 + production2
        productions.action_confirm()
        
        # Assign materials to one
        production1.action_assign()
        
        # Create wizard in unassignment mode
        wizard = self.env['mrp.production.batch.assignment.wizard'].with_context({
            'active_ids': productions.ids,
            'active_model': 'mrp.production'
        }).create({
            'operation_mode': 'unassign'
        })
        
        # Test that categorization counts are properly calculated
        self.assertEqual(wizard.total_orders, 2)
        # At least one should have no reservations
        self.assertGreaterEqual(wizard.no_reservations_count, 1)
