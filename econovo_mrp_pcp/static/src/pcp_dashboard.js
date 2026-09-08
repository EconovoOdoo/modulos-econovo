/** @odoo-module **/
// ---------------------------------------------------------------------------
//  Econovo - PCP Production Progress Dashboard
//  OWL component, same architectural pattern as dotbd_hr_zk_attendance_suite's
//  AttendanceDashboard (ir.actions.client tag + JSON controller routes).
// ---------------------------------------------------------------------------
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class PcpProductionDashboard extends Component {
    static template = "econovo_mrp_pcp.PcpProductionDashboard";
    static props = ["*"];

    setup() {
        this.rpc = useService("rpc");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            processFilter: "ALL",
            statusFilter: "ALL",
            searchQuery: "",
            includeArchived: false,
            processes: [],
            priorities: [],
            isManager: false,
            plans: [],
            displayProcesses: [],
        });

        onWillStart(async () => {
            await this._loadFilters();
            await this._loadData();
        });
    }

    async _loadFilters() {
        const filters = await this.rpc("/pcp/dashboard/filters", {});
        this.state.processes = filters.processes;
        this.state.priorities = filters.priorities;
        this.state.isManager = filters.is_manager;
    }

    async _loadData() {
        this.state.loading = true;
        try {
            const data = await this.rpc("/pcp/dashboard/data", {
                include_archived: this.state.includeArchived,
            });
            this.state.plans = data.plans;
            this.state.displayProcesses = data.display_processes;
        } finally {
            this.state.loading = false;
        }
    }

    get filteredPlans() {
        let rows = this.state.plans;
        const query = this.state.searchQuery.trim().toLowerCase();
        if (query) {
            rows = rows.filter((row) => row.plan_name.toLowerCase().includes(query));
        }
        if (this.state.processFilter !== "ALL") {
            rows = rows.filter((row) => {
                const stats = row.by_process[this.state.processFilter];
                return stats && stats.qty_production > 0;
            });
        }
        if (this.state.statusFilter !== "ALL") {
            rows = rows.filter((row) => {
                const progress = this.state.processFilter === "ALL"
                    ? row.progress
                    : (row.by_process[this.state.processFilter]?.progress || 0);
                return this.state.statusFilter === "PENDING" ? progress < 100 : progress >= 100;
            });
        }
        return rows;
    }

    get kpis() {
        const rows = this.filteredPlans;
        const totalProduction = rows.reduce((acc, row) => acc + row.qty_production, 0);
        const totalProduced = rows.reduce((acc, row) => acc + row.qty_produced, 0);
        return {
            totalPlans: rows.length,
            totalProduction,
            totalProduced,
            globalProgress: totalProduction ? Math.round((totalProduced / totalProduction) * 100) : 0,
        };
    }

    onProcessFilterChange(ev) {
        this.state.processFilter = ev.target.value;
    }

    onStatusFilterChange(ev) {
        this.state.statusFilter = ev.target.value;
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
    }

    async onToggleArchived() {
        this.state.includeArchived = !this.state.includeArchived;
        await this._loadData();
    }

    async onPriorityChange(planId, ev) {
        const value = ev.target.value ? parseInt(ev.target.value, 10) : false;
        await this.orm.write("mrp.plan", [planId], { priority_id: value });
        await this._loadData();
    }

    async onToggleActive(plan) {
        await this.orm.write("mrp.plan", [plan.plan_id], { active: !plan.active });
        this.notification.add(
            plan.active ? _t("Plan archived") : _t("Plan restored"),
            { type: "success" }
        );
        await this._loadData();
    }

    async onExportExcel() {
        await this.action.doAction({
            type: "ir.actions.report",
            report_name: "econovo_mrp_pcp.report_plan_progress",
            report_type: "xlsx",
            context: { active_ids: this.filteredPlans.map((row) => row.plan_id).filter(Boolean) },
        });
    }
}

registry.category("actions").add("pcp_production_dashboard", PcpProductionDashboard);
