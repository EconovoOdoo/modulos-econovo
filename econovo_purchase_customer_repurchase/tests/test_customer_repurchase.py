# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestCustomerRepurchase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.supplier_location = cls.env.ref('stock.stock_location_suppliers')

        cls.partner = cls.env['res.partner'].create({'name': 'Test Dealer'})
        cls.product = cls.env['product.product'].create({
            'name': 'Test Repurchase Machine',
            'type': 'product',
            'tracking': 'serial',
            'purchase_method': 'purchase',
        })

        common_type_vals = {
            'code': 'incoming',
            'warehouse_id': cls.warehouse.id,
            'company_id': cls.company.id,
            'default_location_dest_id': cls.stock_location.id,
            'use_create_lots': True,
            'use_existing_lots': True,
        }
        cls.repurchase_type = cls.env['stock.picking.type'].create(dict(
            common_type_vals,
            name='Test Repurchase from Customer',
            sequence_code='TSTRP',
            is_customer_repurchase=True,
        ))
        cls.standard_type = cls.env['stock.picking.type'].create(dict(
            common_type_vals,
            name='Test Standard Receipt',
            sequence_code='TSTIN',
        ))

    def _create_confirmed_purchase(self, picking_type):
        order = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'picking_type_id': picking_type.id,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_qty': 1,
                'product_uom': self.product.uom_po_id.id,
                'price_unit': 100.0,
            })],
        })
        order.button_confirm()
        return order

    def _deliver_serial(self, lot):
        """Send one unit of `lot` from stock to the customer location."""
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'partner_id': self.partner.id,
            'move_ids': [(0, 0, {
                'name': self.product.name,
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'product_uom': self.product.uom_id.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        picking.move_line_ids.write({'lot_id': lot.id, 'quantity': 1, 'picked': True})
        picking.with_context(skip_backorder=True).button_validate()
        return picking

    def _quantity_at(self, location, lot):
        quants = self.env['stock.quant'].search([
            ('product_id', '=', self.product.id),
            ('location_id', '=', location.id),
            ('lot_id', '=', lot.id),
        ])
        return sum(quants.mapped('quantity'))

    def _purchase_receipt_validation_is_supported(self):
        """False when an installed third-party addon breaks every purchase receipt.

        `gg_cost_dolarization` calls `stock.move._get_currency_convert_date()`, which it
        does not declare as a dependency and which is provided by
        `gg_document_dolarization`. When the latter is missing from the addons path,
        validating *any* purchase receipt raises, repurchase or not.
        """
        installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', 'gg_cost_dolarization'),
            ('state', '=', 'installed'),
        ])
        return not installed or hasattr(self.env['stock.move'], '_get_currency_convert_date')

    def test_repurchase_receipt_sources_from_customer_location(self):
        order = self._create_confirmed_purchase(self.repurchase_type)
        picking = order.picking_ids
        self.assertEqual(picking.location_id, self.customer_location)
        self.assertEqual(picking.move_ids.location_id, self.customer_location)
        self.assertEqual(picking.location_dest_id, self.stock_location)

    def test_standard_receipt_still_sources_from_vendor_location(self):
        order = self._create_confirmed_purchase(self.standard_type)
        picking = order.picking_ids
        self.assertEqual(picking.location_id, self.supplier_location)
        self.assertEqual(picking.move_ids.location_id, self.supplier_location)

    def test_flag_is_rejected_on_non_incoming_operation_type(self):
        with self.assertRaises(ValidationError):
            self.env['stock.picking.type'].create({
                'name': 'Test Invalid Repurchase',
                'code': 'outgoing',
                'sequence_code': 'TSTBAD',
                'warehouse_id': self.warehouse.id,
                'company_id': self.company.id,
                'default_location_src_id': self.stock_location.id,
                'is_customer_repurchase': True,
            })

    def test_repurchased_serial_can_be_sold_again(self):
        """Full round trip: sell a serial, buy it back, sell it again."""
        if not self._purchase_receipt_validation_is_supported():
            self.skipTest(
                "Incomplete addons path: no purchase receipt can be validated in this database.")
        lot = self.env['stock.lot'].create({
            'name': 'TEST-SN-REPURCHASE',
            'product_id': self.product.id,
            'company_id': self.company.id,
        })
        self.env['stock.quant']._update_available_quantity(
            self.product, self.stock_location, 1, lot_id=lot)

        self._deliver_serial(lot)
        self.assertEqual(self._quantity_at(self.customer_location, lot), 1)
        self.assertEqual(self._quantity_at(self.stock_location, lot), 0)

        order = self._create_confirmed_purchase(self.repurchase_type)
        receipt = order.picking_ids
        receipt.move_line_ids.write({'lot_id': lot.id, 'quantity': 1, 'picked': True})
        receipt.with_context(skip_backorder=True).button_validate()

        self.assertEqual(receipt.state, 'done')
        self.assertEqual(
            self._quantity_at(self.customer_location, lot), 0,
            "The repurchase must clear the balance left by the original delivery.")
        self.assertEqual(self._quantity_at(self.stock_location, lot), 1)
        self.assertEqual(
            self._quantity_at(self.supplier_location, lot), 0,
            "A repurchase must not create a counterpart in the vendor location.")

        # Without the fix this second delivery raises "The serial number has already been assigned".
        self._deliver_serial(lot)
        self.assertEqual(self._quantity_at(self.customer_location, lot), 1)
        self.assertEqual(self._quantity_at(self.stock_location, lot), 0)
