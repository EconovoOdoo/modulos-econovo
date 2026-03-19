/** @odoo-module **/
/**
 * Bridge module: econovo_mrp_bom_cost_summary_dolarization
 *
 * Adds two "direct USD" columns to the BOM Cost Summary view using
 * ``product.standard_price_usd`` (from ``gg_cost_dolarization``) and
 * restricts the existing exchange-rate USD columns to developer mode.
 *
 * Patches applied:
 *  - BomOverviewComponent._computeCostSummary  → uses computeCostSummaryWithDirect
 *  - BomCostSummaryView.getBomData             → re-runs with direct USD augmentation
 *  - BomCostSummarySection prototype:
 *      · showCostsUsd        (existing)  → requires debug mode
 *      · showCostsUsdDirect  (new)       → always visible when module installed
 *      · fmtUsdDirect        (new)       → format monetary in secondary currency
 *      · colTooltip          (extended)  → tooltips for new + renamed columns
 */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { computeCostSummary } from "@econovo_mrp_bom_cost_summary/utils/bom_cost_summary_utils";
import { BomOverviewComponent } from "@mrp/components/bom_overview/mrp_bom_overview";
import { BomCostSummarySection } from "@econovo_mrp_bom_cost_summary/components/bom_cost_summary_section/bom_cost_summary_section";
import { BomCostSummaryView } from "@econovo_mrp_bom_cost_summary/views/bom_cost_summary_view";

// ---------------------------------------------------------------------------
// Direct USD aggregation helpers
// ---------------------------------------------------------------------------

/**
 * Traverse the raw BOM tree received from the server and collect the
 * ``bom_cost_usd_direct`` / ``prod_cost_usd_direct`` values added by the
 * Python override, grouping them as:
 *
 *   directMap[catId][prodId][parentProdId] = { bom: <total>, prod: <total> }
 *
 * Raw server values are used without cost_share scaling – same rationale
 * as the base ``collectCosts``: the server already applies cost_share at
 * sub-BOM level; we rely on the explicit byproducts subtraction in
 * ``augmentWithDirectUsd`` for the top-level adjustment.
 *
 * Product Cost (prod) uses native Odoo semantics: for sub-BOM components
 * the sub-product's own ``prod_cost_usd_direct`` is used (standard_price
 * in USD × qty); its internal leaves receive prod = 0 to avoid
 * double-counting – same strategy as base ``collectCosts``.
 *
 * @param {Object}  node         Raw BOM node (root or sub-BOM component).
 * @param {Object}  directMap    Accumulator dict (mutated in place).
 * @param {boolean} skipProdCost True when recursing inside a sub-BOM.
 */
function collectDirectUsd(node, directMap, skipProdCost = false) {
    if (!node.components) return;

    for (const comp of node.components) {
        if (comp.type === "bom" && comp.components) {
            // Sub-BOM: capture prod_cost_usd_direct at this level (native
            // semantics); recurse for bom_cost_usd_direct leaf breakdown.
            if (!skipProdCost) {
                const catId = comp.categ_id || 0;
                const prodId = comp.product_id;
                const parentProdId = node.product_id;
                if (!directMap[catId]) directMap[catId] = {};
                if (!directMap[catId][prodId]) directMap[catId][prodId] = {};
                if (!directMap[catId][prodId][parentProdId]) {
                    directMap[catId][prodId][parentProdId] = { bom: 0, prod: 0 };
                }
                // bom stays 0 here — the recursive call below populates it.
                directMap[catId][prodId][parentProdId].prod +=
                    comp.prod_cost_usd_direct || 0;
            }
            collectDirectUsd(comp, directMap, true);
        } else {
            // Leaf component: record its direct USD contribution.
            const catId = comp.categ_id || 0;
            const prodId = comp.product_id;
            const parentProdId = node.product_id;

            if (!directMap[catId]) directMap[catId] = {};
            if (!directMap[catId][prodId]) directMap[catId][prodId] = {};
            if (!directMap[catId][prodId][parentProdId]) {
                directMap[catId][prodId][parentProdId] = { bom: 0, prod: 0 };
            }
            directMap[catId][prodId][parentProdId].bom +=
                comp.bom_cost_usd_direct || 0;
            // prod_cost_usd_direct = 0 for leaves inside a sub-BOM: already
            // captured at the sub-BOM level above.
            if (!skipProdCost) {
                directMap[catId][prodId][parentProdId].prod +=
                    comp.prod_cost_usd_direct || 0;
            }
        }
    }
}

