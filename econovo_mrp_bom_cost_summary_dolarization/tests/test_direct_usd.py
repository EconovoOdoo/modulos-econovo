# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDolarizationDirectUsd(TransactionCase):
    """Verify the direct-USD aggregation is computed server-side and consumed
    identically by the UI (get_html), the PDF and the Excel export.

    Before this module was made server-side, the direct USD was only computed
    in JS for the interactive view, so the Excel/PDF exports showed a different
    (exchange-rate) USD figure.  These tests assert the single-source result.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env["report.mrp.report_bom_structure"]
        cls.summary_model = cls.env[
            "report.econovo_mrp_bom_cost_summary.report_cost_summary"
        ]
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.group_show_cost = cls.env.ref(
            "hide_product_price_cost."
            "hide_product_price_cost_group_user_show_product_cost"
        )
        cls.env.user.groups_id |= cls.group_show_cost

        cls.comp = cls.env["product.product"].create({
            "name": "Direct USD Component",
            "type": "product",
            "standard_price": 1000.0,
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
        })
        # Direct USD catalogue price (independent of the exchange rate).
        cls.comp.standard_price_usd = 10.0
        cls.finished = cls.env["product.product"].create({
            "name": "Direct USD Finished",
            "type": "product",
            "standard_price": 5000.0,
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
        })
        cls.finished.standard_price_usd = 50.0
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

    def _summary(self):
        raw = self.report.get_html(bom_id=self.bom.id, searchQty=1)
        return raw["lines"].get("cost_summary")

    def test_direct_usd_injected_server_side(self):
        summary = self._summary()
        self.assertTrue(summary)
        totals = summary["totals"]
        # 2 units x standard_price_usd (10) = 20 USD of components.
        self.assertAlmostEqual(totals["components_usd_direct"], 20.0, places=2)
        # No operations / subcontracting => grand total = components only.
        self.assertAlmostEqual(totals["total_usd_direct"], 20.0, places=2)

    def test_prefer_direct_usd_overwrites_rate(self):
        summary = self._summary()
        self.summary_model._prefer_direct_usd(summary)
        totals = summary["totals"]
        # After the transform the exchange-rate USD fields carry the direct
        # values, so PDF/Excel (which read ``*_usd``) match the UI.
        self.assertEqual(totals["total_usd"], totals["total_usd_direct"])
        self.assertEqual(
            totals["components_usd"], totals["components_usd_direct"],
        )

    def test_direct_usd_absent_without_group(self):
        """No direct-USD value may reach a user outside "Show Product Cost",
        neither in the summary nor in the raw tree."""
        self.env.user.groups_id -= self.group_show_cost

        raw = self.report.get_html(bom_id=self.bom.id, searchQty=1)
        self.assertNotIn(
            "bom_cost_usd_direct", raw["lines"]["components"][0],
        )
        self.assertNotIn(
            "total_usd_direct", raw["lines"]["cost_summary"]["totals"],
        )
