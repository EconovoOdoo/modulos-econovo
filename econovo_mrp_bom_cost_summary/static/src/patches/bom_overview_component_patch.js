/** @odoo-module **/

import { useSubEnv } from "@odoo/owl";
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
        // Add the performance key so BomOverviewDisplayFilter receives it
        // in showOptions and our patched checkbox can toggle it.
        this.state.showOptions.performance = false;
        // Inject Excel export callback so bom_overview_control_panel_patch.xml
        // can render the "Excel" button on the native BOM overview page.
        useSubEnv({
            overviewXlsxExport: () => this._onExportXlsx(),
        });
    },

    /**
     * Triggers a file download of the BOM Cost Summary as .xlsx.
     * Mirrors the same logic in BomCostSummaryView.onExportXlsx().
     */
    _onExportXlsx() {
        const params = new URLSearchParams({
            bom_id:     this.props.action.context.active_id,
            quantity:   this.state.bomQuantity || 1,
            costs:      this.state.showOptions.costs,
            operations: this.state.showOptions.operations,
            lead_times: this.state.showOptions.leadTimes,
        });
        if (this.state.currentWarehouse && this.state.currentWarehouse.id) {
            params.set("warehouse_id", this.state.currentWarehouse.id);
        }
        if (this.showVariants && this.state.currentVariantId) {
            params.set("variant", this.state.currentVariantId);
        }
        window.open(
            "/econovo/bom_cost_summary/export_xlsx?" + params.toString(),
            "_blank",
        );
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

