# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWarehousePermissionHooks(TransactionCase):
    """Test module hooks and automatic permission assignment"""

    def setUp(self):
        super(TestWarehousePermissionHooks, self).setUp()
        
        # Get base.group_system and stock.group_stock_manager groups
        self.group_system = self.env.ref('base.group_system')
        self.group_stock_manager = self.env.ref('stock.group_stock_manager')
        
        # Create test admin user with Settings and Inventory/Administrator access
        self.admin_user = self.env['res.users'].create({
            'name': 'Test Admin User',
            'login': 'test_admin_hooks',
            'email': 'test_admin_hooks@test.com',
            'groups_id': [(6, 0, [self.group_system.id, self.group_stock_manager.id])],
        })
        
        # Get existing warehouses
        self.warehouses = self.env['stock.warehouse'].search([])

    def test_post_init_hook_creates_admin_permissions(self):
        """
        Test that post_init_hook creates Full Control permissions for all admin users
        on all existing warehouses.
        
        CASO 1.2: Verifies post_init_hook execution
        """
        # Simulate post_init_hook behavior: call the hook function directly
        from odoo.addons.econovo_user_warehouse_restriction.hooks import post_init_hook
        post_init_hook(self.env)
        
        # Verify that admin user has permissions on all warehouses
        for warehouse in self.warehouses:
            permission = self.env['warehouse.user.permission'].search([
                ('warehouse_id', '=', warehouse.id),
                ('user_id', '=', self.admin_user.id),
            ])
            
            # Assert permission exists
            self.assertEqual(
                len(permission), 1,
                f"Admin user should have exactly one permission on warehouse {warehouse.name}"
            )
            
            # Assert Full Control is enabled
            self.assertTrue(
                permission[0].full_control,
                f"Admin user should have Full Control on warehouse {warehouse.name}"
            )

    def test_warehouse_create_auto_assigns_admin(self):
        """
        Test that creating a new warehouse automatically assigns Full Control
        to all admin users.
        
        CASO 1.4: Verifies auto-assignment on warehouse creation
        """
        # Create new warehouse using sudo() for system operation
        # (warehouse creation involves complex FK operations with picking_types)
        new_warehouse = self.env['stock.warehouse'].sudo().create({
            'name': 'Test Warehouse Auto Assign',
            'code': 'TWAA',
        })
        
        # Verify admin user has automatic permission
        permission = self.env['warehouse.user.permission'].search([
            ('warehouse_id', '=', new_warehouse.id),
            ('user_id', '=', self.admin_user.id),
        ])
        
        # Assert permission was created automatically
        self.assertEqual(
            len(permission), 1,
            f"Admin user should be auto-assigned exactly once to new warehouse {new_warehouse.name}"
        )
        
        # Assert Full Control is enabled
        self.assertTrue(
            permission[0].full_control,
            f"Admin user should have Full Control on new warehouse {new_warehouse.name}"
        )
        
        # Note: No cleanup needed - test transaction will rollback automatically
