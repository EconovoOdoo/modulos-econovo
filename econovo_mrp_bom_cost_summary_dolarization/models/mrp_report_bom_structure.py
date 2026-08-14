# -*- coding: utf-8 -*-
from odoo import api, fields, models

from odoo.addons.econovo_mrp_bom_cost_summary.report.report_cost_summary import (
    GROUP_SHOW_COST,
)


class ReportBomStructure(models.AbstractModel):
    """Extend BOM structure report to include direct USD costs.

    When both ``econovo_mrp_bom_cost_summary`` and ``gg_cost_dolarization``
    are installed, each component in the BOM tree gets two additional keys:

    - ``bom_cost_usd_direct``:  BOM Cost scaled to ``standard_price_usd``
      using the local-price ratio (``bom_cost × usd_price / ars_price``).
      For components without a local price, falls back to
      ``line_quantity × standard_price_usd``.

    - ``prod_cost_usd_direct``:  ``line_quantity × standard_price_usd``
      (direct catalogue cost in USD, independent of the exchange rate).

    These values are then picked up by the JS side
    (``bom_cost_dolarization.js``) to populate the new columns.

    Every injection is skipped for users outside the "Show Product Cost"
    group so no USD amount reaches them, not even in the raw RPC payload.
    """

    _inherit = 'report.mrp.report_bom_structure'

    @api.model
    def _can_show_costs_usd(self):
        return self.env.user.has_group(GROUP_SHOW_COST)

    @api.model
    def _get_component_data(
        self, parent_bom, parent_product, warehouse, bom_line,
        line_quantity, level, index, product_info, ignore_stock=False,
    ):
        res = super()._get_component_data(
            parent_bom, parent_product, warehouse, bom_line,
            line_quantity, level, index, product_info,
            ignore_stock=ignore_stock,
        )
        if not self._can_show_costs_usd():
            return res

        product = bom_line.product_id
        std_usd = getattr(product, 'standard_price_usd', 0.0) or 0.0
        std_ars = product.standard_price or 0.0

        # Product Cost USD direct: same formula as prod_cost but using
        # standard_price_usd instead of standard_price.
        prod_cost_usd_direct = line_quantity * std_usd

        # BOM Cost USD direct: scale the existing bom_cost by the
        # usd/ars price ratio so that nested sub-assembly costs are
        # also approximated in USD.  Falls back to the product cost
        # direct when no local price is set.
        bom_cost = res.get('bom_cost') or 0.0
        if std_ars > 0:
            bom_cost_usd_direct = bom_cost * (std_usd / std_ars)
        else:
            bom_cost_usd_direct = prod_cost_usd_direct

        res['prod_cost_usd_direct'] = prod_cost_usd_direct
        res['bom_cost_usd_direct'] = bom_cost_usd_direct
        return res

    @api.model
    def _get_byproducts_lines(self, product, bom, bom_quantity, level, total, index):
        """Add direct-USD cost fields to byproduct lines.

        Extends the base override from ``econovo_mrp_bom_cost_summary``
        (which adds category info) by computing:

        - ``prod_cost_usd_direct``: quantity × product.standard_price_usd
        - ``bom_cost_usd_direct``:  bom_cost × (usd_price / ars_price),
          falling back to prod_cost_usd_direct when no ARS price is set.
        """
        byproducts, byproduct_cost_portion = super()._get_byproducts_lines(
            product, bom, bom_quantity, level, total, index,
        )
        if not self._can_show_costs_usd():
            return byproducts, byproduct_cost_portion
        for bp in byproducts:
            byproduct_obj = self.env['mrp.bom.byproduct'].browse(bp['id'])
            prod = byproduct_obj.product_id
            std_usd = getattr(prod, 'standard_price_usd', 0.0) or 0.0
            std_ars = prod.standard_price or 0.0

            quantity = bp.get('quantity', 0.0) or 0.0
            prod_cost_usd_direct = quantity * std_usd

            bom_cost = bp.get('bom_cost', 0.0) or 0.0
            if std_ars > 0:
                bom_cost_usd_direct = bom_cost * (std_usd / std_ars)
            else:
                bom_cost_usd_direct = prod_cost_usd_direct

            bp['prod_cost_usd_direct'] = prod_cost_usd_direct
            bp['bom_cost_usd_direct'] = bom_cost_usd_direct
        return byproducts, byproduct_cost_portion

    @api.model
    def _get_operation_line(self, product, bom, qty, level, index):
        """Inject ``bom_cost_usd_direct`` into every operation line.

        Mirrors the full ARS formula from ``_get_operation_cost``
        (base + mrp_workorder enterprise override):

            bom_cost_usd_direct =
                (duration / 60) × costs_hour_usd
              + (duration / 60) × employee_costs_hour_usd × employee_ratio

        ``costs_hour_usd`` and ``employee_costs_hour_usd`` are the
        direct-USD fields added to ``mrp.workcenter`` by this bridge module.
        ``employee_ratio`` is defined by ``mrp_workorder`` (enterprise);
        getattr guards are used so the formula degrades gracefully when
        mrp_workorder is not installed.
        """
        operations = super()._get_operation_line(product, bom, qty, level, index)
        if not self._can_show_costs_usd():
            return operations
        bom_ops = bom.operation_ids.filtered(
            lambda o: not product or not o._skip_operation_line(product)
        )
        for i, op_data in enumerate(operations):
            if i < len(bom_ops):
                op = bom_ops[i]
                wc = op.workcenter_id
                duration = op_data.get('quantity', 0.0) or 0.0  # minutes
                costs_hour_usd = getattr(wc, 'costs_hour_usd', 0.0) or 0.0
                employee_costs_hour_usd = (
                    getattr(wc, 'employee_costs_hour_usd', 0.0) or 0.0
                )
                employee_ratio = getattr(op, 'employee_ratio', 0.0) or 0.0
                hours = duration / 60.0
                op_data['bom_cost_usd_direct'] = (
                    hours * costs_hour_usd
                    + hours * employee_costs_hour_usd * employee_ratio
                )
            else:
                op_data['bom_cost_usd_direct'] = 0.0
        return operations

    @api.model
    def _get_subcontracting_line(self, bom, seller, level, bom_quantity):
        """Inject ``bom_cost_usd_direct`` / ``prod_cost_usd_direct`` into the
        subcontracting node.

        The direct USD cost is always derived from the vendor's actual price
        converted to USD using Odoo's standard currency conversion.  When the
        vendor already prices in USD the conversion is 1:1 (no rounding loss).
        When the vendor prices in ARS or any other currency the exchange rate
        is applied, which is the most honest representation of what the
        subcontracted item costs in USD.
        """
        res = super()._get_subcontracting_line(bom, seller, level, bom_quantity)
        if not self._can_show_costs_usd():
            return res
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        if not usd_currency:
            res['bom_cost_usd_direct'] = 0.0
            res['prod_cost_usd_direct'] = 0.0
            return res
        ratio_uom_seller = seller.product_uom.ratio / bom.product_uom_id.ratio
        price_in_seller_currency = seller.price / ratio_uom_seller * bom_quantity
        company = bom.company_id or self.env.company
        bom_cost_usd_direct = seller.currency_id._convert(
            price_in_seller_currency,
            usd_currency,
            company,
            fields.Date.today(),
        )
        res['bom_cost_usd_direct'] = bom_cost_usd_direct
        res['prod_cost_usd_direct'] = bom_cost_usd_direct
        return res