/**
 * Walk the category/product/usage tree built by ``computeCostSummary`` and
 * inject the direct USD totals gathered by ``collectDirectUsd``.  Values
 * bubble up from usages → products → categories, mirroring the way
 * ``buildCategoryTree`` bubbles ARS costs.
 *
 * After this call every node in the tree has:
 *   node.total_usd_direct            – direct USD BoM cost
 *   node.prod_cost_total_usd_direct  – direct USD product cost
 *
 * @param {Array}  nodes      Root-level category nodes from costSummary.
 * @param {Object} directMap  Output of ``collectDirectUsd``.
 */
function injectAndBubbleDirectUsd(nodes, directMap) {
    for (const node of nodes) {
        // Depth-first: inject into children first.
        injectAndBubbleDirectUsd(node.children || [], directMap);

        let nodeTotal = 0;
        let nodeProdTotal = 0;

        // Accumulate from child categories.
        for (const child of node.children || []) {
            nodeTotal += child.total_usd_direct || 0;
            nodeProdTotal += child.prod_cost_total_usd_direct || 0;
        }

        // Inject into products belonging to this category.
        const catDirect = directMap[node.id];
        for (const prod of node.products || []) {
            let prodTotal = 0;
            let prodProdTotal = 0;
            const prodDirect = catDirect && catDirect[prod.product_id];

            for (const usage of prod.usages || []) {
                const parentId = usage.parent_product_id;
                const usageDirect = prodDirect && prodDirect[parentId];
                usage.total_usd_direct = usageDirect ? usageDirect.bom : 0;
                usage.prod_cost_usd_direct = usageDirect ? usageDirect.prod : 0;
                prodTotal += usage.total_usd_direct;
                prodProdTotal += usage.prod_cost_usd_direct;
            }

            prod.total_usd_direct = prodTotal;
            prod.prod_cost_total_usd_direct = prodProdTotal;
            nodeTotal += prodTotal;
            nodeProdTotal += prodProdTotal;
        }

        node.total_usd_direct = nodeTotal;
        node.prod_cost_total_usd_direct = nodeProdTotal;
    }
}

/**
 * Traverse the raw BOM tree and collect the ``bom_cost_usd_direct`` /
 * ``prod_cost_usd_direct`` values for every BYPRODUCT, grouped as:
 *
 *   byproductDirectMap[catId][prodId][parentProdId] = { bom, prod }
 *
 * Raw server values are used without cost_share scaling – same rationale
 * as the base ``collectCosts``.
 *
 * @param {Object} node                Raw BOM node.
 * @param {Object} byproductDirectMap  Accumulator dict (mutated in place).
 */
function collectDirectUsdByproducts(node, byproductDirectMap) {
    if (node.byproducts) {
        for (const bp of node.byproducts) {
            const catId = bp.categ_id || 0;
            // Byproduct dicts use link_id (product.product/template id) or
            // id (mrp.bom.byproduct id) as the product key – same as
            // collectCosts uses for prodKey.  bp.product_id does not exist.
            const prodId = bp.link_id || bp.id;
            const parentProdId = node.product_id;

            if (!byproductDirectMap[catId]) byproductDirectMap[catId] = {};
            if (!byproductDirectMap[catId][prodId]) byproductDirectMap[catId][prodId] = {};
            if (!byproductDirectMap[catId][prodId][parentProdId]) {
                byproductDirectMap[catId][prodId][parentProdId] = { bom: 0, prod: 0 };
            }
            byproductDirectMap[catId][prodId][parentProdId].bom +=
                bp.bom_cost_usd_direct || 0;
            byproductDirectMap[catId][prodId][parentProdId].prod +=
                bp.prod_cost_usd_direct || 0;
        }
    }
    // Recurse into sub-BOM components to collect THEIR byproducts too.
    if (!node.components) return;
    for (const comp of node.components) {
        if (comp.type === 'bom' && comp.components) {
            collectDirectUsdByproducts(comp, byproductDirectMap);
        }
    }
}

/**
 * Mirror of ``injectAndBubbleDirectUsd`` for the byproduct category tree.
 * Walks ``costSummary.byproductCategories`` and sets ``total_usd_direct``
 * / ``prod_cost_total_usd_direct`` on every node, product and usage.
 *
 * @param {Array}  nodes               Root-level byproduct category nodes.
 * @param {Object} byproductDirectMap  Output of ``collectDirectUsdByproducts``.
 */
