# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestComexProductLineStockPosition(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1,
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.supplier_location = cls.env.ref('stock.stock_location_suppliers')
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.transit_location = cls.env['stock.location'].create({
            'name': 'COMEX Test Transit',
            'usage': 'internal',
            'location_id': cls.stock_location.location_id.id,
            'company_id': cls.company.id,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'COMEX Stock Partner'})
        cls.product = cls.env['product.product'].create({
            'name': 'COMEX Untracked Product',
            'type': 'product',
        })
        cls.serial_product = cls.env['product.product'].create({
            'name': 'COMEX Serial Product',
            'type': 'product',
            'tracking': 'serial',
        })

    def _create_operation(self):
        return self.env['comex.operation'].create({
            'operation_type': 'import',
            'partner_id': self.partner.id,
            'date_operation': fields.Date.today(),
            'company_id': self.company.id,
        })

    def _create_line(self, operation, product, qty=2.0):
        return self.env['comex.operation.product.line'].create({
            'operation_id': operation.id,
            'product_id': product.id,
            'name': product.display_name,
            'product_qty': qty,
            'product_uom': product.uom_id.id,
            'price_unit': 100.0,
            'origin_type': 'manual',
        })

    def _make_move(self, line, source, destination, qty=2.0, lot=None, partner=None,
                   picking_type=None):
        picking = self.env['stock.picking']
        if partner:
            if not picking_type:
                picking_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'internal'),
                    ('company_id', '=', self.company.id),
                ], limit=1)
            picking = picking.create({
                'picking_type_id': picking_type.id,
                'location_id': source.id,
                'location_dest_id': destination.id,
                'partner_id': partner.id,
                'company_id': self.company.id,
            })
        move = self.env['stock.move'].create({
            'name': line.product_id.display_name,
            'product_id': line.product_id.id,
            'product_uom': line.product_id.uom_id.id,
            'product_uom_qty': qty,
            'location_id': source.id,
            'location_dest_id': destination.id,
            'company_id': self.company.id,
            'picking_id': picking.id,
            'comex_operation_id': line.operation_id.id,
            'comex_product_line_id': line.id,
        })
        move._action_confirm()
        move._action_assign()
        move.move_line_ids.unlink()
        move_line_values = {
            'move_id': move.id,
            'product_id': move.product_id.id,
            'product_uom_id': move.product_uom.id,
            'location_id': source.id,
            'location_dest_id': destination.id,
            'quantity': qty,
            'company_id': self.company.id,
        }
        if lot:
            move_line_values['lot_id'] = lot.id
        self.env['stock.move.line'].create(move_line_values)
        move.picked = True
        move._action_done()
        return move

    def _create_serial(self, name):
        return self.env['stock.lot'].create({
            'name': name,
            'product_id': self.serial_product.id,
            'company_id': self.company.id,
        })

    def test_untracked_line_reports_reached_location(self):
        """An untracked line is located by the net balance of its COMEX moves."""
        operation = self._create_operation()
        line = self._create_line(operation, self.product)

        self._make_move(line, self.supplier_location, self.transit_location)

        self.assertEqual(line.current_location_ids, self.transit_location)
        self.assertEqual(line.stock_status, 'internal')

    def test_untracked_line_split_between_two_locations(self):
        """Units spread across stages report every location, not just one."""
        operation = self._create_operation()
        line = self._create_line(operation, self.product, qty=3.0)

        self._make_move(line, self.supplier_location, self.transit_location, qty=3.0)
        self._make_move(line, self.transit_location, self.stock_location, qty=1.0)

        self.assertEqual(
            line.current_location_ids,
            self.transit_location | self.stock_location,
        )

    def test_untracked_line_drops_emptied_location(self):
        """A location emptied outside the COMEX chain is no longer reported."""
        operation = self._create_operation()
        line = self._create_line(operation, self.product)

        self._make_move(line, self.supplier_location, self.transit_location)
        # Goods leave through a transfer that is not part of the COMEX chain.
        outside_move = self.env['stock.move'].create({
            'name': 'Outside transfer',
            'product_id': self.product.id,
            'product_uom': self.product.uom_id.id,
            'product_uom_qty': 2.0,
            'location_id': self.transit_location.id,
            'location_dest_id': self.stock_location.id,
            'company_id': self.company.id,
        })
        outside_move._action_confirm()
        outside_move._action_assign()
        outside_move.move_line_ids.quantity = 2.0
        outside_move.picked = True
        outside_move._action_done()
        line.invalidate_recordset()

        self.assertNotIn(self.transit_location, line.current_location_ids)

    def test_serial_line_follows_lot_location(self):
        """A tracked line is located through the stock of its serial numbers."""
        operation = self._create_operation()
        line = self._create_line(operation, self.serial_product, qty=1.0)
        serial = self._create_serial('COMEX-SERIAL-01')

        self._make_move(line, self.supplier_location, self.transit_location,
                        qty=1.0, lot=serial)

        self.assertEqual(line.lot_ids, serial)
        self.assertEqual(line.current_location_ids, self.transit_location)

    def test_serial_line_follows_manual_lot_relocation(self):
        """Editing stock.lot.location_id by hand is reflected immediately.

        The inverse of that field moves the quants through inventory moves that
        carry no COMEX link, so the position must be read from the quants.
        """
        operation = self._create_operation()
        line = self._create_line(operation, self.serial_product, qty=1.0)
        serial = self._create_serial('COMEX-SERIAL-02')
        self._make_move(line, self.supplier_location, self.transit_location,
                        qty=1.0, lot=serial)

        serial.location_id = self.stock_location
        line.invalidate_recordset()

        self.assertEqual(line.current_location_ids, self.stock_location)
        self.assertEqual(line.stock_status, 'internal')

    def test_serial_line_delivered_to_customer(self):
        """A delivered serial reports the customer location and status."""
        operation = self._create_operation()
        line = self._create_line(operation, self.serial_product, qty=1.0)
        serial = self._create_serial('COMEX-SERIAL-03')
        self._make_move(line, self.supplier_location, self.stock_location,
                        qty=1.0, lot=serial)

        self._make_move(line, self.stock_location, self.customer_location,
                        qty=1.0, lot=serial)
        line.invalidate_recordset()

        self.assertEqual(line.stock_status, 'delivered')
        self.assertEqual(line.current_location_ids, self.customer_location)

    def test_serial_line_returned(self):
        """A returned serial is distinguished from one never delivered."""
        operation = self._create_operation()
        line = self._create_line(operation, self.serial_product, qty=1.0)
        serial = self._create_serial('COMEX-SERIAL-04')
        self._make_move(line, self.supplier_location, self.stock_location,
                        qty=1.0, lot=serial)
        delivery = self._make_move(line, self.stock_location, self.customer_location,
                                   qty=1.0, lot=serial)

        return_move = self._make_move(line, self.customer_location, self.stock_location,
                                      qty=1.0, lot=serial)
        return_move.origin_returned_move_id = delivery
        line.invalidate_recordset()

        self.assertEqual(line.stock_status, 'returned')

    def test_line_without_moves_is_pending(self):
        """A line with no done move has no location."""
        operation = self._create_operation()
        line = self._create_line(operation, self.product)

        self.assertFalse(line.current_location_ids)
        self.assertEqual(line.stock_status, 'pending')

    def test_two_lines_same_product_are_independent(self):
        """The dedicated move link keeps lines of the same product separated."""
        operation = self._create_operation()
        first_line = self._create_line(operation, self.product)
        second_line = self._create_line(operation, self.product)

        self._make_move(first_line, self.supplier_location, self.transit_location)
        self._make_move(second_line, self.supplier_location, self.stock_location)

        self.assertEqual(first_line.current_location_ids, self.transit_location)
        self.assertEqual(second_line.current_location_ids, self.stock_location)

    def test_search_by_current_location(self):
        """The location column is filterable."""
        operation = self._create_operation()
        line = self._create_line(operation, self.product)
        self._make_move(line, self.supplier_location, self.transit_location)

        found = self.env['comex.operation.product.line'].search([
            ('current_location_ids', 'in', self.transit_location.ids),
        ])

        self.assertIn(line, found)

    def test_search_by_stock_status(self):
        """The stock status is filterable."""
        operation = self._create_operation()
        line = self._create_line(operation, self.product)
        self._make_move(line, self.supplier_location, self.transit_location)

        found = self.env['comex.operation.product.line'].search([
            ('stock_status', '=', 'internal'),
        ])

        self.assertIn(line, found)

    def test_location_display_is_stored_and_sortable(self):
        """The location text is materialised, so the column can be sorted."""
        operation = self._create_operation()
        line = self._create_line(operation, self.product)
        self._make_move(line, self.supplier_location, self.transit_location)

        self.assertEqual(line.current_location_display, self.transit_location.complete_name)
        # A stored column can be used in an ORDER BY.
        self.assertIn(
            line,
            self.env['comex.operation.product.line'].search(
                [('id', '=', line.id)], order='current_location_display asc',
            ),
        )

    def test_serial_names_column(self):
        """The serial numbers are also exposed as a sortable text column."""
        operation = self._create_operation()
        line = self._create_line(operation, self.serial_product, qty=1.0)
        serial = self._create_serial('COMEX-SERIAL-05')

        self._make_move(line, self.supplier_location, self.stock_location,
                        qty=1.0, lot=serial)

        self.assertEqual(line.lot_name_display, 'COMEX-SERIAL-05')

    def test_last_delivery_partner_covers_internal_transfers(self):
        """The contact of the last transfer is kept, even for internal moves.

        stock.lot.last_delivery_partner_id only looks at outgoing transfers, so
        it stays empty when a machine is sent to a dealer location.
        """
        dealer = self.env['res.partner'].create({'name': 'COMEX Test Dealer'})
        dealer_location = self.env['stock.location'].create({
            'name': 'COMEX Test Dealer Location',
            'usage': 'internal',
            'location_id': self.stock_location.location_id.id,
            'company_id': self.company.id,
        })
        operation = self._create_operation()
        line = self._create_line(operation, self.serial_product, qty=1.0)
        serial = self._create_serial('COMEX-SERIAL-06')
        self._make_move(line, self.supplier_location, self.stock_location,
                        qty=1.0, lot=serial)

        self._make_move(line, self.stock_location, dealer_location,
                        qty=1.0, lot=serial, partner=dealer)

        self.assertEqual(line.current_location_ids, dealer_location)
        self.assertEqual(line.last_delivery_partner_id, dealer)
        self.assertFalse(serial.last_delivery_partner_id)

    def test_last_delivery_partner_ignores_comex_inbound(self):
        """Goods still travelling the COMEX chain have no delivery contact.

        The receipt and the chained transfers carry the supplier as contact, and
        reporting it would wrongly suggest the goods were handed to someone.
        """
        supplier = self.env['res.partner'].create({'name': 'COMEX Test Supplier'})
        receipt_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        chain_type = self.env['stock.picking.type'].create({
            'name': 'COMEX Test Chain',
            'code': 'internal',
            'sequence_code': 'COMEX/TEST',
            'company_id': self.company.id,
            'warehouse_id': self.warehouse.id,
            'is_comex_import': True,
        })
        operation = self._create_operation()
        line = self._create_line(operation, self.product)

        self._make_move(line, self.supplier_location, self.transit_location,
                        partner=supplier, picking_type=receipt_type)
        self._make_move(line, self.transit_location, self.stock_location,
                        partner=supplier, picking_type=chain_type)

        self.assertEqual(line.current_location_ids, self.stock_location)
        self.assertFalse(line.last_delivery_partner_id)

    def test_operation_aggregates_lots_for_the_smart_button(self):
        """The operation exposes the lots of its lines for the smart button."""
        operation = self._create_operation()
        first_line = self._create_line(operation, self.serial_product, qty=1.0)
        second_line = self._create_line(operation, self.serial_product, qty=1.0)
        first_serial = self._create_serial('COMEX-SERIAL-07')
        second_serial = self._create_serial('COMEX-SERIAL-08')

        self._make_move(first_line, self.supplier_location, self.stock_location,
                        qty=1.0, lot=first_serial)
        self._make_move(second_line, self.supplier_location, self.stock_location,
                        qty=1.0, lot=second_serial)
        operation.invalidate_recordset()

        self.assertEqual(operation.lot_ids, first_serial | second_serial)
        self.assertEqual(operation.lot_count, 2)
        action = operation.action_view_lots()
        self.assertEqual(action['res_model'], 'stock.lot')
        self.assertEqual(
            sorted(action['domain'][0][2]),
            sorted((first_serial | second_serial).ids),
        )

    def test_purchase_qty_received_is_not_inflated_by_the_chain(self):
        """Guard: the COMEX chain must never be counted as received quantity."""
        operation = self._create_operation()
        order = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'comex_operation_id': operation.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_qty': 2.0,
                'price_unit': 50.0,
            })],
        })
        order.write({'state': 'purchase'})
        line = operation.product_line_ids

        self._make_move(line, self.transit_location, self.stock_location, qty=2.0)
        order.order_line.invalidate_recordset()

        self.assertNotIn(
            order.order_line,
            self.env['stock.move'].search([
                ('comex_product_line_id', '=', line.id),
            ]).mapped('purchase_line_id'),
        )
        self.assertLessEqual(order.order_line.qty_received, 2.0)
