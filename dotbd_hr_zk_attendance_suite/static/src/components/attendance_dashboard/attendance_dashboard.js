/** @odoo-module **/
// ---------------------------------------------------------------------------
//  Dot BD Solutions Limited – Attendance Main Dashboard
//  OWL 2 Component for Odoo 18
// ---------------------------------------------------------------------------
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class AttendanceDashboard extends Component {
    static template = "dotbd_hr_zk_attendance_suite.AttendanceDashboard";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.rpc = useService("rpc");

        const now = new Date();
        this.state = useState({
            loading: true,
            month: now.getMonth() + 1,   // 1-based
            year:  now.getFullYear(),
            department_id: false,
            employee_id:   false,

            departments:   [],
            allEmployees:  [],   // full list, never filtered after init
            employees:     [],   // filtered list shown in dropdown

            today: { total: 0, present: 0, absent: 0, on_leave: 0, late: 0, total_fine: 0.0, currency_symbol: '', late_enabled: false },
            days: [],
            month_name: "",
            calendar: [],

            today_holiday: '',
            upcoming_holidays: [],
            weekend_days: [4, 5],

            selected_employee: null,
            status_filter: null,   // 'present' | 'absent' | 'late' | 'leave' | null
            sort_by: null,         // 'top_present' | 'top_absent' | 'top_late' | 'top_leave' | null
            downloading: false,
            popup: null,           // active cell detail popup
            tolerance_minutes: 0,
        });

        onMounted(() => this._init());
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────
    async _init() {
        const filters = await this.rpc("/attendance/main/dashboard/filters", {});
        this.state.departments  = filters.departments || [];
        this.state.allEmployees = filters.employees   || [];
        this.state.employees    = filters.employees   || [];
        await this._loadData();
    }

    async _loadData() {
        this.state.loading = true;
        try {
            const data = await this.rpc("/attendance/main/dashboard/data", {
                month:         this.state.month,
                year:          this.state.year,
                department_id: this.state.department_id,
                employee_id:   this.state.employee_id,
            });
            this.state.today      = data.today;
            this.state.days       = data.days;
            this.state.month_name = data.month_name;
            this.state.calendar   = data.calendar;
            this.state.today_holiday    = data.today_holiday    || '';
            this.state.upcoming_holidays = data.upcoming_holidays || [];
            this.state.weekend_days     = data.weekend_days     || [4, 5];
            this.state.tolerance_minutes = data.tolerance_minutes || 0;
        } finally {
            this.state.loading = false;
        }
    }

    // ── Greeting ──────────────────────────────────────────────────────────────
    get greeting() {
        const h = new Date().getHours();
        if (h < 12) return "Good Morning";
        if (h < 17) return "Good Afternoon";
        return "Good Evening";
    }

    get todayLabel() {
        return new Date().toLocaleDateString("en-US", {
            weekday: "long", year: "numeric", month: "long", day: "numeric",
        });
    }

    get monthlyPresentCount() {
        return this.state.calendar.filter(r => r.summary.P > 0).length;
    }
    get monthlyAbsentCount() {
        return this.state.calendar.filter(r => r.summary.A > 0).length;
    }
    get monthlyLateCount() {
        return this.state.calendar.filter(r => r.summary.Late > 0).length;
    }
    get monthlyLeaveCount() {
        return this.state.calendar.filter(r => r.summary.L > 0).length;
    }

    // ── Filter handlers ───────────────────────────────────────────────────────
    onDeptChange(ev) {
        const val = ev.target.value;
        this.state.department_id = val ? parseInt(val) : false;
        // Reset employee selection when department changes
        this.state.employee_id = false;
        // Filter employee dropdown to match selected department
        if (!this.state.department_id) {
            this.state.employees = this.state.allEmployees;
        } else if (this.state.department_id === -1) {
            // "Others" — employees with no department
            this.state.employees = this.state.allEmployees.filter(e => !e.department_id);
        } else {
            this.state.employees = this.state.allEmployees.filter(
                e => e.department_id && e.department_id[0] === this.state.department_id
            );
        }
        this._loadData();
    }

    onEmpChange(ev) {
        this.state.employee_id = ev.target.value ? parseInt(ev.target.value) : false;
        this._loadData();
    }

    onMonthChange(ev) {
        this.state.month = parseInt(ev.target.value);
        this._loadData();
    }

    onYearChange(ev) {
        this.state.year = parseInt(ev.target.value);
        this._loadData();
    }

    // ── Status filter + sort ──────────────────────────────────────────────────
    get filteredCalendar() {
        let rows = this.state.calendar;

        // Filter by today's status chip
        const f = this.state.status_filter;
        if (f) {
            rows = rows.filter(row => {
                if (f === 'present') return row.summary.P > 0;
                if (f === 'absent')  return row.summary.A > 0;
                if (f === 'late')    return row.summary.Late > 0;
                if (f === 'leave')   return row.summary.L > 0;
                return true;
            });
        }

        // Sort by top ranking
        const s = this.state.sort_by;
        if (s) {
            const key = s === 'top_present' ? 'P'
                      : s === 'top_absent'  ? 'A'
                      : s === 'top_late'    ? 'Late'
                      : s === 'top_leave'   ? 'L' : null;
            if (key) {
                rows = [...rows].sort((a, b) => b.summary[key] - a.summary[key]);
            }
        }

        return rows;
    }

    onStatusFilter(status) {
        this.state.status_filter = this.state.status_filter === status ? null : status;
        this.state.selected_employee = null;
    }

    onSortBy(sort) {
        this.state.sort_by = this.state.sort_by === sort ? null : sort;
        this.state.selected_employee = null;
    }

    // ── Employee selection ────────────────────────────────────────────────────
    onEmployeeSelect(empRow) {
        if (this.state.selected_employee &&
            this.state.selected_employee.employee_id === empRow.employee_id) {
            this.state.selected_employee = null;  // deselect on second click
        } else {
            this.state.selected_employee = empRow;
        }
    }

    // ── Cell Popup ────────────────────────────────────────────────────────────
    onCellClick(empRow, dayObj) {
        if (!dayObj.cell_text) return;
        const d = dayObj;
        const workedH = Math.floor(d.worked_hours || 0);
        const workedM = Math.round(((d.worked_hours || 0) - workedH) * 60);
        const cellLabels = { 'A': 'Absent', 'W': 'Weekend', 'H': 'Public Holiday' };
        this.state.popup = {
            employee_name: empRow.employee_name,
            date_label: `${d.day_name} ${d.day}`,
            cell_text: d.cell_text,
            check_in: d.check_in || '',
            check_out: d.check_out || '',
            worked_label: d.worked_hours ? `${workedH}h ${workedM.toString().padStart(2, '0')}m` : '—',
            late_minutes: d.late_minutes || 0,
            tolerance: this.state.tolerance_minutes || 0,
            leave_type: d.leave_type || '',
            leave_desc: d.leave_desc || '',
            cell_text_label: cellLabels[d.cell_text] || d.cell_text,
        };
    }

    onPopupClose() {
        this.state.popup = null;
    }

    // ── Download ──────────────────────────────────────────────────────────────
    async onDownloadExcel() {
        // Check if a report generation is already running for this user
        try {
            const status = await this.rpc("/attendance/export/status", {});
            if (status && status.running) {
                this.notification.add(
                    _t("Your attendance report is being processed in the background. Please wait for it to complete before starting a new download."),
                    { type: "warning", title: _t("Download In Progress"), sticky: false }
                );
                return;
            }
        } catch (_e) {
            // If status check fails, allow the user to proceed normally
        }

        this.state.downloading = true;
        try {
            await this.action.doAction({
                type:      "ir.actions.act_window",
                res_model: "employee.attendance.sheet.wizard",
                views:     [[false, "form"]],
                target:    "new",
            });
        } finally {
            this.state.downloading = false;
        }
    }
}

try {
    registry.category("actions").add("attendance_main_dashboard", AttendanceDashboard);
} catch (e) {
    console.error("[dotbd] Failed to register attendance_main_dashboard:", e);
}
