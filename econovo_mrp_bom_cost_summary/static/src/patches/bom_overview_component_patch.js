/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { BomOverviewComponent } from
    "@mrp/components/bom_overview/mrp_bom_overview";
import {
    computeCostSummary,
    collectCosts,
    buildCategoryTree,
    enrichCategoryTree,
} from "../utils/bom_cost_summary_utils";

patch(BomOverviewComponent.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, {
            costSummary: false,
            secondaryCurrency: false,
        });
    },

    async getBomData() {
        const bomData = await super.getBomData(...arguments);
        this.state.secondaryCurrency = bomData.secondary_currency || false;
        this.state.costSummary = this._computeCostSummary(
            this.state.bomData,
            this.state.secondaryCurrency
        );
        return bomData;
    },

    /**
     * Traverses the recursive bomData tree and aggregates:
     * - Component costs by category -> product -> parent usages (3-level)
     * - Operation costs by work center with inline parent reference
     *
     * @param {Object} data - The recursive BOM data tree (state.bomData)
     * @param {Object|false} secondaryCurrency - USD currency info or false
     * @returns {Object|false} Cost summary object or false if empty
     */
    /** @see bom_cost_summary_utils.computeCostSummary */
    _computeCostSummary(data, secondaryCurrency) {
        return computeCostSummary(data, secondaryCurrency);
    },

    /** @see bom_cost_summary_utils.buildCategoryTree */
    _buildCategoryTree(categoryMap) {
        return buildCategoryTree(categoryMap);
    },

    /** @see bom_cost_summary_utils.enrichCategoryTree */
    _enrichCategoryTree(nodes, rate, totalComponents) {
        return enrichCategoryTree(nodes, rate, totalComponents);
    },

    /** @see bom_cost_summary_utils.collectCosts */
    _collectCosts(node, categoryMap, workcenterMap, ancestorCostShare = 1.0) {
        return collectCosts(node, categoryMap, workcenterMap, ancestorCostShare);
    },
});

