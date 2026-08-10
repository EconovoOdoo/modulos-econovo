# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import Form, tagged, TransactionCase


@tagged('post_install', '-at_install')
class TestStockMoveSubcontractingPurchaseOrders(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        main_partner = cls.env['res.partner'].create({'name': 'Main Partner'})
        cls.subcontractor = cls.env['res.partner'].create({
            'name': 'Subcontractor Partner',
            'parent_id': main_partner.id,
        })
        cls.component = cls.env['product.product'].create({
            'name': 'Component', 'type': 'product',
        })
        cls.finished_product = cls.env['product.product'].create({
            'name': 'Subcontracted Product', 'type': 'product',
        })
        bom_form = Form(cls.env['mrp.bom'])
        bom_form.type = 'subcontract'
        bom_form.product_tmpl_id = cls.finished_product.product_tmpl_id
        bom_form.subcontractor_ids.add(cls.subcontractor)
        with bom_form.bom_line_ids.new() as line:
            line.product_id = cls.component
            line.product_qty = 1
        cls.bom = bom_form.save()

        resupply_route = cls.env['stock.route'].search(
            [('name', '=', 'Resupply Subcontractor on Order')])
        cls.component.route_ids = [(4, resupply_route.id)]

    def test_get_subcontracting_purchase_orders(self):
        """The resupply move (sending the component to the subcontractor)
        is never linked to the PO directly - only through the procurement
        group it shares with the subcontracting MO, which itself points to
        the incoming shipment that MO was created for.
        """
        purchase_order = self.env['purchase.order'].create({
            'partner_id': self.subcontractor.id,
            'order_line': [(0, 0, {
                'product_id': self.finished_product.id,
                'product_qty': 1.0,
                'product_uom': self.finished_product.uom_id.id,
                'price_unit': 100.0,
                'name': self.finished_product.name,
            })],
        })
        purchase_order.button_confirm()

        mo = self.env['mrp.production'].search([('bom_id', '=', self.bom.id)], limit=1)
        self.assertTrue(mo, "Confirming the purchase order should create a subcontracting MO")
        resupply_picking = mo.picking_ids.filtered(
            lambda p: p.picking_type_id == p.picking_type_id.warehouse_id.subcontracting_resupply_type_id)
        self.assertTrue(resupply_picking, "A resupply picking should have been created")
        self.assertFalse(resupply_picking.move_ids.purchase_line_id)

        purchase_orders = resupply_picking.move_ids._get_subcontracting_purchase_orders()

        self.assertEqual(purchase_orders, purchase_order)

    def test_get_subcontracting_purchase_orders_none_found(self):
        """A move unrelated to any subcontracting flow returns an empty
        recordset, not an error."""
        stock_location = self.env.ref('stock.stock_location_stock')
        move = self.env['stock.move'].create({
            'name': self.component.name,
            'location_id': stock_location.id,
            'location_dest_id': stock_location.id,
            'product_id': self.component.id,
            'product_uom': self.component.uom_id.id,
            'product_uom_qty': 1.0,
        })

        self.assertFalse(move._get_subcontracting_purchase_orders())
