/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useSubEnv } from "@odoo/owl";
import { MoOverview } from "@mrp/components/mo_overview/mrp_mo_overview";
import { BomCostSummarySection } from
    "@econovo_mrp_bom_cost_summary/components/bom_cost_summary_section/bom_cost_summary_section";
import { computeMoCostSummary } from "../utils/mo_cost_summary_utils";

// Add BomCostSummarySection to MoOverview's component registry so the XML
// template (mo_overview_patch.xml) can reference it by name.
patch(MoOverview, {
    components: {
        ...MoOverview.components,
        BomCostSummarySection,
    },
});

patch(MoOverview.prototype, {
    /**
     * Extend setup to add costSummary to reactive state and provide
     * overviewBus / overviewXlsxExport to the env so the patched
     * MO Overview control-panel template can render the Plegar and
     * Excel buttons.
     */
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, {
            costSummary: false,
        });
        // Extend the env with our extra flags without replacing the native
        // overviewBus that super.setup() already created.  Replacing it would
        // break MoOverview's own "update-folded" subscriptions, which are
        // registered against the bus that was active at useBus() call time.
        // BomCostSummarySection listens to env.overviewBus for fold-all /
        // unfold-all; since native components only subscribe to "unfold-all",
        // triggering "fold-all" on the shared bus only affects our section.
        useSubEnv({
            overviewHasFoldButton: true,
            overviewXlsxExport: () => this._onMoExportXlsx(),
        });
    },

    /**
     * Triggers a file download of the MO Cost Summary as an .xlsx workbook.
     */
    _onMoExportXlsx() {
        const productionId = this.props.action
            && this.props.action.context
            && this.props.action.context.active_id;
        if (!productionId) {
            return;
        }
        const params = new URLSearchParams({ production_id: productionId });
        window.open(
            "/econovo/mo_cost_summary/export_xlsx?" + params.toString(),
            "_blank",
        );
    },

    /**
     * After the native data fetch, compute and store the MO cost summary.
     * The summary is built from the flat components and operations lists
     * that have been enriched with categ_id / workcenter_id by the Python
     * override in models/report_mo_overview.py.
     */
    async getManufacturingData() {
        await super.getManufacturingData(...arguments);
        this.state.costSummary = computeMoCostSummary(this.state.data);
    },

    /**
     * ShowOptions compatible with BomCostSummarySection.
     * Derived on each render from the current MO show state.
     */
    get moCostSummaryShowOptions() {
        return {
            costs: true,
            operations: true,
            state: true,
            uom: false,
            availabilities: true,
            leadTimes: false,
            performance: false,
        };
    },

    /**
     * Column label overrides: rename "BoM Cost" → "MO Cost" and
     * "Product Cost" → "Real Cost" in BomCostSummarySection.
     */
    get moCostSummaryColumnLabels() {
        return {
            col1: _t("MO Cost"),
            col2: _t("Real Cost"),
        };
    },
});