class ReportEconovoBomCostSummaryDirectUsd(models.AbstractModel):
    """Inject the direct-USD aggregation into the cost summary server-side.

    The base module computes the cost summary once on the server
    (``report.econovo_mrp_bom_cost_summary.report_cost_summary
    ._compute_cost_summary``) and the UI, PDF and Excel all consume it.  This
    override augments that single result with the ``*_usd_direct`` values
    (built from ``product.standard_price_usd`` / ``workcenter.costs_hour_usd``,
    injected into the raw tree by the overrides above) so every surface shows
    the same direct-USD figures instead of the UI recomputing them in JS.

    Python port of ``augmentWithDirectUsd`` and helpers in
    ``bom_cost_dolarization.js``.
    """

    _inherit = 'report.econovo_mrp_bom_cost_summary.report_cost_summary'

    @api.model
    def _compute_cost_summary(self, data, secondary_currency):
        summary = super()._compute_cost_summary(data, secondary_currency)
        # ``show_costs`` is False for users outside the "Show Product Cost"
        # group; the base module already stripped every amount, so adding the
        # direct-USD figures back would defeat that restriction.
        if summary and summary.get("show_costs"):
            self._augment_with_direct_usd(summary, data)
        return summary

    # ------------------------------------------------------------------
    # Components
    # ------------------------------------------------------------------
    @api.model
    def _collect_direct_usd(self, node, direct_map, skip_prod_cost=False):
        """Gather ``*_usd_direct`` component values from the raw tree into
        ``direct_map[cat_id][prod_id][parent_prod_id] = {bom, prod}``."""
        for comp in node.get("components", []):
            cat_id = comp.get("categ_id") or 0
            prod_id = comp.get("product_id")
            parent_prod_id = node.get("product_id")
            entry = direct_map.setdefault(cat_id, {}).setdefault(
                prod_id, {},
            ).setdefault(parent_prod_id, {"bom": 0.0, "prod": 0.0})
            if comp.get("type") == "bom" and comp.get("components"):
                if not skip_prod_cost:
                    entry["prod"] += comp.get("prod_cost_usd_direct") or 0.0
                self._collect_direct_usd(comp, direct_map, True)
            else:
                entry["bom"] += comp.get("bom_cost_usd_direct") or 0.0
                if not skip_prod_cost:
                    entry["prod"] += comp.get("prod_cost_usd_direct") or 0.0

    @api.model
    def _inject_bubble_direct_usd(self, nodes, direct_map):
        """Inject direct-USD totals into a category tree (components or
        byproducts), bubbling usages -> products -> categories."""
        for node in nodes:
            self._inject_bubble_direct_usd(node.get("children", []), direct_map)
            node_total = 0.0
            node_prod_total = 0.0
            for child in node.get("children", []):
                node_total += child.get("total_usd_direct") or 0.0
                node_prod_total += child.get("prod_cost_total_usd_direct") or 0.0
            cat_direct = direct_map.get(node["id"])
            for prod in node.get("products", []):
                prod_total = 0.0
                prod_prod_total = 0.0
                prod_direct = (
                    cat_direct.get(prod["product_id"]) if cat_direct else None
                )
                for usage in prod.get("usages", []):
                    parent_id = usage.get("parent_product_id")
                    usage_direct = (
                        prod_direct.get(parent_id) if prod_direct else None
                    )
                    usage["total_usd_direct"] = (
                        usage_direct["bom"] if usage_direct else 0.0
                    )
                    usage["prod_cost_usd_direct"] = (
                        usage_direct["prod"] if usage_direct else 0.0
                    )
                    prod_total += usage["total_usd_direct"]
                    prod_prod_total += usage["prod_cost_usd_direct"]
                prod["total_usd_direct"] = prod_total
                prod["prod_cost_total_usd_direct"] = prod_prod_total
                node_total += prod_total
                node_prod_total += prod_prod_total
            node["total_usd_direct"] = node_total
            node["prod_cost_total_usd_direct"] = node_prod_total

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------
    @api.model
    def _collect_direct_usd_ops(self, node, ops_direct_map):
        """Gather operation ``bom_cost_usd_direct`` into
        ``ops_direct_map[wc_id][link_id][parent_prod_id] = sum``."""
        for op in node.get("operations", []):
            wc_id = op.get("workcenter_id") or 0
            link_id = op.get("link_id") or 0
            parent_prod_id = node.get("product_id")
            link_map = ops_direct_map.setdefault(wc_id, {}).setdefault(
                link_id, {},
            )
            link_map[parent_prod_id] = (
                link_map.get(parent_prod_id, 0.0)
                + (op.get("bom_cost_usd_direct") or 0.0)
            )
        for comp in node.get("components", []):
            if comp.get("type") == "bom" and comp.get("components"):
                self._collect_direct_usd_ops(comp, ops_direct_map)

    @api.model
    def _inject_bubble_direct_usd_ops(self, workcenters, ops_direct_map):
        for wc in workcenters:
            wc_total = 0.0
            for item in wc.get("items", []):
                wc_map = ops_direct_map.get(wc["id"])
                link_map = wc_map.get(item.get("link_id")) if wc_map else None
                usd_direct = (
                    link_map.get(item.get("parent_product_id"), 0.0)
                    if link_map else 0.0
                )
                item["total_usd_direct"] = usd_direct
                wc_total += usd_direct
            wc["total_usd_direct"] = wc_total

    # ------------------------------------------------------------------
    # Byproducts
    # ------------------------------------------------------------------
    @api.model
    def _collect_direct_usd_byproducts(self, node, bp_direct_map):
        for bp in node.get("byproducts", []):
            cat_id = bp.get("categ_id") or 0
            prod_id = bp.get("link_id") or bp.get("id")
            parent_prod_id = node.get("product_id")
            entry = bp_direct_map.setdefault(cat_id, {}).setdefault(
                prod_id, {},
            ).setdefault(parent_prod_id, {"bom": 0.0, "prod": 0.0})
            entry["bom"] += bp.get("bom_cost_usd_direct") or 0.0
            entry["prod"] += bp.get("prod_cost_usd_direct") or 0.0
        for comp in node.get("components", []):
            if comp.get("type") == "bom" and comp.get("components"):
                self._collect_direct_usd_byproducts(comp, bp_direct_map)

    # ------------------------------------------------------------------
    # Subcontracting
    # ------------------------------------------------------------------
    @api.model
    def _collect_direct_usd_subcontracting(self, node, sc_direct_map):
        sc = node.get("subcontracting")
        if sc:
            vendor_id = sc.get("partner_id") or 0
            product_id = node.get("product_id")
            key = "%s:%s" % (vendor_id, product_id)
            entry = sc_direct_map.setdefault(
                key, {"total": 0.0, "prod_cost_total": 0.0},
            )
            entry["total"] += sc.get("bom_cost_usd_direct") or 0.0
            entry["prod_cost_total"] += sc.get("prod_cost_usd_direct") or 0.0
        for comp in node.get("components", []):
            if comp.get("type") == "bom":
                self._collect_direct_usd_subcontracting(comp, sc_direct_map)

    @api.model
    def _inject_direct_usd_subcontracting(self, subcontracting, sc_direct_map):
        for vendor in subcontracting:
            vendor["total_usd_direct"] = 0.0
            vendor["prod_cost_total_usd_direct"] = 0.0
            for item in vendor.get("items", []):
                key = "%s:%s" % (vendor["id"], item.get("product_id"))
                entry = sc_direct_map.get(
                    key, {"total": 0.0, "prod_cost_total": 0.0},
                )
                item["total_usd_direct"] = entry["total"]
                item["prod_cost_usd_direct"] = entry["prod_cost_total"]
                vendor["total_usd_direct"] += entry["total"]
                vendor["prod_cost_total_usd_direct"] += entry["prod_cost_total"]

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    @api.model
    def _augment_with_direct_usd(self, summary, data):
        totals = summary["totals"]

        # Components
        direct_map = {}
        self._collect_direct_usd(data, direct_map)
        self._inject_bubble_direct_usd(summary.get("categories", []), direct_map)
        total_comp = sum(
            c.get("total_usd_direct") or 0.0
            for c in summary.get("categories", [])
        )
        total_prod_cost = sum(
            c.get("prod_cost_total_usd_direct") or 0.0
            for c in summary.get("categories", [])
        )
        totals["components_usd_direct"] = total_comp
        totals["prod_cost_usd_direct"] = total_prod_cost

        # Operations
        ops_direct_map = {}
        self._collect_direct_usd_ops(data, ops_direct_map)
        self._inject_bubble_direct_usd_ops(
            summary.get("workcenters", []), ops_direct_map,
        )
        total_ops = sum(
            wc.get("total_usd_direct") or 0.0
            for wc in summary.get("workcenters", [])
        )
        totals["operations_usd_direct"] = total_ops

        # Subcontracting
        sc_direct_map = {}
        self._collect_direct_usd_subcontracting(data, sc_direct_map)
        self._inject_direct_usd_subcontracting(
            summary.get("subcontracting", []), sc_direct_map,
        )
        total_sc = sum(
            v.get("total_usd_direct") or 0.0
            for v in summary.get("subcontracting", [])
        )
        total_sc_prod = sum(
            v.get("prod_cost_total_usd_direct") or 0.0
            for v in summary.get("subcontracting", [])
        )
        totals["subcontracting_usd_direct"] = total_sc
        totals["subcontracting_prod_cost_usd_direct"] = total_sc_prod

        # Grand totals (gross)
        totals["total_usd_direct"] = total_comp + total_ops + total_sc
        totals["total_prod_usd_direct"] = total_prod_cost

        # Byproducts (reuse the component tree injector)
        bp_direct_map = {}
        self._collect_direct_usd_byproducts(data, bp_direct_map)
        self._inject_bubble_direct_usd(
            summary.get("byproductCategories", []), bp_direct_map,
        )
        total_bp = sum(
            c.get("total_usd_direct") or 0.0
            for c in summary.get("byproductCategories", [])
        )
        total_bp_prod = sum(
            c.get("prod_cost_total_usd_direct") or 0.0
            for c in summary.get("byproductCategories", [])
        )
        totals["byproducts_usd_direct"] = total_bp
        totals["byproducts_prod_cost_usd_direct"] = total_bp_prod
        totals["net_bom_usd_direct"] = totals["total_usd_direct"] - total_bp
        totals["net_prod_usd_direct"] = total_prod_cost - total_bp_prod

