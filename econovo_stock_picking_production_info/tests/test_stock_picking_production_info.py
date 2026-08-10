# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestStockPickingProductionInfo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.workcenter = cls.env['mrp.workcenter'].create({'name': 'Test Workcenter'})
        cls.plan = cls.env['mrp.plan'].create({'name': 'Test Plan'})
        cls.bom_product = cls.env['product.product'].create({
            'name': 'Finished Product', 'type': 'product',
        })
        cls.component = cls.env['product.product'].create({
            'name': 'Component', 'type': 'product',
        })
        cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.bom_product.product_tmpl_id.id,
            'product_qty': 1.0,
            'bom_line_ids': [(0, 0, {'product_id': cls.component.id, 'product_qty': 1.0})],
        })

    def test_production_plan_and_workcenter_via_procurement_group(self):
        """The supply transfer's own move is never linked to the MO
        directly (no move_dest_ids/move_orig_ids chain at all in this
        Econovo install's replenishment-to-workcenter routes): the only
        real link is the procurement group shared with the MO.
        """
        stock_location = self.env.ref('stock.stock_location_stock')
        production = self.env['mrp.production'].create({
            'product_id': self.bom_product.id,
            'product_qty': 1.0,
            'plan_id': self.plan.id,
            'location_src_id': stock_location.id,
            'location_dest_id': stock_location.id,
        })
        production.action_confirm()
        self.assertTrue(production.procurement_group_id)
        self.env['mrp.workorder'].create({
            'name': 'Test Operation',
            'production_id': production.id,
            'workcenter_id': self.workcenter.id,
            'product_uom_id': self.bom_product.uom_id.id,
        })

        supply_picking = self.env['stock.picking'].create({
            'location_id': stock_location.id,
            'location_dest_id': stock_location.id,
            'picking_type_id': self.env.ref('stock.picking_type_internal').id,
            'group_id': production.procurement_group_id.id,
        })
        supply_move = self.env['stock.move'].create({
            'name': self.component.name,
            'location_id': stock_location.id,
            'location_dest_id': stock_location.id,
            'picking_id': supply_picking.id,
            'product_id': self.component.id,
            'product_uom': self.component.uom_id.id,
            'product_uom_qty': 1.0,
            'group_id': production.procurement_group_id.id,
        })
        self.assertFalse(supply_move.raw_material_production_id)
        self.assertFalse(supply_move.move_dest_ids)
        self.assertFalse(supply_move.move_orig_ids)

        self.assertEqual(supply_picking.production_plan_id, self.plan)
        self.assertEqual(supply_picking.workcenter_id, self.workcenter)

