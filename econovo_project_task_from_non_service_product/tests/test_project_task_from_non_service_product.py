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

    def test_qty_delivered_method_manual_for_tracked_non_service_product(self):
        """A tracked non-service line is kept on 'manual' delivered-qty
        tracking, not forced to 'stock_move' by sale_stock just because the
        product is consu/storable. That extra, unneeded dependency on stock
        moves is what let qty_to_invoice/invoice_status intermittently
        freeze at 0 on already-confirmed orders in production."""
        order, line = self._create_order(self.product_task_in_project)
        order.action_confirm()
        self.assertEqual(line.qty_delivered_method, 'manual')
        self.assertEqual(line.invoice_status, 'to invoice')
        self.assertEqual(line.qty_to_invoice, 2)

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


@tagged('post_install', '-at_install')
class TestFsmWarrantyInvoicing(TransactionCase):
    """Zero-priced warranty labour must still be invoiceable.

    industry_fsm_sale zeroes qty_to_invoice on every zero-priced line linked to a
    Field Service task, to keep free materials off the invoice. Lines generated by
    this module from a Sales Order are a different concept and must stay
    invoiceable at 0, without weakening that guard for real FSM material lines.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'FSM Customer'})
        cls.fsm_project = cls.env['project.project'].create({
            'name': 'Field Service Project',
            'is_fsm': True,
            'allow_billable': True,
            # project_project_company_id_required_for_fsm_project
            'company_id': cls.env.company.id,
        })
        cls.regular_project = cls.env['project.project'].create({
            'name': 'Regular Tracking Project',
            'allow_billable': True,
        })
        cls.warranty_product = cls.env['product.product'].create({
            'name': 'Warranty Labour',
            'type': 'consu',
            'invoice_policy': 'order',
            'service_tracking': 'task_global_project',
            'project_id': cls.fsm_project.id,
            'list_price': 0.0,
        })
        cls.material_product = cls.env['product.product'].create({
            'name': 'Spare Part',
            'type': 'consu',
            'invoice_policy': 'order',
            'list_price': 0.0,
        })

    def _confirm_order(self, product, price_unit, project=None):
        if project is not None:
            product.project_id = project
        order = self.env['sale.order'].with_context(tracking_disable=True).create({
            'partner_id': self.partner.id,
        })
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': price_unit,
        })
        order.action_confirm()
        return order, line

    def test_zero_priced_warranty_line_is_invoiceable(self):
        """The core scenario: labour billed at 0 in warranty still has to be
        invoiceable, even though its task lives in a Field Service project."""
        _order, line = self._confirm_order(self.warranty_product, 0.0)
        self.assertTrue(line.task_id.is_fsm)
        self.assertEqual(line.task_id.sale_line_id, line)
        self.assertEqual(line.qty_to_invoice, 1)
        self.assertEqual(line.invoice_status, 'to invoice')

    def test_zero_priced_warranty_line_reaches_the_invoice(self):
        """End to end: the zero-priced line must actually appear on the invoice,
        since _get_invoiceable_lines() drops anything with qty_to_invoice = 0."""
        order, line = self._confirm_order(self.warranty_product, 0.0)
        invoice = order._create_invoices()
        self.assertIn(line, invoice.invoice_line_ids.sale_line_ids)

    def test_fsm_material_line_is_still_excluded(self):
        """Regression guard: free materials added from inside a Field Service
        task must keep industry_fsm_sale's native behaviour."""
        order, line = self._confirm_order(self.material_product, 0.0)
        fsm_task = self.env['project.task'].create({
            'name': 'Manual FSM Intervention',
            'project_id': self.fsm_project.id,
        })
        # A material line points at the task without having generated it.
        line.task_id = fsm_task
        self.assertTrue(line.task_id.is_fsm)
        self.assertFalse(line.task_id.sale_line_id)
        line.invalidate_recordset(['qty_to_invoice', 'invoice_status'])
        self.assertEqual(line.qty_to_invoice, 0)
        self.assertNotIn(line, order._get_invoiceable_lines())

    def test_priced_warranty_line_is_unaffected(self):
        """A non-zero price never triggered the FSM guard; behaviour must not
        change for those lines."""
        _order, line = self._confirm_order(self.warranty_product, 150.0)
        self.assertEqual(line.qty_to_invoice, 1)
        self.assertEqual(line.invoice_status, 'to invoice')

    def test_zero_priced_line_outside_fsm_is_unaffected(self):
        """Same product tracked into a non-FSM project: the guard never applied
        there, and the override must not change that either."""
        _order, line = self._confirm_order(
            self.warranty_product, 0.0, project=self.regular_project)
        self.assertFalse(line.task_id.is_fsm)
        self.assertEqual(line.qty_to_invoice, 1)
        self.assertEqual(line.invoice_status, 'to invoice')
