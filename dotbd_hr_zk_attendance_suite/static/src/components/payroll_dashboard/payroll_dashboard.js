/** @odoo-module **/
// ---------------------------------------------------------------------------
//  Dot BD Solutions Limited – Payroll Dashboard
//  OWL 2 Component for Odoo 18
// ---------------------------------------------------------------------------
import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";

const GROUP_BY_LABELS = {
    department:    'Department',
    employee_type: 'Employee Type',
    wage_type:     'Wage Type',
    job:           'Job Position',
    template:      'Salary Template',
    state:         'Status',
};

const CHART_COLORS = [
    'rgba(99,132,255,0.75)',  'rgba(255,159,64,0.75)',
    'rgba(75,192,192,0.75)',  'rgba(255,99,132,0.75)',
    'rgba(153,102,255,0.75)', 'rgba(54,162,235,0.75)',
    'rgba(255,205,86,0.75)',  'rgba(201,203,207,0.75)',
];

export class PayrollDashboard extends Component {
    static template = "dotbd_hr_zk_attendance_suite.PayrollDashboard";
    static props = ["*"];

    setup() {
        this.action       = useService("action");
        this.notification = useService("notification");
        this.rpc          = useService("rpc");

        this.groupChartRef  = useRef("groupChart");
        this.trendChartRef  = useRef("trendChart");
        this.statusChartRef = useRef("statusChart");

        this._groupChartInst  = null;
        this._trendChartInst  = null;
        this._statusChartInst = null;

        const now = new Date();
        this.state = useState({
            loading: true,
            // ── Filters ───────────────────────────────────────────────────
            month:         now.getMonth() + 1,
            year:          now.getFullYear(),
            department_id: false,
            employee_type: '',
            wage_type:     '',
            state_filter:  '',
            group_by:      'department',
            // ── Filter options (from server) ───────────────────────────────
            departments: [],
            jobs:        [],
            templates:   [],
            // ── KPIs ─────────────────────────────────────────────────────
            month_name:       '',
            currency_symbol:  '',
            total_gross:      0,
            total_deductions: 0,
            total_net:        0,
            paid_amount:      0,
            pending_payment:  0,
            employees_total:   0,
            employees_covered: 0,
            no_payslip_count:  0,
            draft_count:     0,
            confirmed_count: 0,
            partial_count:   0,
            paid_count:      0,
            // ── Chart data ────────────────────────────────────────────────
            group_chart: [],
            type_chart:  [],
            wage_chart:  [],
            trend_chart: [],
            top_earners: [],
            alerts:      [],
        });

        onMounted(() => this._init());
        onWillUnmount(() => this._destroyCharts());
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────
    async _init() {
        const filters = await this.rpc("/payroll/dashboard/filters", {});
        this.state.departments = filters.departments || [];
        this.state.jobs        = filters.jobs        || [];
        this.state.templates   = filters.templates   || [];
        await this._loadData();
    }

    async _loadData() {
        this.state.loading = true;
        try {
            const data = await this.rpc("/payroll/dashboard/data", {
                month:         this.state.month,
                year:          this.state.year,
                department_id: this.state.department_id,
                employee_type: this.state.employee_type  || null,
                wage_type:     this.state.wage_type      || null,
                state_filter:  this.state.state_filter   || null,
                group_by:      this.state.group_by,
            });
            Object.assign(this.state, data);
            setTimeout(() => this._renderCharts(), 50);
        } finally {
            this.state.loading = false;
        }
    }

    // ── Charts ────────────────────────────────────────────────────────────────
    _destroyCharts() {
        [['_groupChartInst'], ['_trendChartInst'], ['_statusChartInst']].forEach(([k]) => {
            if (this[k]) { this[k].destroy(); this[k] = null; }
        });
    }

    async _renderCharts() {
        let Chart = window.Chart;
        if (!Chart) {
            await loadJS("/web/static/lib/Chart/Chart.js");
            Chart = window.Chart;
            if (!Chart) return;
        }
        this._destroyCharts();
        this._renderGroupChart(Chart);
        this._renderTrendChart(Chart);
        this._renderStatusChart(Chart);
    }

    _renderGroupChart(Chart) {
        const canvas = this.groupChartRef.el;
        if (!canvas || !this.state.group_chart.length) return;
        const labels = this.state.group_chart.map(d => d.name);
        const netVals   = this.state.group_chart.map(d => d.net);
        const grossVals = this.state.group_chart.map(d => d.gross);
        const sym = this.state.currency_symbol;
        this._groupChartInst = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Net Payable',
                        data: netVals,
                        backgroundColor: 'rgba(99,132,255,0.75)',
                        borderColor:     'rgba(99,132,255,1)',
                        borderWidth: 1,
                        borderRadius: 5,
                    },
                    {
                        label: 'Gross',
                        data: grossVals,
                        backgroundColor: 'rgba(75,192,192,0.4)',
                        borderColor:     'rgba(75,192,192,1)',
                        borderWidth: 1,
                        borderRadius: 5,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { font: { size: 11 } } },
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.dataset.label}: ${sym}${ctx.parsed.y.toLocaleString()}`,
                        },
                    },
                },
                scales: {
                    y: {
                        ticks: { callback: v => sym + v.toLocaleString() },
                        grid:  { color: 'rgba(0,0,0,0.05)' },
                    },
                    x: { grid: { display: false } },
                },
            },
        });
    }

    _renderTrendChart(Chart) {
        const canvas = this.trendChartRef.el;
        if (!canvas || !this.state.trend_chart.length) return;
        const labels    = this.state.trend_chart.map(d => d.month);
        const netVals   = this.state.trend_chart.map(d => d.net);
        const grossVals = this.state.trend_chart.map(d => d.gross);
        const sym = this.state.currency_symbol;
        this._trendChartInst = new Chart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Net',
                        data: netVals,
                        borderColor:     'rgba(40,167,69,1)',
                        backgroundColor: 'rgba(40,167,69,0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgba(40,167,69,1)',
                    },
                    {
                        label: 'Gross',
                        data: grossVals,
                        borderColor:     'rgba(99,132,255,0.8)',
                        backgroundColor: 'transparent',
                        fill: false,
                        tension: 0.4,
                        pointRadius: 3,
                        borderDash: [4, 3],
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { font: { size: 11 } } },
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.dataset.label}: ${sym}${ctx.parsed.y.toLocaleString()}`,
                        },
                    },
                },
                scales: {
                    y: {
                        ticks: { callback: v => sym + v.toLocaleString() },
                        grid:  { color: 'rgba(0,0,0,0.05)' },
                    },
                    x: { grid: { display: false } },
                },
            },
        });
    }

    _renderStatusChart(Chart) {
        const canvas = this.statusChartRef.el;
        if (!canvas) return;
        const { draft_count, confirmed_count, partial_count, paid_count } = this.state;
        if (!(draft_count + confirmed_count + partial_count + paid_count)) return;
        this._statusChartInst = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: ['Draft', 'Confirmed', 'Partial', 'Paid'],
                datasets: [{
                    data: [draft_count, confirmed_count, partial_count, paid_count],
                    backgroundColor: [
                        'rgba(255,193,7,0.85)',
                        'rgba(13,110,253,0.85)',
                        'rgba(220,53,69,0.85)',
                        'rgba(25,135,84,0.85)',
                    ],
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '62%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { padding: 10, font: { size: 11 } },
                    },
                    tooltip: {
                        callbacks: {
                            label: ctx => ` ${ctx.label}: ${ctx.parsed}`,
                        },
                    },
                },
            },
        });
    }

    // ── Computed ──────────────────────────────────────────────────────────────
    fmt(val) {
        return (this.state.currency_symbol || '') +
               (val || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }

    get totalPayslips() {
        const s = this.state;
        return (s.draft_count || 0) + (s.confirmed_count || 0) +
               (s.partial_count || 0) + (s.paid_count || 0);
    }

    get coveragePercent() {
        if (!this.state.employees_total) return 0;
        return Math.round((this.state.employees_covered / this.state.employees_total) * 100);
    }

    get groupByLabel() {
        return GROUP_BY_LABELS[this.state.group_by] || 'Group';
    }

    get activeFilterCount() {
        let n = 0;
        if (this.state.department_id) n++;
        if (this.state.employee_type) n++;
        if (this.state.wage_type)     n++;
        if (this.state.state_filter)  n++;
        return n;
    }

    get months() {
        return [
            [1,'January'],[2,'February'],[3,'March'],[4,'April'],
            [5,'May'],[6,'June'],[7,'July'],[8,'August'],
            [9,'September'],[10,'October'],[11,'November'],[12,'December'],
        ];
    }

    get years() {
        const y = new Date().getFullYear();
        return [y - 3, y - 2, y - 1, y, y + 1];
    }

    // ── Event Handlers ────────────────────────────────────────────────────────
    onMonthChange(ev)      { this.state.month         = parseInt(ev.target.value); this._loadData(); }
    onYearChange(ev)       { this.state.year          = parseInt(ev.target.value); this._loadData(); }
    onDeptChange(ev)       { this.state.department_id = ev.target.value ? parseInt(ev.target.value) : false; this._loadData(); }
    onEmpTypeChange(ev)    { this.state.employee_type = ev.target.value; this._loadData(); }
    onWageTypeChange(ev)   { this.state.wage_type     = ev.target.value; this._loadData(); }
    onStateFilterChange(ev){ this.state.state_filter  = ev.target.value; this._loadData(); }
    onGroupByChange(ev)    { this.state.group_by      = ev.target.value; this._loadData(); }

    clearFilters() {
        Object.assign(this.state, {
            department_id: false,
            employee_type: '',
            wage_type:     '',
            state_filter:  '',
        });
        this._loadData();
    }

    // ── Navigation helpers ────────────────────────────────────────────────────
    _monthPrefix() {
        return `${this.state.year}-${String(this.state.month).padStart(2,'0')}-01`;
    }

    _buildDomain(extraFilters) {
        const d = [['date_from', '>=', this._monthPrefix()]];
        if (this.state.department_id) d.push(['department_id', '=', this.state.department_id]);
        if (this.state.employee_type) d.push(['employee_type', '=', this.state.employee_type]);
        if (this.state.wage_type)     d.push(['wage_type',     '=', this.state.wage_type]);
        if (this.state.state_filter)  d.push(['state',         '=', this.state.state_filter]);
        return d.concat(extraFilters || []);
    }

    openPayslips(extraDomain) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'dotbd.payslip',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: this._buildDomain(extraDomain),
        });
    }

    openPayslipsByState(state) {
        this.openPayslips([['state', '=', state]]);
    }

    generatePayslips(context) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'dotbd.payslip.generator.wizard',
            views: [[false, 'form']],
            target: 'new',
            context: context || {},
        });
    }

    generateForDept() {
        if (!this.state.department_id) {
            this.notification.add('Please select a department first.', { type: 'warning' });
            return;
        }
        this.generatePayslips({ default_department_id: this.state.department_id });
    }
}

try {
    registry.category("actions").add("dotbd_payroll_dashboard", PayrollDashboard);
} catch (e) {
    console.error("[dotbd] Failed to register dotbd_payroll_dashboard:", e);
}
