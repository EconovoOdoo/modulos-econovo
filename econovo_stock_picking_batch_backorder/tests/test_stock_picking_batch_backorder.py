# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestStockPickingBatchBackorder(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.picking_type_out = cls.env.ref('stock.picking_type_out')
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.partner = cls.env['res.partner'].create({'name': 'Batch Backorder Partner'})
        cls.product = cls.env['product.product'].create({
            'name': 'Batch Backorder Product',
            'type': 'product',
        })
        cls.env['stock.quant']._update_available_quantity(
            cls.product, cls.stock_location, 100.0)

    def _create_delivery(self, quantity=10.0):
        picking = self.env['stock.picking'].create({
            'location_dest_id': self.customer_location.id,
            'location_id': self.stock_location.id,
            'partner_id': self.partner.id,
            'picking_type_id': self.picking_type_out.id,
        })
        self.env['stock.move'].create({
            'location_dest_id': self.customer_location.id,
            'location_id': self.stock_location.id,
            'name': self.product.name,
            'picking_id': picking.id,
            'product_id': self.product.id,
            'product_uom': self.product.uom_id.id,
            'product_uom_qty': quantity,
        })
        picking.action_confirm()
        picking.action_assign()
        return picking

    def _create_batch(self, pickings):
        batch = self.env['stock.picking.batch'].create({
            'picking_ids': [Command.set(pickings.ids)],
            'picking_type_id': self.picking_type_out.id,
            'user_id': self.env.user.id,
        })
        batch.action_confirm()
        return batch

    def _pick_partially(self, pickings, quantity=4.0):
        for move in pickings.move_ids:
            move.quantity = quantity
            move.picked = True

    def _process_backorder_wizard(self, action, values=None):
        self.assertEqual(action.get('res_model'), 'stock.backorder.confirmation')
        wizard = self.env['stock.backorder.confirmation'].with_context(
            **action['context']).create(values or {})
        wizard.process()
        return wizard

    def test_backorder_batch_created(self):
        """Backorders of a partially validated batch land in a new batch."""
        pickings = self._create_delivery() | self._create_delivery()
        batch = self._create_batch(pickings)
        self._pick_partially(pickings)

        self._process_backorder_wizard(batch.action_done())

        backorders = pickings.backorder_ids
        self.assertEqual(len(backorders), 2)
        self.assertEqual(len(backorders.batch_id), 1)
        new_batch = backorders.batch_id
        self.assertEqual(new_batch.origin_batch_id, batch)
        self.assertEqual(new_batch.state, 'draft')
        self.assertEqual(new_batch.picking_type_id, batch.picking_type_id)
        self.assertEqual(new_batch.user_id, batch.user_id)
        self.assertFalse(new_batch.is_wave)
        self.assertEqual(batch.backorder_batch_count, 1)

    def test_backorder_batch_includes_fully_untouched_pickings(self):
        """A transfer with literally nothing picked is detached from the batch
        WITHOUT ever being validated (same record, no backorder created for
        it) - it must still join the new batch alongside the backorders of
        its siblings, matching the reported scenario (a transfer left with 0
        delivered items was missing from the resulting batch).
        """
        picked_pickings = self._create_delivery() | self._create_delivery()
        untouched_picking = self._create_delivery()
        batch = self._create_batch(picked_pickings | untouched_picking)
        self._pick_partially(picked_pickings)

        self._process_backorder_wizard(batch.action_done())

        self.assertEqual(untouched_picking.state, 'assigned')
        self.assertFalse(untouched_picking.backorder_ids)
        new_batch = picked_pickings.backorder_ids.batch_id
        self.assertEqual(len(new_batch), 1)
        self.assertEqual(untouched_picking.batch_id, new_batch)
        self.assertEqual(new_batch.origin_batch_id, batch)
        self.assertEqual(len(new_batch.picking_ids), 3)

    def test_backorder_batch_not_created_when_disabled(self):
        """Unticking the option keeps the legacy behavior."""
        pickings = self._create_delivery() | self._create_delivery()
        batch = self._create_batch(pickings)
        self._pick_partially(pickings)

        self._process_backorder_wizard(
            batch.action_done(), {'create_backorder_batch': False})

        self.assertFalse(pickings.backorder_ids.batch_id)

    def test_backorder_batch_created_with_single_backorder(self):
        """A single backorder is batched as well."""
        picking = self._create_delivery()
        batch = self._create_batch(picking)
        self._pick_partially(picking)

        self._process_backorder_wizard(batch.action_done())

        self.assertEqual(picking.backorder_ids.batch_id.origin_batch_id, batch)

    def test_backorder_batch_state_in_progress(self):
        """The operation type drives the status of the new batch."""
        pickings = self._create_delivery() | self._create_delivery()
        batch = self._create_batch(pickings)
        self.picking_type_out.backorder_batch_state = 'in_progress'
        self._pick_partially(pickings)

        self._process_backorder_wizard(batch.action_done())

        self.assertEqual(pickings.backorder_ids.batch_id.state, 'in_progress')

    def test_backorder_batch_takes_precedence_over_auto_batch(self):
        """Automatic Batches must not grab the backorders."""
        pickings = self._create_delivery() | self._create_delivery()
        batch = self._create_batch(pickings)
        # Enabled once the transfers are batched to not auto-batch them on confirmation.
        self.picking_type_out.write({
            'auto_batch': True,
            'batch_group_by_partner': True,
        })
        self._pick_partially(pickings)

        self._process_backorder_wizard(batch.action_done())

        backorders = pickings.backorder_ids
        self.assertEqual(len(backorders.batch_id), 1)
        self.assertEqual(backorders.batch_id.origin_batch_id, batch)

    def test_backorder_of_unbatched_picking_is_not_batched(self):
        """Transfers outside of a batch are left untouched."""
        picking = self._create_delivery()
        self._pick_partially(picking)

        self._process_backorder_wizard(
            picking.button_validate(), {'create_backorder_batch': True})

        self.assertFalse(picking.backorder_ids.batch_id)
