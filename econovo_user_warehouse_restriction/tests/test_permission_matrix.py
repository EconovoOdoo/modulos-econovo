# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install')
class TestWarehousePermissionMatrix(TransactionCase):
    """Test permission matrix access control and assignment"""

    def setUp(self):
        super(TestWarehousePermissionMatrix, self).setUp()
        
        # Get groups
        self.group_system = self.env.ref('base.group_system')
        self.group_stock_user = self.env.ref('stock.group_stock_user')
        self.group_stock_manager = self.env.ref('stock.group_stock_manager')
        
        # Create admin user with Settings and Inventory/Administrator access
        self.admin_user = self.env['res.users'].create({
            'name': 'Test Admin Matrix',
            'login': 'test_admin_matrix',
            'email': 'test_admin_matrix@test.com',
            'groups_id': [(6, 0, [self.group_system.id, self.group_stock_manager.id])],
        })
        
        # Create regular user WITHOUT Settings access
        self.regular_user = self.env['res.users'].create({
            'name': 'Test Regular User',
            'login': 'test_regular_matrix',
            'email': 'test_regular_matrix@test.com',
            'groups_id': [(6, 0, [self.group_stock_user.id])],
        })
        
        # Get or create test warehouses (use sudo for system operations)
        self.warehouse_1 = self.env['stock.warehouse'].search([('code', '=', 'WH')], limit=1)
        if not self.warehouse_1:
            self.warehouse_1 = self.env['stock.warehouse'].sudo().create({
                'name': 'Main Warehouse',
                'code': 'WH',
            })
        
        self.warehouse_2 = self.env['stock.warehouse'].search([('code', '=', 'WH2')], limit=1)
        if not self.warehouse_2:
            self.warehouse_2 = self.env['stock.warehouse'].sudo().create({
                'name': 'Secondary Warehouse',
                'code': 'WH2',
            })

    def test_admin_sees_all_permission_records(self):
        """
        Test that admin users can see ALL permission records regardless of assignment.
        
        CASO 1.3: Verifies admin has unrestricted access to permission matrix
        """
        # Create permission for regular user on warehouse_1
        permission = self.env['warehouse.user.permission'].create({
            'warehouse_id': self.warehouse_1.id,
            'user_id': self.regular_user.id,
            'full_control': True,
        })
        
        # Admin should see this permission even though it's not assigned to admin
        permissions_as_admin = self.env['warehouse.user.permission'].with_user(self.admin_user).search([
            ('id', '=', permission.id),
        ])
        
        self.assertTrue(
            permissions_as_admin,
            "Admin user should see permission records for other users"
        )
        
        # Admin should be able to read all fields
        self.assertEqual(
            permissions_as_admin.user_id.id,
            self.regular_user.id,
            "Admin should see correct user assignment"
        )

    def test_user_sees_only_own_permission_records(self):
        """
        Test that regular users can only see their OWN permission records.
        
        CASO 2.1: Verifies permission matrix access restriction for non-admin users
        """
        # Create permission for regular user on warehouse_1
        permission_own = self.env['warehouse.user.permission'].create({
            'warehouse_id': self.warehouse_1.id,
            'user_id': self.regular_user.id,
            'full_control': True,
        })
        
        # Get existing permission for admin user on warehouse_2 (auto-created by hook)
        permission_other = self.env['warehouse.user.permission'].search([
            ('warehouse_id', '=', self.warehouse_2.id),
            ('user_id', '=', self.admin_user.id),
        ], limit=1)
        
        # If not exists (shouldn't happen), create it
        if not permission_other:
            permission_other = self.env['warehouse.user.permission'].create({
                'warehouse_id': self.warehouse_2.id,
                'user_id': self.admin_user.id,
                'full_control': True,
            })
        
        # Regular user searches for all permissions
        permissions_as_regular = self.env['warehouse.user.permission'].with_user(self.regular_user).search([])
        
        # Should only see own permission
        self.assertEqual(
            len(permissions_as_regular),
            1,
            "Regular user should only see 1 permission record (their own)"
        )
        
        self.assertEqual(
            permissions_as_regular[0].id,
            permission_own.id,
            "Regular user should only see their own permission"
        )
        
        # Should NOT see admin's permission
        self.assertNotIn(
            permission_other.id,
            permissions_as_regular.ids,
            "Regular user should NOT see other users' permissions"
        )

    def test_regular_user_cannot_assign_permissions(self):
        """
        Test that regular users (without Settings access) CANNOT create or modify
        permission records.
        
        CASO 1.5 restriction: Only admins can assign permissions
        """
        # Attempt to create permission as regular user should fail
        with self.assertRaises(AccessError, msg="Regular user should NOT be able to create permissions"):
            self.env['warehouse.user.permission'].with_user(self.regular_user).create({
                'warehouse_id': self.warehouse_1.id,
                'user_id': self.regular_user.id,
                'full_control': True,
            })
        
        # Create permission as admin
        permission = self.env['warehouse.user.permission'].create({
            'warehouse_id': self.warehouse_1.id,
            'user_id': self.regular_user.id,
            'view_only': True,
        })
        
        # Attempt to modify as regular user should fail
        with self.assertRaises(AccessError, msg="Regular user should NOT be able to modify permissions"):
            permission.with_user(self.regular_user).write({
                'full_control': True,
                'view_only': False,
            })
