# -*- coding: utf-8 -*-
# pylint: disable=missing-function-docstring,too-many-locals

from odoo import api, models, _


class ReportEconovoBomCostSummary(models.AbstractModel):
    _name = "report.econovo_mrp_bom_cost_summary.report_cost_summary"
    _description = "BOM Cost Summary PDF Report"

    # ------------------------------------------------------------------
    # Report entry point
    # ------------------------------------------------------------------

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Called by Odoo's report engine when generating the PDF.

        URL query parameters forwarded via ``data``:
          - quantity    : float   - BOM quantity (defaults to bom.product_qty)
          - variant     : int str - product.product ID (optional)
          - warehouse_id: int str - stock.warehouse ID (optional)
          - costs       : str     - "false" to hide cost columns
          - operations  : str     - "false" to hide operations section
          - lead_times  : str     - "false" to hide lead-time column
          - all_variants: str     - "1" to print every variant
        """
        data = data or {}
        docs = []

        bom_report = self.env["report.mrp.report_bom_structure"]
        if data.get("warehouse_id"):
            bom_report = bom_report.with_context(
                warehouse=int(data.get("warehouse_id"))
            )

        for bom_id in docids:
            bom = self.env["mrp.bom"].browse(bom_id)
            if not bom.exists():
                continue

            quantity = float(data.get("quantity") or bom.product_qty or 1)
            show_costs = data.get("costs") != "false"
            show_operations = data.get("operations") != "false"
            show_lead_times = data.get("lead_times") != "false"

            if data.get("all_variants"):
                variants = (
                    bom.product_tmpl_id.product_variant_ids.ids or [False]
                )
            elif data.get("variant"):
                variants = [int(data.get("variant"))]
            else:
                variants = [False]

            for variant_id in variants:
                raw = bom_report.get_html(
                    bom_id=bom.id,
                    searchQty=quantity,
                    searchVariant=variant_id,
                )
                bom_lines = raw.get("lines", {})
                secondary = raw.get("secondary_currency", False)
                cost_summary = self._compute_cost_summary(
                    bom_lines, secondary
                )
                docs.append(
                    {
                        "bom": bom,
                        "bom_lines": bom_lines,
                        "cost_summary": cost_summary,
                        "currency": bom.company_id.currency_id,
                        "secondary_currency": secondary,
                        "quantity": quantity,
                        "show_costs": show_costs,
                        "show_operations": show_operations,
                        "show_lead_times": show_lead_times,
                    }
                )

        return {
            "doc_ids": docids,
            "doc_model": "mrp.bom",
            "docs": docs,
        }

    # ------------------------------------------------------------------
    # Aggregation helpers (Python port of bom_cost_summary_utils.js)
    # ------------------------------------------------------------------

    @api.model
    def _compute_cost_summary(self, data, secondary_currency):
        """
        Aggregates the BOM data into the cost summary structure consumed
        by the PDF template.  Mirrors ``computeCostSummary`` in JS.

        :param dict data:               BOM root node (result of get_html["lines"])
        :param dict|bool secondary_currency: USD rate info or False
        :returns dict|bool:             Cost summary or False if empty
        """
        category_map = {}
        workcenter_map = {}
        byproduct_category_map = {}
        subcontracting_map = {}
        self._collect_costs(
            data, category_map, workcenter_map,
            byproduct_category_map=byproduct_category_map,
            subcontracting_map=subcontracting_map,
        )

        rate = secondary_currency.get("rate", 0) if secondary_currency else 0

        categories = self._build_category_tree(category_map)
        workcenters = sorted(
            workcenter_map.values(), key=lambda w: w["total"], reverse=True
        )
        byproduct_categories = self._build_category_tree(byproduct_category_map)
        subcontracting = sorted(
            subcontracting_map.values(), key=lambda v: v["total"], reverse=True
        )

        if not categories and not workcenters and not byproduct_categories and not subcontracting:
            return False

        total_components = sum(c["total"] for c in categories)
        total_prod_cost = sum(c["prod_cost_total"] for c in categories)
        total_operations = sum(w["total"] for w in workcenters)
        total_duration = sum(w["total_duration"] for w in workcenters)
        total_byproducts = sum(c["total"] for c in byproduct_categories)
        total_byproducts_prod_cost = sum(
            c["prod_cost_total"] for c in byproduct_categories
        )
        total_subcontracting = sum(v["total"] for v in subcontracting)
        total_subcontracting_prod_cost = sum(
            v["prod_cost_total"] for v in subcontracting
        )
        # Gross BoM = all costs before byproduct deduction.
        total_bom = total_components + total_operations + total_subcontracting
        net_bom = total_bom - total_byproducts
        total_prod = total_prod_cost + total_operations
        net_prod = total_prod - total_byproducts_prod_cost

        self._enrich_category_tree(categories, rate, total_components)
        # bom_cost-based % for byproducts (0 when cost_share=0).
        self._enrich_category_tree(byproduct_categories, rate, total_byproducts)
        # prod_cost-based % (always meaningful, independent of cost_share).
        self._enrich_byproduct_prod_cost_pct(byproduct_categories, total_byproducts_prod_cost)

        for wc in workcenters:
            wc["percentage"] = (
                wc["total"] / total_operations * 100 if total_operations else 0
            )
            wc["total_usd"] = wc["total"] * rate if rate else False
            for item in wc["items"]:
                item["percentage"] = (
                    item["total"] / total_operations * 100
                    if total_operations
                    else 0
                )
                item["total_usd"] = item["total"] * rate if rate else False

        for vendor in subcontracting:
            vendor["percentage"] = (
                vendor["total"] / total_subcontracting * 100
                if total_subcontracting else 0
            )
            vendor["total_usd"] = vendor["total"] * rate if rate else False
            vendor["prod_cost_total_usd"] = (
                vendor["prod_cost_total"] * rate if rate else False
            )
            for item in vendor["items"]:
                item["percentage"] = (
                    item["total"] / total_subcontracting * 100
                    if total_subcontracting else 0
                )
                item["total_usd"] = item["total"] * rate if rate else False
                item["prod_cost_usd"] = item["prod_cost"] * rate if rate else False

        return {
            "categories": categories,
            "workcenters": workcenters,
            "byproduct_categories": byproduct_categories,
            "subcontracting": subcontracting,
            "totals": {
                "components": total_components,
                "components_usd": total_components * rate if rate else False,
                "prod_cost": total_prod_cost,
                "prod_cost_usd": total_prod_cost * rate if rate else False,
                "operations": total_operations,
                "operations_usd": total_operations * rate if rate else False,
                "operations_duration": total_duration,
                "subcontracting": total_subcontracting,
                "subcontracting_usd": total_subcontracting * rate if rate else False,
                "subcontracting_prod_cost": total_subcontracting_prod_cost,
                "subcontracting_prod_cost_usd": (
                    total_subcontracting_prod_cost * rate if rate else False
                ),
                "byproducts": total_byproducts,
                "byproducts_usd": total_byproducts * rate if rate else False,
                "byproducts_prod_cost": total_byproducts_prod_cost,
                "byproducts_prod_cost_usd": (
                    total_byproducts_prod_cost * rate if rate else False
                ),
                "total": total_bom,
                "total_usd": total_bom * rate if rate else False,
                "total_prod": total_prod,
                "total_prod_usd": total_prod * rate if rate else False,
                "net_bom": net_bom,
                "net_bom_usd": net_bom * rate if rate else False,
                "net_prod": net_prod,
                "net_prod_usd": net_prod * rate if rate else False,
            },
            "currency_id": data.get("currency_id"),
        }

    @api.model
    def _collect_costs(
        self, node, category_map, workcenter_map, ancestor_cost_share=1.0,
        byproduct_category_map=None, subcontracting_map=None,
    ):
        """
        Recursively walk the BOM tree collecting leaf component, operation,
        byproduct, and subcontracting costs.
        Mirrors ``collectCosts`` in bom_cost_summary_utils.js.
        """
        parent_name = node.get("name", "")
        parent_product_id = node.get("product_id")
        parent_route_info = {
            "route_name": node.get("route_name", ""),
            "route_detail": node.get("route_detail", ""),
            "route_type": node.get("route_type", ""),
            "bom_id": node.get("bom_id", False),
        }

        node_cost_share = node.get("cost_share")
        if node_cost_share is None:
            node_cost_share = 1.0
        effective_cost_share = ancestor_cost_share * node_cost_share

        # Collect operations at this BOM level
        for op in node.get("operations", []):
            wc_id = op.get("workcenter_id") or 0
            wc_name = op.get("workcenter_name") or _("Unknown")
            if wc_id not in workcenter_map:
                workcenter_map[wc_id] = {
                    "id": wc_id,
                    "name": wc_name,
                    "total": 0.0,
                    "total_duration": 0.0,
                    "items": [],
                }
            adjusted_cost = (op.get("bom_cost") or 0.0) * effective_cost_share
            op_duration = op.get("quantity") or 0.0
            workcenter_map[wc_id]["total"] += adjusted_cost
            workcenter_map[wc_id]["total_duration"] += op_duration
            workcenter_map[wc_id]["items"].append(
                {
                    "name": op.get("operation_name") or op.get("name", ""),
                    "link_id": op.get("link_id", False),
                    "duration": op_duration,
                    "total": adjusted_cost,
                    "parent_name": parent_name,
                    "parent_product_id": parent_product_id,
                    "lead_time": node.get("lead_time", False),
                    "route_name": node.get("route_name", ""),
                    "route_detail": node.get("route_detail", ""),
                    "route_type": node.get("route_type", ""),
                    "bom_id": node.get("bom_id", False),
                    "parent_qty": node.get("quantity") or 1,
                }
            )

        # Collect subcontracting cost for this BOM level.
        # node['subcontracting'] is injected by mrp_subcontracting when
        # bom.type == 'subcontract'.  Keys: name (vendor), partner_id,
        # quantity, uom, bom_cost, prod_cost, level.
        if subcontracting_map is not None and node.get("subcontracting"):
            sc = node["subcontracting"]
            vendor_id = sc.get("partner_id") or 0
            vendor_name = sc.get("name") or _("Unknown Vendor")
            if vendor_id not in subcontracting_map:
                subcontracting_map[vendor_id] = {
                    "id": vendor_id,
                    "name": vendor_name,
                    "total": 0.0,
                    "prod_cost_total": 0.0,
                    "items": [],
                }
            sc_cost = (sc.get("bom_cost") or 0.0)
            sc_prod_cost = (sc.get("prod_cost") or 0.0)
            subcontracting_map[vendor_id]["total"] += sc_cost
            subcontracting_map[vendor_id]["prod_cost_total"] += sc_prod_cost
            subcontracting_map[vendor_id]["items"].append({
                "product_id": node.get("product_id"),
                "product_name": node.get("name", ""),
                "quantity": sc.get("quantity") or 0.0,
                "uom_name": sc.get("uom") or node.get("uom_name", ""),
                "total": sc_cost,
                "prod_cost": sc_prod_cost,
                "partner_id": vendor_id,
            })

        # Process byproducts at this BOM level.
        # Scaled only by ancestor_cost_share (not effective_cost_share) because
        # the byproduct's own cost_share is already embedded in bp["bom_cost"].
        if byproduct_category_map is not None:
            for bp in node.get("byproducts", []):
                cat_id = bp.get("categ_id") or 0
                cat_name = bp.get("categ_name") or _("Uncategorized")
                if cat_id not in byproduct_category_map:
                    byproduct_category_map[cat_id] = {
                        "id": cat_id,
                        "name": cat_name,
                        "total": 0.0,
                        "prod_cost_total": 0.0,
                        "products": {},
                        "ancestors": bp.get("categ_ancestors")
                        or [{"id": cat_id, "name": cat_name}],
                    }
                adjusted_cost = (
                    (bp.get("bom_cost") or 0.0) * ancestor_cost_share
                )
                adjusted_prod_cost = (
                    (bp.get("prod_cost") or 0.0) * ancestor_cost_share
                )
                cat = byproduct_category_map[cat_id]
                cat["total"] += adjusted_cost
                cat["prod_cost_total"] += adjusted_prod_cost

                prod_key = bp.get("link_id") or bp.get("id")
                if prod_key not in cat["products"]:
                    cat["products"][prod_key] = {
                        "product_id": prod_key,
                        "name": bp.get("name", ""),
                        "link_id": bp.get("link_id") or False,
                        "link_model": bp.get("link_model", "product.product"),
                        "total": 0.0,
                        "prod_cost_total": 0.0,
                        "usages": [],
                    }
                bp_product = cat["products"][prod_key]
                bp_product["total"] += adjusted_cost
                bp_product["prod_cost_total"] += adjusted_prod_cost

                existing_usage = next(
                    (
                        u
                        for u in bp_product["usages"]
                        if u["parent_product_id"] == parent_product_id
                    ),
                    None,
                )
                if existing_usage:
                    existing_usage["quantity"] += bp.get("quantity") or 0.0
                    existing_usage["total"] += adjusted_cost
                    existing_usage["prod_cost"] += adjusted_prod_cost
                else:
                    bp_product["usages"].append(
                        {
                            "parent_product_id": parent_product_id,
                            "parent_name": parent_name,
                            "quantity": bp.get("quantity") or 0.0,
                            "uom_name": bp.get("uom_name", ""),
                            "total": adjusted_cost,
                            "prod_cost": adjusted_prod_cost,
                        }
                    )

        # Process components
        for comp in node.get("components", []):
            if comp.get("type") == "bom" and comp.get("components"):
                # Sub-BOM: recurse
                self._collect_costs(
                    comp, category_map, workcenter_map, effective_cost_share,
                    byproduct_category_map=byproduct_category_map,
                    subcontracting_map=subcontracting_map,
                )
            else:
                # Leaf component
                cat_id = comp.get("categ_id") or 0
                cat_name = comp.get("categ_name") or _("Uncategorized")
                if cat_id not in category_map:
                    category_map[cat_id] = {
                        "id": cat_id,
                        "name": cat_name,
                        "total": 0.0,
                        "prod_cost_total": 0.0,
                        "products": {},
                        "ancestors": comp.get("categ_ancestors")
                        or [{"id": cat_id, "name": cat_name}],
                    }
                adjusted_cost = (
                    (comp.get("bom_cost") or 0.0) * effective_cost_share
                )
                adjusted_prod_cost = (
                    (comp.get("prod_cost") or 0.0) * effective_cost_share
                )
                cat = category_map[cat_id]
                cat["total"] += adjusted_cost
                cat["prod_cost_total"] += adjusted_prod_cost

                prod_id = comp.get("product_id")
                if prod_id not in cat["products"]:
                    cat["products"][prod_id] = {
                        "product_id": prod_id,
                        "name": comp.get("name", ""),
                        "link_id": comp.get("link_id") or prod_id,
                        "link_model": comp.get("link_model", "product.product"),
                        "total": 0.0,
                        "prod_cost_total": 0.0,
                        "usages": [],
                    }
                product = cat["products"][prod_id]
                product["total"] += adjusted_cost
                product["prod_cost_total"] += adjusted_prod_cost

                # Aggregate usages by parent product
                existing_usage = next(
                    (
                        u
                        for u in product["usages"]
                        if u["parent_product_id"] == parent_product_id
                    ),
                    None,
                )
                if existing_usage:
                    existing_usage["quantity"] += comp.get("quantity") or 0.0
                    existing_usage["total"] += adjusted_cost
                    existing_usage["prod_cost"] += adjusted_prod_cost
                else:
                    product["usages"].append(
                        {
                            "parent_product_id": parent_product_id,
                            "parent_name": parent_name,
                            "quantity": comp.get("quantity") or 0.0,
                            "uom_name": comp.get("uom_name", ""),
                            "total": adjusted_cost,
                            "prod_cost": adjusted_prod_cost,
                            "lead_time": comp.get("lead_time", False),
                            "route_name": comp.get("route_name", ""),
                            "route_detail": comp.get("route_detail", ""),
                            "route_type": comp.get("route_type", ""),
                            "bom_id": comp.get("bom_id", False),
                            "parent_route_name": parent_route_info["route_name"],
                            "parent_route_detail": parent_route_info["route_detail"],
                            "parent_route_type": parent_route_info["route_type"],
                            "parent_bom_id": parent_route_info["bom_id"],
                        }
                    )

    @api.model
    def _build_category_tree(self, category_map):
        """
        Builds a hierarchical category tree from the flat leaf-category map.
        Python port of ``buildCategoryTree`` in bom_cost_summary_utils.js.

        :returns list: Root-level nodes sorted by total descending.
        """
        node_map = {}
        roots = []

        for leaf in category_map.values():
            ancestors = leaf["ancestors"]
            parent_children = roots

            for i, anc in enumerate(ancestors):
                anc_id = anc["id"]
                if anc_id not in node_map:
                    node = {
                        "id": anc_id,
                        "name": anc["name"],
                        "depth": i,
                        "total": 0.0,
                        "prod_cost_total": 0.0,
                        "children": [],
                        "products": [],
                    }
                    node_map[anc_id] = node
                    parent_children.append(node)
                else:
                    node = node_map[anc_id]
                    if node not in parent_children:
                        parent_children.append(node)
                        if node in roots and parent_children is not roots:
                            roots.remove(node)

                node = node_map[anc_id]
                if i == len(ancestors) - 1:
                    node["products"] = sorted(
                        leaf["products"].values(),
                        key=lambda p: p["total"],
                        reverse=True,
                    )
                    node["total"] += leaf["total"]
                    node["prod_cost_total"] += leaf["prod_cost_total"]

                parent_children = node["children"]

        # Normalise depth top-down
        def normalise_depth(nodes, depth):
            for n in nodes:
                n["depth"] = depth
                normalise_depth(n["children"], depth + 1)

        normalise_depth(roots, 0)

        # Bubble costs from leaves up to roots
        def bubble_up(node):
            for child in node["children"]:
                bubble_up(child)
                node["total"] += child["total"]
                node["prod_cost_total"] += child["prod_cost_total"]

        for root in roots:
            bubble_up(root)

        # Sort recursively by total descending
        def sort_tree(nodes):
            nodes.sort(key=lambda n: n["total"], reverse=True)
            for n in nodes:
                sort_tree(n["children"])

        sort_tree(roots)
        return roots

    @api.model
    def _enrich_byproduct_prod_cost_pct(self, nodes, total_prod_cost):
        """
        Recursively add prod_cost_percentage to every node, product and usage
        in a byproduct category tree.  This is the second % column shown in
        the byproducts section: prod_cost_total / total * 100.
        Always meaningful, even when bom_cost = 0 (cost_share = 0%).
        Python port of ``enrichByproductProdCostPct`` in bom_cost_summary_utils.js.
        """
        for node in nodes:
            node["prod_cost_percentage"] = (
                node["prod_cost_total"] / total_prod_cost * 100
                if total_prod_cost
                else 0.0
            )
            for prod in node.get("products", []):
                prod["prod_cost_percentage"] = (
                    prod["prod_cost_total"] / total_prod_cost * 100
                    if total_prod_cost
                    else 0.0
                )
                for usage in prod.get("usages", []):
                    usage["prod_cost_percentage"] = (
                        usage["prod_cost"] / total_prod_cost * 100
                        if total_prod_cost
                        else 0.0
                    )
            self._enrich_byproduct_prod_cost_pct(node.get("children", []), total_prod_cost)

    @api.model
    def _enrich_category_tree(self, nodes, rate, total_components):
        """
        Recursively add percentage and USD fields to all tree nodes.
        Python port of ``enrichCategoryTree`` in bom_cost_summary_utils.js.
        """
        for node in nodes:
            node["percentage"] = (
                node["total"] / total_components * 100
                if total_components
                else 0.0
            )
            node["total_usd"] = node["total"] * rate if rate else False
            node["prod_cost_total_usd"] = (
                node["prod_cost_total"] * rate if rate else False
            )
            for prod in node["products"]:
                prod["percentage"] = (
                    prod["total"] / total_components * 100
                    if total_components
                    else 0.0
                )
                prod["total_usd"] = prod["total"] * rate if rate else False
                prod["prod_cost_total_usd"] = (
                    prod["prod_cost_total"] * rate if rate else False
                )
                # Aggregate quantity for PDF display (single UoM only).
                prod_usages = prod.get("usages", [])
                uoms = {
                    u.get("uom_name", "") for u in prod_usages
                    if u.get("uom_name")
                }
                if len(uoms) == 1:
                    total_qty = sum(u.get("quantity", 0) for u in prod_usages)
                    prod["quantity_display"] = "%.4g %s" % (total_qty, list(uoms)[0])
                else:
                    prod["quantity_display"] = _("—") if len(uoms) > 1 else ""
                for usage in prod["usages"]:
                    usage["percentage"] = (
                        usage["total"] / total_components * 100
                        if total_components
                        else 0.0
                    )
                    usage["total_usd"] = (
                        usage["total"] * rate if rate else False
                    )
                    usage["prod_cost_usd"] = (
                        usage["prod_cost"] * rate if rate else False
                    )
            self._enrich_category_tree(node["children"], rate, total_components)
