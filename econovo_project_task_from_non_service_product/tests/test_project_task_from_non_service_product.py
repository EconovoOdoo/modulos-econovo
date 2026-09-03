# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProjectTaskFromNonServiceProduct(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Customer'})
        cls.existing_project = cls.env['project.project'].create({
            'name': 'Existing Project For Global Tasks',
            'allow_billable': True,
        })
        cls.product_task_global_project = cls.env['product.product'].create({
            'name': 'Storable - Task In Existing Project',
            'type': 'consu',
            'service_tracking': 'task_global_project',
            'project_id': cls.existing_project.id,
        })
        cls.product_task_in_project = cls.env['product.product'].create({
            'name': 'Consumable - Project & Task',
            'type': 'consu',
            'service_tracking': 'task_in_project',
        })
        cls.product_no_tracking = cls.env['product.product'].create({
            'name': 'Consumable - No Tracking',
            'type': 'consu',
            'service_tracking': 'no',
        })

    def _create_order(self, product):
        order = self.env['sale.order'].with_context(tracking_disable=True).create({
            'partner_id': self.partner.id,
            'partner_invoice_id': self.partner.id,
            'partner_shipping_id': self.partner.id,
        })
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': 2,
        })
        return order, line

    def test_is_service_extended_for_tracked_non_service_product(self):
        """A tracked non-service product's SOL is flagged as is_service, a
        plain (service_tracking='no') one is not."""
        _order, tracked_line = self._create_order(self.product_task_in_project)
        _order2, untracked_line = self._create_order(self.product_no_tracking)
        self.assertTrue(tracked_line.is_service)
        self.assertFalse(untracked_line.is_service)

    def test_task_generated_in_existing_project(self):
        """Confirming the order creates a task in the product's configured
        project (task_global_project), like it does for real services."""
        order, line = self._create_order(self.product_task_global_project)
        order.action_confirm()
        self.assertTrue(line.task_id)
        self.assertEqual(line.task_id.project_id, self.existing_project)

    def test_project_and_task_generated_in_new_project(self):
        """Confirming the order creates a brand new project and a task in it
        (task_in_project), like it does for real services."""
        order, line = self._create_order(self.product_task_in_project)
        order.action_confirm()
        self.assertTrue(line.project_id)
        self.assertTrue(line.task_id)
        self.assertEqual(line.task_id.project_id, line.project_id)

    def test_no_project_or_task_when_tracking_disabled(self):
        """service_tracking='no' keeps the native no-op behavior."""
        order, line = self._create_order(self.product_no_tracking)
        order.action_confirm()
        self.assertFalse(line.project_id)
        self.assertFalse(line.task_id)

    def test_show_project_and_task_buttons(self):
        """The Sale Order Projects/Tasks smart buttons show up once a
        non-service tracked line generated a project/task."""
        order, _line = self._create_order(self.product_task_in_project)
        order.action_confirm()
        # show_project_button/show_task_button have no @api.depends (same as
        # core): force a recompute instead of reading a pre-confirm cached value.
        order.invalidate_recordset(['show_project_button', 'show_task_button'])
        self.assertTrue(order.show_project_button)
        self.assertTrue(order.show_task_button)

    def test_product_locked_after_confirm(self):
        """Once the project/task has been generated, the product can no
        longer be swapped on the confirmed line."""
        order, line = self._create_order(self.product_task_in_project)
        self.assertTrue(line.product_updatable)
        order.action_confirm()
        self.assertFalse(line.product_updatable)

    def test_onchange_type_keeps_service_tracking(self):
        """Switching the Product Type in the form view must not silently
        reset the configured Service Tracking option."""
        with Form(self.product_task_in_project.product_tmpl_id) as product_form:
            product_form.detailed_type = 'service'
            product_form.detailed_type = 'consu'
            self.assertEqual(product_form.service_tracking, 'task_in_project')

    def test_write_type_keeps_service_tracking(self):
        """A plain write() on 'type' (e.g. from code/RPC, bypassing the form's
        onchange) must not silently reset the configured Service Tracking
        option either, mirroring sale_project's own
        test_sol_product_type_update but with the opposite expectation."""
        product = self.env['product.product'].create({
            'name': 'Service - Project & Task',
            'type': 'service',
            'service_tracking': 'task_in_project',
        })
        product.write({'type': 'consu'})
        self.assertEqual(product.service_tracking, 'task_in_project')
