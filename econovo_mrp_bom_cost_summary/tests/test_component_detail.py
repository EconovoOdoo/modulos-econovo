# -*- coding: utf-8 -*-
"""Verify the "Components Detail" smart button opens a flat, native list of
component usages sourced from the exact same cost_summary as the Excel
export, and respects the same "Show Product Cost" gating."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestBomComponentDetail(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.group_show_cost = cls.env.ref(
            "hide_product_price_cost."
            "hide_product_price_cost_group_user_show_product_cost"
        )
        cls.env.user.groups_id |= cls.group_show_cost

        cls.comp = cls.env["product.product"].create({
            "name": "Component Detail Component",
            "type": "product",
            "standard_price": 100.0,
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
        })
        cls.finished = cls.env["product.product"].create({
            "name": "Component Detail Finished",
            "type": "product",
            "standard_price": 500.0,
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
        })
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.finished.product_tmpl_id.id,
            "product_qty": 1.0,
            "product_uom_id": cls.uom_unit.id,
            "type": "normal",
            "bom_line_ids": [(0, 0, {
                "product_id": cls.comp.id,
                "product_qty": 2.0,
            })],
        })

    def _open(self):
        action = self.bom.action_open_component_detail()
        self.assertEqual(action["res_model"], "mrp.bom.component.line")
        return self.env["mrp.bom.component.line"].search(action["domain"])

    def test_creates_one_line_per_usage(self):
        lines = self._open()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.product_id, self.comp)
        self.assertEqual(lines.parent_product_id, self.finished)
        self.assertAlmostEqual(lines.quantity, 2.0, places=2)

    def test_costs_populated_with_group(self):
        lines = self._open()
        # 2 x component.standard_price (100) = 200.
        self.assertAlmostEqual(lines.bom_cost, 200.0, places=2)
        self.assertAlmostEqual(lines.percentage, 100.0, places=1)

    def test_costs_zeroed_without_group(self):
        self.env.user.groups_id -= self.group_show_cost
        lines = self._open()
        self.assertEqual(lines.bom_cost, 0.0)
        self.assertEqual(lines.prod_cost, 0.0)
        # Structure survives: quantity/percentage are not cost amounts.
        self.assertAlmostEqual(lines.quantity, 2.0, places=2)
        self.assertAlmostEqual(lines.percentage, 100.0, places=1)

    def test_reopening_creates_an_independent_fresh_batch(self):
        """Each click creates a new batch; the action's own domain scopes to
        it, so stale batches never leak into what the user sees. Transient
        records from previous opens are left for Odoo's own vacuum, by
        design - no manual cleanup needed."""
        first = self._open()
        second = self._open()
        self.assertNotEqual(first.ids, second.ids)
        self.assertEqual(len(second), 1)
