/** @odoo-module **/

import { Component, EventBus, onWillStart, useState, useSubEnv } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/views/fields/formatters";
import { BomOverviewControlPanel } from
    "@mrp/components/bom_overview_control_panel/mrp_bom_overview_control_panel";
import { BomCostSummarySection } from
    "../components/bom_cost_summary_section/bom_cost_summary_section";
import { computeCostSummary } from "../utils/bom_cost_summary_utils";

/**
 * Standalone Cost Summary view.
 *
 * Registered as ir.actions.client tag ``mrp_bom_cost_summary_report``.
 * Reuses BomOverviewControlPanel (Odoo) for the header (quantity input,
 * warehouse dropdown, variant selector, display filter, print button,
 * unfold button) and renders only BomCostSummarySection — no BOM tree.
 *
 * An extra "Plegar" (fold-all) button is rendered below the ControlPanel.
 * Fold/unfold events are propagated to BomCostSummarySection via overviewBus.
 */
export class BomCostSummaryView extends Component {
    static template = "econovo_mrp_bom_cost_summary.BomCostSummaryView";
    static components = { BomOverviewControlPanel, BomCostSummarySection };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.context = this.props.action.context;
        this.formatFloat = formatFloat;

        // Non-reactive metadata (set once in initBomData, not changed thereafter)
        this.variants = {};
        this.warehouses = [];
        this.showVariants = false;
        this.uomName = "";

        // EC-1: create overviewBus so BomOverviewControlPanel.clickUnfold
        //       can call env.overviewBus.trigger("unfold-all") without crashing.
        // overviewHasFoldButton: flag read by bom_overview_control_panel_patch.xml
        //       to inject a "Plegar" button next to the native "Desplegar" button.
        useSubEnv({ overviewBus: new EventBus(), overviewHasFoldButton: true });

        // EC-2: currentWarehouse starts as a placeholder (not null) so the
        //       prop validator of BomOverviewControlPanel never receives undefined.
        this.state = useState({
            showOptions: {
                uom: false,
                availabilities: false,
                costs: true,
                operations: true,
                leadTimes: true,
                attachments: false,
            },
            currentWarehouse: { id: false, name: "" },
            currentVariantId: null,
            bomData: {},
            precision: 2,
            bomQuantity: null,
            costSummary: false,
            secondaryCurrency: false,
        });

        onWillStart(async () => {
            await this.getWarehouses();
            await this.initBomData();
        });
    }

    // ---- Getters ----

    /** The mrp.bom record ID passed by the smart button via action context. */
    get activeId() {
        return this.props.action.context.active_id;
    }

    // ---- Data fetching ----

    /**
     * Loads available warehouses and sets the first one as current.
     * Mirrors BomOverviewComponent.getWarehouses().
     */
    async getWarehouses() {
        const warehouses = await this.orm.call(
            "report.mrp.report_bom_structure",
            "get_warehouses",
        );
        this.warehouses = warehouses;
        if (warehouses.length) {
            this.state.currentWarehouse = warehouses[0];
        }
    }

    /**
     * Fetches raw BOM data, then derives costSummary.
     * Used both for the initial load and for reactive refreshes
     * (qty / warehouse / variant change).
     *
     * @returns {Object} Raw bomData response from get_html
     */
    async getBomData() {
        // EC-17: guard against missing active_id
        if (!this.activeId) {
            console.error("BomCostSummaryView: action context is missing active_id");
            return {};
        }
        const context = { ...this.context };
        if (this.state.currentWarehouse && this.state.currentWarehouse.id) {
            context.warehouse = this.state.currentWarehouse.id;
        }
        const bomData = await this.orm.call(
            "report.mrp.report_bom_structure",
            "get_html",
            [this.activeId, this.state.bomQuantity, this.state.currentVariantId],
            { context },
        );
        this.state.bomData = bomData.lines;
        this.state.secondaryCurrency = bomData.secondary_currency || false;
        this.state.costSummary = computeCostSummary(
            this.state.bomData,
            this.state.secondaryCurrency,
        );
        return bomData;
    }

    /**
     * Called once on initial load; extracts non-reactive metadata from the
     * raw bomData response (variants list, uomName, showVariants, precision).
     */
    async initBomData() {
        const bomData = await this.getBomData();
        this.uomName = bomData.bom_uom_name || "";
        this.variants = bomData.variants || {};
        this.showVariants = Boolean(bomData.is_variant_applied);
        this.state.bomQuantity = bomData.bom_qty || 1;
        this.state.precision = bomData.precision || 2;
    }

    // ---- Control panel callbacks ----

    onChangeWarehouse(warehouse) {
        this.state.currentWarehouse = warehouse;
        this.getBomData();
    }

    onChangeVariant(variantId) {
        this.state.currentVariantId = variantId;
        this.getBomData();
    }

    onChangeBomQuantity(quantity) {
        this.state.bomQuantity = quantity;
        this.getBomData();
    }

    onChangeDisplay(optionKey) {
        this.state.showOptions[optionKey] = !this.state.showOptions[optionKey];
    }

    // ---- Print ----

    /**
     * Builds the report URL string for the PDF action.
     *
     * @param {boolean} [printAll=false] - Print all variants.
     * @returns {string}
     */
    getReportName(printAll = false) {
        let name =
            "econovo_mrp_bom_cost_summary.report_cost_summary" +
            "?docids=" + this.activeId +
            "&costs=" + this.state.showOptions.costs +
            "&operations=" + this.state.showOptions.operations +
            "&lead_times=" + this.state.showOptions.leadTimes +
            "&quantity=" + (this.state.bomQuantity || 1) +
            "&warehouse_id=" + (this.state.currentWarehouse
                ? this.state.currentWarehouse.id : false);
        if (printAll) {
            name += "&all_variants=1";
        } else if (this.showVariants && this.state.currentVariantId) {
            name += "&variant=" + this.state.currentVariantId;
        }
        return name;
    }

    /**
     * Triggers the PDF report.
     *
     * @param {boolean} [printAll=false]
     */
    async onClickPrint(printAll = false) {
        return this.actionService.doAction({
            type: "ir.actions.report",
            report_type: "qweb-pdf",
            report_name: this.getReportName(printAll),
            report_file:
                "econovo_mrp_bom_cost_summary.report_cost_summary",
        });
    }

    /**
     * Triggers a "fold-all" event on overviewBus so BomCostSummarySection
     * collapses all its rows via its useEffect listener.
     */
    onClickFoldAll() {
        this.env.overviewBus.trigger("fold-all");
    }
}

registry
    .category("actions")
    .add("mrp_bom_cost_summary_report", BomCostSummaryView);
