# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestComexOperationFobUsd(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({'name': 'COMEX FOB Test Partner'})
        cls.product = cls.env['product.product'].create({
            'name': 'COMEX FOB Test Product',
            'type': 'consu',
        })
        cls.usd = cls.env.ref('base.USD')
        cls.eur = cls.env.ref('base.EUR')
        cls.eur.active = True
        # 1 ARS = 0.001 USD (1000 ARS per USD) and 1 ARS = 0.0009 EUR (~1111 ARS per EUR).
        cls.env['res.currency.rate'].create({
            'name': fields.Date.to_date('2026-01-01'),
            'currency_id': cls.usd.id,
            'company_id': cls.company.id,
            'rate': 0.001,
        })
        cls.env['res.currency.rate'].create({
            'name': fields.Date.to_date('2026-01-01'),
            'currency_id': cls.eur.id,
            'company_id': cls.company.id,
            'rate': 0.0009,
        })

    def _create_operation(self, currency):
        return self.env['comex.operation'].create({
            'operation_type': 'import',
            'partner_id': self.partner.id,
            'date_operation': fields.Date.to_date('2026-02-01'),
            'currency_id': currency.id,
            'company_id': self.company.id,
        })

    def _create_confirmed_purchase_order(self, operation, currency, qty=1.0, price_unit=100.0):
        order = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'currency_id': currency.id,
            'date_order': fields.Datetime.to_datetime('2026-01-15 00:00:00'),
            'comex_operation_id': operation.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': qty,
                'price_unit': price_unit,
            })],
        })
        order.write({'state': 'purchase'})
        return order

    def test_price_subtotal_usd_same_currency_is_a_no_op(self):
        """A line already in USD is not altered by the conversion."""
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.usd, qty=2.0, price_unit=50.0)

        line = operation.product_line_ids
        self.assertEqual(line.price_subtotal, 100.0)
        self.assertEqual(line.price_subtotal_usd, 100.0)

    def test_price_subtotal_usd_converts_from_the_order_currency(self):
        """A EUR purchase order line is converted to USD using its own rate."""
        operation = self._create_operation(self.eur)
        self._create_confirmed_purchase_order(operation, self.eur, qty=1.0, price_unit=100.0)

        line = operation.product_line_ids
        self.assertEqual(line.price_subtotal, 100.0)
        # 100 EUR -> USD at (rate_usd / rate_eur) = 0.001 / 0.0009.
        self.assertAlmostEqual(line.price_subtotal_usd, 100.0 * (0.001 / 0.0009), places=2)

    def test_amount_fob_is_computed_not_manual(self):
        """The operation FOB amount is the sum of its confirmed order lines."""
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.usd, qty=2.0, price_unit=50.0)
        self._create_confirmed_purchase_order(operation, self.usd, qty=1.0, price_unit=30.0)

        self.assertEqual(operation.amount_fob, 130.0)
        self.assertEqual(operation.amount_fob_usd, 130.0)

    def test_amount_fob_usd_is_stable_across_operation_currencies(self):
        """amount_fob_usd does not depend on the operation's own currency."""
        operation = self._create_operation(self.eur)
        self._create_confirmed_purchase_order(operation, self.eur, qty=1.0, price_unit=100.0)

        expected_usd = 100.0 * (0.001 / 0.0009)
        self.assertAlmostEqual(operation.amount_fob_usd, expected_usd, places=2)
        # Converting the USD total back into EUR must recover the original amount.
        self.assertAlmostEqual(operation.amount_fob, 100.0, places=2)

    def test_amount_fob_cannot_be_written_manually(self):
        """amount_fob is a stored compute: writing it directly has no effect."""
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.usd, qty=1.0, price_unit=100.0)

        operation.write({'amount_fob': 999999.0})
        operation.invalidate_recordset()

        self.assertEqual(operation.amount_fob, 100.0)

    def test_operation_without_lines_has_zero_fob(self):
        """An operation with no confirmed order line has no FOB to report."""
        operation = self._create_operation(self.usd)

        self.assertEqual(operation.amount_fob, 0.0)
        self.assertEqual(operation.amount_fob_usd, 0.0)

    def test_manual_line_falls_back_to_operation_currency_and_date(self):
        """A manual line has no PO/SO to read from: use the operation's own data."""
        operation = self._create_operation(self.eur)
        line = self.env['comex.operation.product.line'].create({
            'operation_id': operation.id,
            'product_id': self.product.id,
            'name': self.product.display_name,
            'product_qty': 1.0,
            'product_uom': self.product.uom_id.id,
            'price_unit': 100.0,
            'origin_type': 'manual',
        })

        self.assertAlmostEqual(line.price_subtotal_usd, 100.0 * (0.001 / 0.0009), places=2)

    def test_stage_change_is_no_longer_blocked_by_actionable_transfers(self):
        """Moving an operation to another stage never raises, regardless of transfers."""
        operation = self._create_operation(self.usd)
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'comex_operation_id': operation.id,
        })
        other_stage = self.env['comex.operation.stage'].search([], limit=1, order='id desc')

        operation.write({'stage_id': other_stage.id})

        self.assertEqual(operation.stage_id, other_stage)