function injectAndBubbleDirectUsdByproducts(nodes, byproductDirectMap) {
    for (const node of nodes) {
        injectAndBubbleDirectUsdByproducts(node.children || [], byproductDirectMap);

        let nodeTotal = 0;
        let nodeProdTotal = 0;

        for (const child of node.children || []) {
            nodeTotal += child.total_usd_direct || 0;
            nodeProdTotal += child.prod_cost_total_usd_direct || 0;
        }

        const catDirect = byproductDirectMap[node.id];
        for (const prod of node.products || []) {
            let prodTotal = 0;
            let prodProdTotal = 0;
            const prodDirect = catDirect && catDirect[prod.product_id];

            for (const usage of prod.usages || []) {
                const parentId = usage.parent_product_id;
                const usageDirect = prodDirect && prodDirect[parentId];
                usage.total_usd_direct = usageDirect ? usageDirect.bom : 0;
                usage.prod_cost_usd_direct = usageDirect ? usageDirect.prod : 0;
                prodTotal += usage.total_usd_direct;
                prodProdTotal += usage.prod_cost_usd_direct;
            }

            prod.total_usd_direct = prodTotal;
            prod.prod_cost_total_usd_direct = prodProdTotal;
            nodeTotal += prodTotal;
            nodeProdTotal += prodProdTotal;
        }

        node.total_usd_direct = nodeTotal;
        node.prod_cost_total_usd_direct = nodeProdTotal;
    }
}

/**
 * Traverse the raw BOM tree and collect the ``bom_cost_usd_direct`` values
 * injected by the Python ``_get_operation_line`` override into every
 * operation node, grouped as:
 *
 *   opsDirectMap[workcenter_id][link_id][parent_product_id] = <sum>
 *
 * The triple key guarantees uniqueness even when the same operation
 * (link_id) appears in multiple sub-BOM contexts (different
 * parent_product_id values) and when multiple instances of a work center
 * contribute to the same BOM (different link_ids).
 *
 * Recursion handles the edge case where operations are defined on
 * sub-BOMs (E9): every BOM level in the tree is visited.
 *
 * @param {Object} node          Raw BOM node (root or sub-BOM component).
 * @param {Object} opsDirectMap  Accumulator dict (mutated in place).
 */
function collectDirectUsdOps(node, opsDirectMap) {
    if (node.operations) {
        for (const op of node.operations) {
            const wcId = op.workcenter_id || 0;
            const linkId = op.link_id || 0;
            const parentProdId = node.product_id;
            const usdDirect = op.bom_cost_usd_direct || 0;

            if (!opsDirectMap[wcId]) opsDirectMap[wcId] = {};
            if (!opsDirectMap[wcId][linkId]) opsDirectMap[wcId][linkId] = {};
            if (!opsDirectMap[wcId][linkId][parentProdId]) {
                opsDirectMap[wcId][linkId][parentProdId] = 0;
            }
            opsDirectMap[wcId][linkId][parentProdId] += usdDirect;
        }
    }
    // Recurse into sub-BOM components so that operations on nested BOMs
    // are also collected (edge case E9).
    if (node.components) {
        for (const comp of node.components) {
            if (comp.type === 'bom' && comp.components) {
                collectDirectUsdOps(comp, opsDirectMap);
            }
        }
    }
}

/**
 * Walk ``costSummary.workcenters`` and inject direct-USD totals gathered by
 * ``collectDirectUsdOps``.
 *
 * After this call:
 *   wc.total_usd_direct  – summed direct USD cost for the whole work center
 *   item.total_usd_direct – direct USD cost for a single operation row
 *
 * The lookup uses the same triple key [wcId][linkId][parentProdId] as the
 * collector; if no matching entry is found (e.g. ``costs_hour_usd = 0``),
 * the value defaults to 0.
 *
 * @param {Array}  workcenters  ``costSummary.workcenters`` array.
 * @param {Object} opsDirectMap Output of ``collectDirectUsdOps``.
 */
function injectAndBubbleDirectUsdOps(workcenters, opsDirectMap) {
    for (const wc of workcenters) {
        let wcTotal = 0;
        for (const item of wc.items || []) {
            const wcMap = opsDirectMap[wc.id];
            const linkMap = wcMap && wcMap[item.link_id];
            const usdDirect = (linkMap && linkMap[item.parent_product_id]) || 0;
            item.total_usd_direct = usdDirect;
            wcTotal += usdDirect;
        }
        wc.total_usd_direct = wcTotal;
    }
}

