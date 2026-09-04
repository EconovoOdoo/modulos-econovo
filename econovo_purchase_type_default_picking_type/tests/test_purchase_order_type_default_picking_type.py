# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPurchaseOrderTypeDefaultPickingType(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env['res.company'].create({'name': 'Test Other Company'})

        cls.receipt_type = cls.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        cls.other_receipt_type = cls.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('company_id', '=', cls.other_company.id),
        ], limit=1)

        cls.partner = cls.env['res.partner'].create({'name': 'Test Preset Vendor'})

        cls.order_type = cls.env['purchase.order.type'].create({
            'name': 'Test Type With Preset',
            'company_id': cls.company.id,
            'picking_type_id': cls.receipt_type.id,
        })

    def test_onchange_order_type_applies_preset_picking_type(self):
        with Form(self.env['purchase.order']) as order_form:
            order_form.partner_id = self.partner
            order_form.order_type = self.order_type
        order = order_form.save()
        self.assertEqual(order.picking_type_id, self.receipt_type)

    def test_onchange_order_type_skips_preset_on_company_mismatch(self):
        """A type from another company must not leak its preset onto this order.

        `purchase_order_type`'s own `_check_po_type_company` constraint would
        reject saving this combination anyway, so this only asserts the transient
        `Form` state right after the onchange fires - deliberately never calling
        `save()` (which `with Form(...) as ...:` would trigger on exit).
        """
        mismatched_type = self.env['purchase.order.type'].create({
            'name': 'Test Type Other Company',
            'company_id': self.other_company.id,
            'picking_type_id': self.other_receipt_type.id,
        })
        order_form = Form(self.env['purchase.order'])
        order_form.partner_id = self.partner
        default_picking_type_id = order_form.picking_type_id.id
        order_form.order_type = mismatched_type
        self.assertEqual(order_form.picking_type_id.id, default_picking_type_id)

    def test_picking_type_requires_single_company_type(self):
        with self.assertRaises(ValidationError):
            self.env['purchase.order.type'].create({
                'name': 'Test Shared Type',
                'company_id': False,
                'picking_type_id': self.receipt_type.id,
            })

    def test_picking_type_must_match_type_company(self):
        with self.assertRaises(ValidationError):
            self.env['purchase.order.type'].create({
                'name': 'Test Mismatched Company Type',
                'company_id': self.company.id,
                'picking_type_id': self.other_receipt_type.id,
            })
