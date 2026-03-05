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
 * ``effectiveCostShare`` propagates the parent cost_share downward when
 * descending into sub-BOM nodes.
 *
 * @param {Object} node              Raw BOM node (root or sub-BOM component).
 * @param {Object} directMap         Accumulator dict (mutated in place).
 * @param {number} [effectiveCostShare=1.0]  Cumulative cost-share factor.
 */
function collectDirectUsd(node, directMap, effectiveCostShare = 1.0) {
    if (!node.components) return;

    const nodeCostShare =
        node.cost_share !== undefined && node.cost_share !== null
            ? node.cost_share
            : 1.0;
    const eff = effectiveCostShare * nodeCostShare;

    for (const comp of node.components) {
        if (comp.type === "bom" && comp.components) {
            // Sub-BOM: descend further, passing the accumulated cost-share.
            collectDirectUsd(comp, directMap, eff);
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
                (comp.bom_cost_usd_direct || 0) * eff;
            directMap[catId][prodId][parentProdId].prod +=
                (comp.prod_cost_usd_direct || 0) * eff;
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
 * Post-process an existing ``costSummary`` object (returned by
 * ``computeCostSummary``) by injecting the direct USD values from the
 * server-side data.
 *
 * Also writes the grand-total keys used by the summary footer:
 *   costSummary.totals.components_usd_direct
 *   costSummary.totals.prod_cost_usd_direct
 *   costSummary.totals.total_usd_direct
 *   costSummary.totals.total_prod_usd_direct
 *
 * Operations do not carry ``standard_price_usd`` (they use work-centre
 * hourly rates), so their direct-USD contribution is zero.
 *
 * @param {Object|null} costSummary  Output of ``computeCostSummary``.
 * @param {Object}      rawData      Raw BOM data from the server.
 * @returns {Object|null}
 */
function augmentWithDirectUsd(costSummary, rawData) {
    if (!costSummary) return costSummary;

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
    // No operations contribution to direct USD.
    costSummary.totals.total_usd_direct = totalCompUsdDirect;
    costSummary.totals.total_prod_usd_direct = totalProdCostUsdDirect;

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
     * Extended tooltip helper.  Delegates unknown keys to the original
     * implementation; handles the four new/renamed column keys.
     *
     * @param {string} key
     * @returns {string}  JSON-serialised tooltip object or empty string.
     */
    colTooltip(key) {
        const original = super.colTooltip(...arguments);
        if (original !== "") return original;

        const tips = {
            bom_cost_usd_direct: {
                title: _t("BoM Cost USD (direct price)"),
                lines: [
                    _t("Calculated using product.standard_price_usd"),
                    _t("= BoM Cost (ARS) \u00d7 (standard_price_usd \u00f7 standard_price_ars)"),
                    _t("Reflects the USD catalogue price on the product, not the exchange rate"),
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
        return tip ? JSON.stringify(tip) : "";
    },
});
