/** @odoo-module **/
/**
 * Bridge module: econovo_mrp_bom_cost_summary_dolarization
 *
 * Adds two "direct USD" columns to the BOM Cost Summary using
 * ``product.standard_price_usd`` / ``workcenter.costs_hour_usd`` (from
 * ``gg_cost_dolarization``) and restricts the existing exchange-rate USD
 * columns to developer mode.
 *
 * The direct-USD aggregation is computed SERVER-SIDE (single source of truth)
 * by ``report.econovo_mrp_bom_cost_summary.report_cost_summary
 * ._compute_cost_summary`` (see ``models/mrp_report_bom_structure.py``), so the
 * interactive UI, the PDF and the Excel export all display identical figures.
 * This file only provides the display-side patches on BomCostSummarySection:
 *  - showCostsUsd        -> exchange-rate columns, restricted to developer mode
 *  - showCostsUsdDirect  -> direct-USD columns, always visible when installed
 *  - fmtUsdDirect        -> format a monetary value in the secondary currency
 *  - colTooltip          -> tooltips for the direct / exchange-rate columns
 */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { BomCostSummarySection } from "@econovo_mrp_bom_cost_summary/components/bom_cost_summary_section/bom_cost_summary_section";

/**
 * BomCostSummarySection display patches.
 *
 * The direct-USD values (``*_usd_direct``) are provided by the server-side
 * cost summary; these getters/formatters only control how they are shown.
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
     * Tooltip helper for the direct-USD / exchange-rate column headers.
     * Handles the bridge-specific keys; any other key is delegated to the
     * base-module implementation so all base tooltips keep working.
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
                    _t("The USD cost is stored per company and frozen at the rate of its last update"),
                    _t("On purchases in USD it is the vendor's own price, not a re-conversion"),
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
                    _t("USD cost stored on the variant, for the active company"),
                    _t("Frozen at the rate of its last update: it does not follow today's quotation"),
                    _t("A gap with the exchange-rate column means the cost is outdated"),
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