/**
 * Post-process an existing ``costSummary`` object (returned by
 * ``computeCostSummary``) by injecting the direct USD values from the
 * server-side data.
 *
 * Writes the following grand-total keys on ``costSummary.totals``:
 *   components_usd_direct           – BoM Cost USD direct (components)
 *   prod_cost_usd_direct            – Product Cost USD direct (components)
 *   operations_usd_direct           – BoM Cost USD direct (operations)
 *   total_usd_direct                – components + operations
 *   total_prod_usd_direct           – same as prod_cost_usd_direct
 *   byproducts_usd_direct           – BoM Cost USD direct (byproducts)
 *   byproducts_prod_cost_usd_direct – Product Cost USD direct (byproducts)
 *   net_bom_usd_direct              – total_usd_direct − byproducts_usd_direct
 *   net_prod_usd_direct             – total_prod_usd_direct − byproducts_prod_cost_usd_direct
 *
 * ``operations_usd_direct`` is derived from ``workcenter.costs_hour_usd``
 * (added by this bridge module).  When no USD hourly rate is configured,
 * the value is 0 — same treatment as components with
 * ``standard_price_usd = 0``.
 *
 * @param {Object|null} costSummary  Output of ``computeCostSummary``.
 * @param {Object}      rawData      Raw BOM data from the server.
 * @returns {Object|null}
 */
function augmentWithDirectUsd(costSummary, rawData) {
    if (!costSummary) return costSummary;

    // --- Components ---
    const directMap = {};
    collectDirectUsd(rawData, directMap);
    injectAndBubbleDirectUsd(costSummary.categories || [], directMap);

    const totalCompUsdDirect = (costSummary.categories || []).reduce(
        (s, c) => s + (c.total_usd_direct || 0),
        0,
    );
    const totalProdCostUsdDirect = (costSummary.categories || []).reduce(
        (s, c) => s + (c.prod_cost_total_usd_direct || 0),
        0,
    );

    costSummary.totals.components_usd_direct = totalCompUsdDirect;
    costSummary.totals.prod_cost_usd_direct = totalProdCostUsdDirect;

    // --- Operations ---
    const opsDirectMap = {};
    collectDirectUsdOps(rawData, opsDirectMap);
    injectAndBubbleDirectUsdOps(costSummary.workcenters || [], opsDirectMap);

    const totalOpsUsdDirect = (costSummary.workcenters || []).reduce(
        (s, wc) => s + (wc.total_usd_direct || 0),
        0,
    );
    costSummary.totals.operations_usd_direct = totalOpsUsdDirect;

    // Grand totals now include both components and operations.
    costSummary.totals.total_usd_direct = totalCompUsdDirect + totalOpsUsdDirect;
    costSummary.totals.total_prod_usd_direct = totalProdCostUsdDirect;

    // --- Byproducts ---
    const byproductDirectMap = {};
    collectDirectUsdByproducts(rawData, byproductDirectMap);
    injectAndBubbleDirectUsdByproducts(
        costSummary.byproductCategories || [],
        byproductDirectMap,
    );

    const totalByprodUsdDirect = (costSummary.byproductCategories || []).reduce(
        (s, c) => s + (c.total_usd_direct || 0),
        0,
    );
    const totalByprodProdCostUsdDirect = (costSummary.byproductCategories || []).reduce(
        (s, c) => s + (c.prod_cost_total_usd_direct || 0),
        0,
    );

    costSummary.totals.byproducts_usd_direct = totalByprodUsdDirect;
    costSummary.totals.byproducts_prod_cost_usd_direct = totalByprodProdCostUsdDirect;
    costSummary.totals.net_bom_usd_direct =
        costSummary.totals.total_usd_direct - totalByprodUsdDirect;
    costSummary.totals.net_prod_usd_direct =
        totalProdCostUsdDirect - totalByprodProdCostUsdDirect;

    return costSummary;
}

/**
 * Drop-in replacement for ``computeCostSummary`` that also injects direct
 * USD columns.  Exported for unit-testing convenience.
 *
 * @param {Object} data                Raw BOM data from the server.
 * @param {Object} secondaryCurrency   Secondary currency record (USD).
 * @returns {Object}
 */
export function computeCostSummaryWithDirect(data, secondaryCurrency) {
    return augmentWithDirectUsd(computeCostSummary(data, secondaryCurrency), data);
}

// ---------------------------------------------------------------------------
// Patches
// ---------------------------------------------------------------------------

/**
 * BomOverviewComponent – swap in the augmented cost-summary function so that
 * the side-panel view also carries direct USD totals.
 */
