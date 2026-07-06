# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestBomCostSummarySingleSource(TransactionCase):
    """Verify the cost summary is computed once server-side and consumed
    identically by the interactive UI (get_html), the PDF and the Excel export.

    A two-level BOM is used so the native Product Cost semantics (root
    standard_price for the grand total, direct-component standard_price for the
    category breakdown) can be asserted against the rolled-up BOM Cost.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env["report.mrp.report_bom_structure"]
        cls.summary_model = cls.env[
            "report.econovo_mrp_bom_cost_summary.report_cost_summary"
        ]
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")

        # Raw material C, sub-assembly B, finished product A.
        cls.product_c = cls.env["product.product"].create({
            "name": "Test Raw Material C",
            "type": "product",
            "standard_price": 100.0,
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
        })
        cls.product_b = cls.env["product.product"].create({
            "name": "Test Sub-Assembly B",
            "type": "product",
            "standard_price": 500.0,
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
        })
        cls.product_a = cls.env["product.product"].create({
            "name": "Test Finished Product A",
            "type": "product",
            "standard_price": 2000.0,
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
        })

        # BOM B: 1 x B <- 2 x C
        cls.bom_b = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.product_b.product_tmpl_id.id,
            "product_qty": 1.0,
            "product_uom_id": cls.uom_unit.id,
            "type": "normal",
            "bom_line_ids": [(0, 0, {
                "product_id": cls.product_c.id,
                "product_qty": 2.0,
            })],
        })
        # BOM A: 1 x A <- 3 x B
        cls.bom_a = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.product_a.product_tmpl_id.id,
            "product_qty": 1.0,
            "product_uom_id": cls.uom_unit.id,
            "type": "normal",
            "bom_line_ids": [(0, 0, {
                "product_id": cls.product_b.id,
                "product_qty": 3.0,
            })],
        })

    def _get_summary_from_ui_path(self):
        """Mirror what the OWL widget receives: the summary attached to the
        lines tree by ReportBomStructure._get_report_data / get_html."""
        raw = self.report.get_html(bom_id=self.bom_a.id, searchQty=1)
        return raw["lines"].get("cost_summary")

    def test_get_html_attaches_cost_summary(self):
        summary = self._get_summary_from_ui_path()
        self.assertTrue(
            summary,
            "get_html must attach a computed cost_summary to the lines tree "
            "so the UI consumes the server value instead of recomputing it.",
        )

    def test_ui_and_report_paths_are_identical(self):
        """The interactive UI and the PDF/Excel exports must derive from the
        exact same server computation (single source of truth)."""
        ui_summary = self._get_summary_from_ui_path()
        raw = self.report.get_html(bom_id=self.bom_a.id, searchQty=1)
        report_summary = self.summary_model._compute_cost_summary(
            raw["lines"], raw.get("secondary_currency", False),
        )
        self.assertEqual(
            ui_summary["totals"], report_summary["totals"],
            "UI totals and PDF/Excel totals must match exactly.",
        )

    def test_native_product_cost_semantics(self):
        """Grand-total Product Cost is the finished product's own standard
        price (native Odoo), while BOM Cost is the rolled-up material cost."""
        totals = self._get_summary_from_ui_path()["totals"]
        # BOM Cost (gross) = rolled-up leaf materials: 3 x (2 x 100) = 600.
        self.assertAlmostEqual(totals["total"], 600.0, places=2)
        # Product Cost (grand total) = A.standard_price x qty = 2000.
        self.assertAlmostEqual(totals["total_prod"], 2000.0, places=2)
        # Components subtotal (BOM Cost) rolls up the leaf materials.
        self.assertAlmostEqual(totals["components"], 600.0, places=2)
        # Product Cost subtotal uses direct-component standard prices: the
        # sub-assembly B contributes 3 x 500 = 1500; its internal leaves add 0.
        self.assertAlmostEqual(totals["prod_cost"], 1500.0, places=2)

    def test_summary_uses_camelcase_byproduct_key(self):
        """The unified output shape exposes ``byproductCategories`` so the
        OWL component, the PDF template and the Excel export all agree."""
        summary = self._get_summary_from_ui_path()
        self.assertIn("byproductCategories", summary)
