from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestStockSplitPickingCounter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.src_location = cls.env.ref("stock.stock_location_stock")
        cls.dest_location = cls.env.ref("stock.stock_location_customers")
        cls.partner = cls.env["res.partner"].create({"name": "Test partner"})
        cls.product = cls.env["product.product"].create(
            {"name": "Test product", "detailed_type": "product"}
        )
        cls.product_2 = cls.env["product.product"].create(
            {"name": "Test product 2", "detailed_type": "product"}
        )

    def _create_picking(self):
        return self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": self.env.ref("stock.picking_type_out").id,
            "location_id": self.src_location.id,
            "location_dest_id": self.dest_location.id,
        })

    def _create_move(self, picking, product, qty):
        return self.env["stock.move"].create({
            "name": "/",
            "picking_id": picking.id,
            "product_id": product.id,
            "product_uom_qty": qty,
            "product_uom": product.uom_id.id,
            "location_id": self.src_location.id,
            "location_dest_id": self.dest_location.id,
        })

    def _open_wizard(self, picking):
        return self.env["stock.split.picking"].with_context(
            active_ids=picking.ids, active_model="stock.picking"
        ).create({"mode": "counter"})

    def test_single_move_split_in_three(self):
        picking = self._create_picking()
        move = self._create_move(picking, self.product, 10)
        picking.action_confirm()

        wizard = self._open_wizard(picking)
        wizard.counter = 3
        self.assertTrue(wizard.valid_split_details)
        self.assertEqual(len(wizard.split_detail_ids), 3)
        # rounding-safe distribution: 3.34 + 3.33 + 3.33 == 10
        quantities = wizard.split_detail_ids.sorted("sequence").mapped(
            lambda d: sum(d.line_ids.mapped("quantity"))
        )
        self.assertAlmostEqual(sum(quantities), 10.0)

        wizard.action_apply()

        self.assertNotIn(picking.state, ("done", "cancel"))
        self.assertAlmostEqual(move.product_uom_qty, quantities[0])
        backorders = self.env["stock.picking"].search([("backorder_id", "=", picking.id)])
        self.assertEqual(len(backorders), 2)
        all_qtys = [move.product_uom_qty] + backorders.mapped("move_ids.product_uom_qty")
        self.assertAlmostEqual(sum(all_qtys), 10.0)

    def test_multi_move_split_in_two_proportional(self):
        picking = self._create_picking()
        move_1 = self._create_move(picking, self.product, 10)
        move_2 = self._create_move(picking, self.product_2, 7)
        picking.action_confirm()

        wizard = self._open_wizard(picking)
        wizard.counter = 2
        self.assertTrue(wizard.valid_split_details)

        wizard.action_apply()

        backorders = self.env["stock.picking"].search([("backorder_id", "=", picking.id)])
        self.assertEqual(len(backorders), 1)
        self.assertAlmostEqual(
            move_1.product_uom_qty + backorders.move_ids.filtered(
                lambda m: m.product_id == self.product
            ).product_uom_qty,
            10.0,
        )
        self.assertAlmostEqual(
            move_2.product_uom_qty + backorders.move_ids.filtered(
                lambda m: m.product_id == self.product_2
            ).product_uom_qty,
            7.0,
        )

    def test_manual_edit_of_quantities_is_kept(self):
        picking = self._create_picking()
        self._create_move(picking, self.product, 10)
        picking.action_confirm()

        wizard = self._open_wizard(picking)
        wizard.counter = 2
        details = wizard.split_detail_ids.sorted("sequence")
        details[0].line_ids.quantity = 4
        details[1].line_ids.quantity = 6
        self.assertTrue(wizard.valid_split_details)

        details[0].line_ids.quantity = 3
        self.assertFalse(wizard.valid_split_details)

    def test_counter_below_two_raises(self):
        picking = self._create_picking()
        self._create_move(picking, self.product, 10)
        picking.action_confirm()

        wizard = self._open_wizard(picking)
        wizard.counter = 1
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_multiple_pickings_selected_raises(self):
        picking_1 = self._create_picking()
        picking_2 = self._create_picking()
        self._create_move(picking_1, self.product, 10)
        self._create_move(picking_2, self.product, 5)
        (picking_1 + picking_2).action_confirm()

        wizard = self.env["stock.split.picking"].with_context(
            active_ids=(picking_1 + picking_2).ids, active_model="stock.picking"
        ).create({"mode": "counter"})
        self.assertEqual(wizard.counter, 0)
        wizard.counter = 2
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_draft_picking_raises(self):
        picking = self._create_picking()
        self._create_move(picking, self.product, 10)

        wizard = self._open_wizard(picking)
        wizard.counter = 2
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_responsible_and_date_propagated(self):
        picking = self._create_picking()
        self._create_move(picking, self.product, 10)
        picking.action_confirm()
        other_user = self.env["res.users"].create({
            "name": "Other user",
            "login": "other_user_split_picking_counter",
        })

        wizard = self._open_wizard(picking)
        wizard.counter = 2
        details = wizard.split_detail_ids.sorted("sequence")
        details[1].user_id = other_user

        wizard.action_apply()

        backorder = self.env["stock.picking"].search([("backorder_id", "=", picking.id)])
        self.assertEqual(backorder.user_id, other_user)