patch(BomOverviewComponent.prototype, {
    _computeCostSummary(data, secondaryCurrency) {
        return computeCostSummaryWithDirect(data, secondaryCurrency);
    },
});

/**
 * BomCostSummaryView – ensure that ``getBomData`` (called on the dedicated
 * full-screen view) also produces the augmented summary.
 */
patch(BomCostSummaryView.prototype, {
    async getBomData() {
        const bomData = await super.getBomData(...arguments);
        // ``super.getBomData`` stores the result in ``this.state``; we
        // recompute costSummary with the augmented helper.
        if (this.state && this.state.bomData) {
            this.state.costSummary = computeCostSummaryWithDirect(
                this.state.bomData,
                this.state.secondaryCurrency,
            );
        }
        return bomData;
    },
});

/**
 * BomCostSummarySection component:
 *
 *  · ``showCostsUsd``        – restrict existing exchange-rate columns to
 *                              developer mode.
 *  · ``showCostsUsdDirect``  – new getter; always visible when this module
 *                              is installed and a secondary currency exists.
 *  · ``fmtUsdDirect``        – monetary formatter using the secondary currency.
 *  · ``colTooltip``          – extended with tooltips for the new columns and
 *                              updated description for exchange-rate columns.
 */
patch(BomCostSummarySection.prototype, {
    /** Exchange-rate USD columns: only shown in developer mode. */
    get showCostsUsd() {
        return this.hasSecondary && this.showCosts && !!this.env.debug;
    },

    /** Direct-USD columns: always shown when module is installed. */
    get showCostsUsdDirect() {
        return this.hasSecondary && this.showCosts;
    },

    /**
     * Format a monetary value in the secondary (USD) currency.
     *
     * @param {number|false|undefined} val
     * @returns {string}
     */
    fmtUsdDirect(val) {
        if (!this.hasSecondary || val === false || val === undefined) return "";
        return formatMonetary(val, { currencyId: this.secondaryCurrency.id });
    },

    /**
     * Tooltip helper for the new direct-USD column headers.
     * Handles the 4 bridge-specific keys; for any other key, delegates
     * to the base class implementation so that all base-module tooltips
     * (Components, Operations, Byproducts sections, Grand Total, etc.)
     * continue to work correctly when this bridge module is installed.
     *
     * @param {string} key
     * @returns {string}  JSON-serialised tooltip object or empty string.
     */
    colTooltip(key, curName, usdName) {
        const tips = {
            bom_cost_usd_direct: {
                title: _t("BoM Cost USD (direct price)"),
                lines: [
                    _t("Calculated using product.standard_price_usd"),
                    _t("= BoM Cost (ARS) \u00d7 (standard_price_usd \u00f7 standard_price_ars)"),
                    _t("Reflects the USD catalogue price on the product, not the exchange rate"),
                ],
            },
            ops_bom_cost_usd_direct: {
                title: _t("Operations Cost USD (direct price)"),
                lines: [
                    _t("= (Duration in hours) \u00d7 workcenter.costs_hour_usd"),
                    _t("costs_hour_usd is stored on each work center"),
                    _t("Auto-updated from costs_hour (ARS) \u00d7 exchange rate when costs_hour changes"),
                    _t("Can be overridden manually on the work center form"),
                ],
            },
            prod_cost_usd_direct: {
                title: _t("Product Cost USD (direct price)"),
                lines: [
                    _t("= Quantity \u00d7 product.standard_price_usd"),
                    _t("Catalogue USD price stored directly on the product"),
                    _t("Independent of the company exchange rate"),
                ],
            },
            bom_cost_usd_exchange: {
                title: _t("BoM Cost USD (exchange rate)"),
                lines: [
                    _t("= BoM Cost (ARS) \u00d7 company exchange rate"),
                    _t("Derived from the company currency conversion rate"),
                    _t("May differ from standard_price_usd if rate is not current"),
                    _t("Only visible in developer mode"),
                ],
            },
            prod_cost_usd_exchange: {
                title: _t("Product Cost USD (exchange rate)"),
                lines: [
                    _t("= Product Cost (ARS) \u00d7 company exchange rate"),
                    _t("Derived from the company currency conversion rate"),
                    _t("Only visible in developer mode"),
                ],
            },
        };

        const tip = tips[key];
        if (tip) return JSON.stringify(tip);
        // Delegate all other keys to the base-module implementation.
        return super.colTooltip(key, curName, usdName);
    },
});
