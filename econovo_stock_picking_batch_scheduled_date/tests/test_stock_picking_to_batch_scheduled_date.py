# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestStockPickingToBatchScheduledDate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.picking_type_out = cls.env.ref('stock.picking_type_out')
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.product = cls.env['product.product'].create({
            'name': 'Scheduled Date Product',
            'type': 'product',
        })

    def _create_delivery(self):
        picking = self.env['stock.picking'].create({
            'location_dest_id': self.customer_location.id,
            'location_id': self.stock_location.id,
            'picking_type_id': self.picking_type_out.id,
        })
        self.env['stock.move'].create({
            'location_dest_id': self.customer_location.id,
            'location_id': self.stock_location.id,
            'name': self.product.name,
            'picking_id': picking.id,
            'product_id': self.product.id,
            'product_uom': self.product.uom_id.id,
            'product_uom_qty': 1.0,
        })
        return picking

    def test_scheduled_date_applied_to_new_batch_and_pickings(self):
        """A date typed in the wizard is applied to the new batch and to
        every transfer added to it."""
        pickings = self._create_delivery() | self._create_delivery()
        scheduled_date = fields.Datetime.to_datetime('2030-01-01 10:00:00')

        wizard = self.env['stock.picking.to.batch'].with_context(
            active_ids=pickings.ids).create({
                'mode': 'new',
                'scheduled_date': scheduled_date,
            })
        wizard.attach_pickings()

        batch = pickings.batch_id
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch.scheduled_date, scheduled_date)
        self.assertEqual(set(pickings.mapped('scheduled_date')), {scheduled_date})

    def test_scheduled_date_left_empty_keeps_native_behavior(self):
        """Leaving the field empty keeps the native compute untouched."""
        pickings = self._create_delivery() | self._create_delivery()
        original_dates = pickings.mapped('scheduled_date')

        wizard = self.env['stock.picking.to.batch'].with_context(
            active_ids=pickings.ids).create({'mode': 'new'})
        wizard.attach_pickings()

        batch = pickings.batch_id
        self.assertEqual(batch.scheduled_date, min(original_dates))
        self.assertEqual(pickings.mapped('scheduled_date'), original_dates)

    def test_scheduled_date_ignored_when_adding_to_existing_batch(self):
        """The field only applies to newly created batches."""
        existing_batch = self.env['stock.picking.batch'].create({
            'picking_type_id': self.picking_type_out.id,
        })
        picking = self._create_delivery()
        original_date = picking.scheduled_date

        wizard = self.env['stock.picking.to.batch'].with_context(
            active_ids=picking.ids).create({
                'mode': 'existing',
                'batch_id': existing_batch.id,
                'scheduled_date': fields.Datetime.to_datetime('2030-01-01 10:00:00'),
            })
        wizard.attach_pickings()

        self.assertEqual(picking.scheduled_date, original_date)
