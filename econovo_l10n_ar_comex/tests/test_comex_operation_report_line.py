# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestComexOperationReportLine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.report = cls.env['comex.operation.report.line']
        cls.product_line_model = cls.env['comex.operation.product.line']
        cls.partner = cls.env['res.partner'].create({'name': 'COMEX Test Partner'})
        cls.product = cls.env['product.product'].create({
            'name': 'COMEX Test Product',
            'type': 'consu',
            'standard_price': 100.0,
            'list_price': 150.0,
        })
        cls.usd = cls.env.ref('base.USD')
        cls.env['res.currency.rate'].create({
            'name': fields.Date.to_date('2026-01-01'),
            'currency_id': cls.usd.id,
            'company_id': cls.company.id,
            'rate': 0.001,
        })
        cls.operation = cls._create_operation('import')

    @classmethod
    def _create_operation(cls, operation_type='import', **values):
        operation_values = {
            'operation_type': operation_type,
            'partner_id': cls.partner.id,
            'date_operation': fields.Date.to_date('2026-02-01'),
            'currency_id': cls.usd.id,
            'company_id': cls.company.id,
        }
        operation_values.update(values)
        return cls.env['comex.operation'].create(operation_values)

    def _create_product_line(self, operation, price_unit=100.0, product_qty=2.0):
        return self.product_line_model.create({
            'operation_id': operation.id,
            'product_id': self.product.id,
            'name': self.product.display_name,
            'product_qty': product_qty,
            'product_uom': self.product.uom_id.id,
            'price_unit': price_unit,
            'origin_type': 'manual',
        })

    def _report_rows(self, operation):
        return self.report.search([('operation_id', '=', operation.id)])

    def test_report_grain_and_header_values(self):
        """One report row per product line, carrying the parent operation values."""
        self.operation.write({
            'date_etd': fields.Date.to_date('2026-02-10'),
            'transport_mode': 'air',
        })
        lines = self._create_product_line(self.operation)
        lines |= self._create_product_line(self.operation, price_unit=50.0)

        rows = self._report_rows(self.operation)

        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows.mapped('product_line_id').ids), set(lines.ids))
        self.assertTrue(all(rows.mapped('has_product_line')))
        for row in rows:
            self.assertEqual(row.operation_name, self.operation.name)
            self.assertEqual(row.partner_id, self.partner)
            self.assertEqual(row.date_etd, self.operation.date_etd)
            self.assertEqual(row.transport_mode, 'air')
            self.assertEqual(row.company_id, self.company)

    def test_operation_without_lines_yields_single_row(self):
        """Operations with no product line are not lost from the analysis."""
        operation = self._create_operation('export')

        rows = self._report_rows(operation)

        self.assertEqual(len(rows), 1)
        self.assertFalse(rows.has_product_line)
        self.assertFalse(rows.product_id)
        self.assertEqual(rows.line_share, 1.0)

    def test_line_share_sums_to_one(self):
        """The prorated weights of an operation always add up to 1."""
        self._create_product_line(self.operation, price_unit=100.0)
        self._create_product_line(self.operation, price_unit=300.0)

        rows = self._report_rows(self.operation)

        self.assertAlmostEqual(sum(rows.mapped('line_share')), 1.0, places=6)

    def test_line_share_falls_back_to_equal_split(self):
        """Zero-valued operations split the header amounts equally."""
        self._create_product_line(self.operation, price_unit=0.0)
        self._create_product_line(self.operation, price_unit=0.0)

        rows = self._report_rows(self.operation)

        self.assertAlmostEqual(sum(rows.mapped('line_share')), 1.0, places=6)
        self.assertEqual(len(set(rows.mapped('line_share'))), 1)

    def test_vep_amount_share_sums_to_header(self):
        """Prorated VEP adds up to the operation VEP, the raw column does not."""
        clearance = self.env['comex.customs.clearance'].create({
            'operation_id': self.operation.id,
            'vep_amount': 1000.0,
        })
        self._create_product_line(self.operation, price_unit=100.0)
        self._create_product_line(self.operation, price_unit=300.0)

        rows = self._report_rows(self.operation)

        self.assertEqual(clearance.vep_amount, 1000.0)
        self.assertAlmostEqual(sum(rows.mapped('vep_amount_share')), 1000.0, places=2)
        self.assertEqual(set(rows.mapped('vep_amount')), {1000.0})

    def test_archived_operation_is_hidden_by_default(self):
        """Archived operations disappear from the analysis unless asked for."""
        self._create_product_line(self.operation)
        self.operation.action_archive()

        self.assertFalse(self._report_rows(self.operation))
        self.assertTrue(
            self.report.with_context(active_test=False).search([
                ('operation_id', '=', self.operation.id),
            ])
        )

    def test_company_currency_conversion(self):
        """Line amounts are also exposed in the company currency."""
        self._create_product_line(self.operation, price_unit=100.0, product_qty=2.0)

        row = self._report_rows(self.operation)

        self.assertEqual(row.company_currency_id, self.company.currency_id)
        self.assertTrue(self.operation.currency_rate)
        self.assertAlmostEqual(
            row.price_subtotal_company,
            row.price_subtotal / self.operation.currency_rate,
            places=2,
        )

    def test_reading_lines_does_not_write(self):
        """Reading never triggers a synchronisation (removed sync-on-read)."""
        line = self._create_product_line(self.operation)
        self.env.flush_all()
        write_date_before = line.write_date

        self.product_line_model.search([])
        self.report.search([])
        self.env.flush_all()
        line.invalidate_recordset()

        self.assertEqual(line.write_date, write_date_before)

    def test_sync_from_confirmed_purchase_order(self):
        """Confirmed purchase order lines are mirrored as product lines."""
        order = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'currency_id': self.usd.id,
            'comex_operation_id': self.operation.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 3.0,
                'price_unit': 120.0,
            })],
        })

        order.write({'state': 'purchase'})

        lines = self.operation.product_line_ids
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.origin_type, 'purchase')
        self.assertEqual(lines.purchase_line_id, order.order_line)
        self.assertEqual(lines.product_qty, 3.0)
        self.assertEqual(len(self._report_rows(self.operation)), 1)

    def test_sync_from_confirmed_sale_order(self):
        """Confirmed sale order lines are mirrored as product lines."""
        operation = self._create_operation('export')
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'currency_id': self.usd.id,
            'comex_operation_id': operation.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 5.0,
                'price_unit': 200.0,
            })],
        })

        order.write({'state': 'sale'})

        lines = operation.product_line_ids
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.origin_type, 'sale')
        self.assertEqual(lines.sale_line_id, order.order_line)
        self.assertEqual(lines.product_qty, 5.0)

        rows = self._report_rows(operation)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows.has_product_line)
