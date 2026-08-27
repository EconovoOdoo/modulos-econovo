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

    def test_price_subtotal_is_tagged_with_the_order_currency_not_the_operation(self):
        """Regression: each line keeps its own order's currency, not the operation's.

        price_subtotal used to be tagged with the operation's currency, so a EUR
        purchase order line under an operation that stayed in USD (because a
        second order in USD keeps the currency genuinely mixed, so it is not
        auto-inferred) displayed "USD 730.00" for an amount that was genuinely
        730 EUR, silently misreporting the FOB subtotal (production case:
        IMP/OSEYS/00852).
        """
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.eur, qty=20.0, price_unit=36.5)
        self._create_confirmed_purchase_order(operation, self.usd, qty=1.0, price_unit=1.0)

        self.assertEqual(operation.currency_id, self.usd)
        eur_line = operation.product_line_ids.filtered(lambda l: l.origin_currency_id == self.eur)
        self.assertEqual(eur_line.price_subtotal, 730.0)
        self.assertNotEqual(eur_line.price_subtotal, eur_line.price_subtotal_usd)
        self.assertAlmostEqual(eur_line.price_subtotal_usd, 730.0 * (0.001 / 0.0009), places=2)

    def test_price_subtotal_usd_converts_from_the_order_currency(self):
        """A EUR purchase order line is converted to USD using its own rate."""
        operation = self._create_operation(self.eur)
        self._create_confirmed_purchase_order(operation, self.eur, qty=1.0, price_unit=100.0)

        line = operation.product_line_ids
        self.assertEqual(line.price_subtotal, 100.0)
        # 100 EUR -> USD at (rate_usd / rate_eur) = 0.001 / 0.0009.
        self.assertAlmostEqual(line.price_subtotal_usd, 100.0 * (0.001 / 0.0009), places=2)

    def test_price_unit_usd_same_currency_is_a_no_op(self):
        """A line already in USD is not altered by the conversion."""
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.usd, qty=2.0, price_unit=50.0)

        line = operation.product_line_ids
        self.assertEqual(line.price_unit, 50.0)
        self.assertEqual(line.price_unit_usd, 50.0)

    def test_price_unit_is_tagged_with_the_order_currency_not_the_operation(self):
        """A EUR purchase order line's unit price must show EUR, mirroring the
        same fix already applied to price_subtotal.
        """
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.eur, qty=20.0, price_unit=36.5)
        self._create_confirmed_purchase_order(operation, self.usd, qty=1.0, price_unit=1.0)

        eur_line = operation.product_line_ids.filtered(lambda l: l.origin_currency_id == self.eur)
        self.assertEqual(eur_line.price_unit, 36.5)
        self.assertNotEqual(eur_line.price_unit, eur_line.price_unit_usd)
        self.assertAlmostEqual(eur_line.price_unit_usd, 36.5 * (0.001 / 0.0009), places=2)

    def test_price_unit_usd_converts_from_the_order_currency(self):
        """A EUR purchase order line's unit price is converted using its own rate."""
        operation = self._create_operation(self.eur)
        self._create_confirmed_purchase_order(operation, self.eur, qty=1.0, price_unit=100.0)

        line = operation.product_line_ids
        self.assertEqual(line.price_unit, 100.0)
        self.assertAlmostEqual(line.price_unit_usd, 100.0 * (0.001 / 0.0009), places=2)

    def test_amount_fob_is_computed_not_manual(self):
        """The operation FOB amount is the sum of its confirmed order lines."""
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.usd, qty=2.0, price_unit=50.0)
        self._create_confirmed_purchase_order(operation, self.usd, qty=1.0, price_unit=30.0)

        self.assertEqual(operation.amount_fob, 130.0)
        self.assertEqual(operation.amount_fob_usd, 130.0)

    def test_currency_id_is_inferred_from_a_single_currency_order(self):
        """A lone confirmed order in another currency corrects the USD default."""
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.eur, qty=1.0, price_unit=100.0)

        self.assertEqual(operation.currency_id, self.eur)
        self.assertFalse(operation.currency_mismatch)

    def test_currency_id_stays_manual_without_any_order(self):
        """With nothing to infer from, the field is left exactly as set."""
        operation = self._create_operation(self.eur)

        self.assertEqual(operation.currency_id, self.eur)

    def test_currency_id_stays_manual_with_mixed_currency_orders(self):
        """Mixed currencies among the orders have no single correct value to
        adopt, so the operation's own currency is left untouched.
        """
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.eur, qty=1.0, price_unit=100.0)
        self._create_confirmed_purchase_order(operation, self.usd, qty=1.0, price_unit=1.0)

        self.assertEqual(operation.currency_id, self.usd)

    def test_currency_mismatch_is_flagged_for_mixed_currency_orders(self):
        """Regression: a genuine currency mix cannot be resolved to one value,
        so it must stay flagged, while FOB amounts stay correct per line
        (production case: IMP/OSEYS/00850).
        """
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.eur, qty=1.0, price_unit=100.0)
        self._create_confirmed_purchase_order(operation, self.usd, qty=1.0, price_unit=1.0)

        self.assertTrue(operation.currency_mismatch)
        expected_usd = 100.0 * (0.001 / 0.0009) + 1.0
        self.assertAlmostEqual(operation.amount_fob_usd, expected_usd, places=2)

    def test_currency_mismatch_is_false_when_currencies_agree(self):
        """No warning when the operation's currency matches its orders."""
        operation = self._create_operation(self.usd)
        self._create_confirmed_purchase_order(operation, self.usd, qty=1.0, price_unit=100.0)

        self.assertFalse(operation.currency_mismatch)

    def test_amount_fob_usd_is_stable_across_operation_currencies(self):
        """amount_fob_usd does not depend on the operation's own currency."""
        operation = self._create_operation(self.eur)
        self._create_confirmed_purchase_order(operation, self.eur, qty=1.0, price_unit=100.0)

        expected_usd = 100.0 * (0.001 / 0.0009)
        self.assertAlmostEqual(operation.amount_fob_usd, expected_usd, places=2)
        # Converting the USD total back into EUR must recover the original amount.
        self.assertAlmostEqual(operation.amount_fob, 100.0, places=2)
        self.assertFalse(operation.currency_mismatch)

    def test_amount_fob_does_not_drift_when_the_order_date_differs(self):
        """Regression: a same-currency line must not round-trip through USD.

        Production case (operation IMP/OSEYS/00835): the operation and its
        single purchase order line were both in EUR, but the order was dated
        after the operation. Converting to USD at the order's date and back to
        EUR at the operation's date applied two different EUR rates, drifting
        the FOB amount away from the source document (EUR 107,879.00 became
        EUR 106,890.89).
        """
        # A second EUR rate, so the order's date and the operation's date
        # resolve to genuinely different rates, exactly like production.
        self.env['res.currency.rate'].create({
            'name': fields.Date.to_date('2026-03-01'),
            'currency_id': self.eur.id,
            'company_id': self.company.id,
            'rate': 0.00097,
        })
        operation = self.env['comex.operation'].create({
            'operation_type': 'import',
            'partner_id': self.partner.id,
            'date_operation': fields.Date.to_date('2026-03-10'),
            'currency_id': self.eur.id,
            'company_id': self.company.id,
        })
        order = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'currency_id': self.eur.id,
            'date_order': fields.Datetime.to_datetime('2026-02-15 00:00:00'),
            'comex_operation_id': operation.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 1.0,
                'price_unit': 107879.0,
            })],
        })
        order.write({'state': 'purchase'})

        self.assertEqual(operation.product_line_ids.price_subtotal, 107879.0)
        self.assertEqual(operation.amount_fob, 107879.0)

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
