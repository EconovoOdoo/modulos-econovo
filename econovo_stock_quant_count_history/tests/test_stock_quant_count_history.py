# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockQuantCountHistory(TransactionCase):
    """Test cases for Stock Quant Count History module."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test company
        cls.company = cls.env['res.company'].create({
            'name': 'Test Company',
        })
        
        # Create test user with inventory manager rights
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Test Manager',
            'login': 'test_manager',
            'email': 'test_manager@test.com',
            'company_id': cls.company.id,
            'company_ids': [(4, cls.company.id)],
            'groups_id': [(4, cls.env.ref('stock.group_stock_manager').id)],
        })
        
        # Create test user with inventory user rights (read-only)
        cls.user_basic = cls.env['res.users'].create({
            'name': 'Test User',
            'login': 'test_user',
            'email': 'test_user@test.com',
            'company_id': cls.company.id,
            'company_ids': [(4, cls.company.id)],
            'groups_id': [(4, cls.env.ref('stock.group_stock_user').id)],
        })
        
        # Create warehouse
        cls.warehouse = cls.env['stock.warehouse'].create({
            'name': 'Test Warehouse',
            'code': 'TWH',
            'company_id': cls.company.id,
        })
        
        # Get stock location from warehouse
        cls.location = cls.warehouse.lot_stock_id
        
        # Create test product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
            'tracking': 'none',
        })
        
        # Create serial-tracked product
        cls.product_serial = cls.env['product.product'].create({
            'name': 'Test Product Serial',
            'type': 'product',
            'tracking': 'serial',
        })
        
        # Create quant
        cls.quant = cls.env['stock.quant'].create({
            'product_id': cls.product.id,
            'location_id': cls.location.id,
            'quantity': 100.0,
            'company_id': cls.company.id,
        })

    def test_01_create_history_on_apply(self):
        """Test that applying inventory creates history record with state='applied'."""
        # Set inventory quantity
        self.quant.inventory_quantity = 90.0
        
        # Apply inventory
        self.quant.action_apply_inventory()
        
        # Check history record was created
        history = self.env['stock.quant.count.history'].search([
            ('quant_id', '=', self.quant.id),
        ], limit=1, order='id desc')
        
        self.assertTrue(history, "History record should be created on apply")
        self.assertEqual(history.state, 'applied', "State should be 'applied'")
        self.assertEqual(history.quantity_on_hand, 100.0, "On hand should be original quantity")
        self.assertEqual(history.quantity_counted, 90.0, "Counted should be new quantity")
        self.assertEqual(history.difference, -10.0, "Difference should be -10")
        self.assertTrue(history.was_applied, "was_applied should be True when difference exists")

    def test_02_manual_save_to_history(self):
        """Test that manual save creates history record with state='saved'."""
        # Create a new quant for this test
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location.id,
            'quantity': 50.0,
            'company_id': self.company.id,
        })
        
        # Set inventory quantity (same as on hand - no difference)
        quant.inventory_quantity = 50.0
        
        # Manual save to history
        quant.action_save_count_to_history()
        
        # Check history record was created
        history = self.env['stock.quant.count.history'].search([
            ('quant_id', '=', quant.id),
        ], limit=1, order='id desc')
        
        self.assertTrue(history, "History record should be created on manual save")
        self.assertEqual(history.state, 'saved', "State should be 'saved'")
        self.assertEqual(history.difference, 0.0, "Difference should be 0")
        self.assertFalse(history.was_applied, "was_applied should be False when saved manually")

    def test_03_no_duplicate_on_same_count(self):
        """Test that different operations create separate records (no duplicates issue)."""
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location.id,
            'quantity': 30.0,
            'company_id': self.company.id,
        })
        
        # Set and save manually
        quant.inventory_quantity = 35.0
        quant.action_save_count_to_history()
        
        # Count records
        count_before = self.env['stock.quant.count.history'].search_count([
            ('quant_id', '=', quant.id),
        ])
        
        # Save again (should create new record with different timestamp)
        quant.action_save_count_to_history()
        
        count_after = self.env['stock.quant.count.history'].search_count([
            ('quant_id', '=', quant.id),
        ])
        
        self.assertEqual(count_after, count_before + 1, "Each save should create a new record")

    def test_04_quant_deletion_preserves_history(self):
        """Test that deleting quant preserves history (quant_id becomes null)."""
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location.id,
            'quantity': 20.0,
            'company_id': self.company.id,
        })
        
        # Set and save
        quant.inventory_quantity = 25.0
        quant.action_save_count_to_history()
        
        # Get history record
        history = self.env['stock.quant.count.history'].search([
            ('quant_id', '=', quant.id),
        ], limit=1)
        history_id = history.id
        
        # Delete quant
        quant.unlink()
        
        # Check history still exists but quant_id is null
        history = self.env['stock.quant.count.history'].browse(history_id)
        self.assertTrue(history.exists(), "History should still exist after quant deletion")
        self.assertFalse(history.quant_id, "quant_id should be null after quant deletion")
        self.assertTrue(history.product_id, "product_id should still be set")

    def test_05_serial_number_constraint(self):
        """Test that serial products cannot have qty > 1."""
        # Create lot for serial product
        lot = self.env['stock.lot'].create({
            'name': 'SERIAL001',
            'product_id': self.product_serial.id,
            'company_id': self.company.id,
        })
        
        # Try to create history with qty > 1 for serial product
        with self.assertRaises(ValidationError):
            self.env['stock.quant.count.history'].create({
                'product_id': self.product_serial.id,
                'location_id': self.location.id,
                'lot_id': lot.id,
                'quantity_on_hand': 1.0,
                'quantity_counted': 2.0,  # Invalid for serial tracking
                'company_id': self.company.id,
                'state': 'saved',
            })

    def test_06_warehouse_computation(self):
        """Test that warehouse is correctly computed from location."""
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location.id,
            'quantity': 10.0,
            'company_id': self.company.id,
        })
        
        quant.inventory_quantity = 15.0
        quant.action_save_count_to_history()
        
        history = self.env['stock.quant.count.history'].search([
            ('quant_id', '=', quant.id),
        ], limit=1)
        
        self.assertEqual(history.warehouse_id, self.warehouse, "Warehouse should be computed from location")

    def test_07_sequence_generation(self):
        """Test that sequence is correctly generated."""
        history = self.env['stock.quant.count.history'].create({
            'product_id': self.product.id,
            'location_id': self.location.id,
            'quantity_on_hand': 10.0,
            'quantity_counted': 10.0,
            'company_id': self.company.id,
            'state': 'saved',
        })
        
        self.assertTrue(history.name, "Name should be generated")
        self.assertTrue(history.name.startswith('COUNT/'), "Name should start with COUNT/")

    def test_08_difference_computation(self):
        """Test that difference is correctly computed."""
        history = self.env['stock.quant.count.history'].create({
            'product_id': self.product.id,
            'location_id': self.location.id,
            'quantity_on_hand': 100.0,
            'quantity_counted': 85.0,
            'company_id': self.company.id,
            'state': 'saved',
        })
        
        self.assertEqual(history.difference, -15.0, "Difference should be counted - on_hand")

    def test_09_count_history_count(self):
        """Test that count_history_count is computed correctly."""
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location.id,
            'quantity': 40.0,
            'company_id': self.company.id,
        })
        
        self.assertEqual(quant.count_history_count, 0, "Initial count should be 0")
        
        # Create history records
        quant.inventory_quantity = 45.0
        quant.action_save_count_to_history()
        quant.action_save_count_to_history()
        
        self.assertEqual(quant.count_history_count, 2, "Count should be 2 after two saves")

    def test_10_apply_with_no_difference(self):
        """Test apply when counted equals on hand (no actual adjustment)."""
        quant = self.env['stock.quant'].create({
            'product_id': self.product.id,
            'location_id': self.location.id,
            'quantity': 60.0,
            'company_id': self.company.id,
        })
        
        # Set same quantity
        quant.inventory_quantity = 60.0
        quant.action_apply_inventory()
        
        history = self.env['stock.quant.count.history'].search([
            ('quant_id', '=', quant.id),
        ], limit=1, order='id desc')
        
        self.assertEqual(history.state, 'applied', "State should be 'applied'")
        self.assertEqual(history.difference, 0.0, "Difference should be 0")
        self.assertFalse(history.was_applied, "was_applied should be False when no difference")
