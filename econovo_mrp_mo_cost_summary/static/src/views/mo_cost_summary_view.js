/** @odoo-module **/

import { Component, EventBus, onWillStart, useState, useSubEnv } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { BomCostSummarySection } from
    "@econovo_mrp_bom_cost_summary/components/bom_cost_summary_section/bom_cost_summary_section";
import { computeMoCostSummary } from "../utils/mo_cost_summary_utils";

/**
 * Standalone Cost Summary view for a Manufacturing Order.
 *
 * Registered as ir.actions.client tag ``mrp_mo_cost_summary_report``.
 * Opened from the smart button on mrp.production form view.
 * Renders a header with MO name, an Unfold/Fold control and the full
 * BomCostSummarySection with MO Cost / Real Cost column labels.
 */
export class MoCostSummaryView extends Component {
    static template = "econovo_mrp_mo_cost_summary.MoCostSummaryView";
    static components = { Layout, BomCostSummarySection };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        useSubEnv({ overviewBus: new EventBus() });

        this.state = useState({
            costSummary: false,
            moName: "",
            moState: "",
        });

        onWillStart(async () => {
            await this._loadData();
        });
    }

    // ---- Getters ----

    /** The mrp.production record ID passed via action context. */
    get activeId() {
        return this.props.action.context.active_id;
    }

    /** Column labels overriding the BOM module defaults. */
    get columnLabels() {
        return {
            col1: _t("MO Cost"),
            col2: _t("Real Cost"),
        };
    }

    /** ShowOptions passed to BomCostSummarySection. */
    get showOptions() {
        return {
            costs: true,
            operations: true,
            uom: false,
            availabilities: false,
            leadTimes: false,
            performance: false,
        };
    }

    // ---- Data loading ----

    async _loadData() {
        if (!this.activeId) {
            console.error("MoCostSummaryView: action context is missing active_id");
            return;
        }
        const result = await this.orm.call(
            "report.mrp.report_mo_overview",
            "get_report_values",
            [this.activeId],
        );
        const data = result.data;
        this.state.moName = data.name || "";
        this.state.moState = data.summary ? (data.summary.state || "") : "";
        this.state.costSummary = computeMoCostSummary(data);
    }

    // ---- Controls ----

    onClickFoldAll() {
        this.env.overviewBus.trigger("fold-all");
    }

    onClickUnfoldAll() {
        this.env.overviewBus.trigger("unfold-all");
    }

    /** Triggers a file download of the MO cost summary as .xlsx. */
    onExportXlsx() {
        const params = new URLSearchParams({ production_id: this.activeId });
        window.open(
            "/econovo/mo_cost_summary/export_xlsx?" + params.toString(),
            "_blank",
        );
    }
}

registry
    .category("actions")
    .add("mrp_mo_cost_summary_report", MoCostSummaryView);
