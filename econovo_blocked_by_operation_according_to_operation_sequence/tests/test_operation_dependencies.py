from odoo.tests.common import SavepointCase
from odoo.exceptions import UserError


class TestOperationDependencies(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create workcenter
        cls.workcenter = cls.env['mrp.workcenter'].create({
            'name': 'Test Workcenter',
            'capacity': 1,
            'time_efficiency': 100,
        })
        
        # Create operations
        cls.operation_1 = cls.env['mrp.routing.workcenter'].create({
            'name': 'Operation 1',
            'workcenter_id': cls.workcenter.id,
            'time_cycle': 60,
            'sequence': 10,
        })
        
        cls.operation_2 = cls.env['mrp.routing.workcenter'].create({
            'name': 'Operation 2',
            'workcenter_id': cls.workcenter.id,
            'time_cycle': 60,
            'sequence': 20,
        })
        
        cls.operation_3 = cls.env['mrp.routing.workcenter'].create({
            'name': 'Operation 3',
            'workcenter_id': cls.workcenter.id,
            'time_cycle': 60,
            'sequence': 30,
        })
        
        # Create product and BOM
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
        })
        
        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'product_qty': 1.0,
            'operation_ids': [(6, 0, [cls.operation_1.id, cls.operation_2.id, cls.operation_3.id])],
            'allow_operation_dependencies': True,
        })

    def test_set_operation_dependencies(self):
        """Test the action to set operation dependencies based on sequence"""
        # Execute the action
        self.bom.action_set_operation_dependencies()
        
        # Check that dependencies are set correctly
        self.assertFalse(self.operation_1.blocked_by_operation_ids, "First operation should not be blocked")
        self.assertEqual(self.operation_2.blocked_by_operation_ids, self.operation_1, "Second operation should be blocked by first")
        self.assertEqual(self.operation_3.blocked_by_operation_ids, self.operation_2, "Third operation should be blocked by second")
    
    def test_dependencies_not_allowed(self):
        """Test that an error is raised when dependencies are not allowed"""
        # Disable operation dependencies
        self.bom.allow_operation_dependencies = False
        
        # Check that an error is raised
        with self.assertRaises(UserError):
            self.bom.action_set_operation_dependencies()
