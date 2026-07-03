# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
import base64
import io
import calendar
from datetime import date, timedelta

import xlsxwriter
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


# ─────────────────────────────────────────────────────────────────────────────
# PAYSLIP BATCH
# ─────────────────────────────────────────────────────────────────────────────
class DotbdPayslipBatch(models.Model):
    """Groups multiple payslips generated in a single run."""
    _name = 'dotbd.payslip.batch'
    _description = 'Payslip Batch'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'

    name = fields.Char(string='Batch Name', required=True, tracking=True)
    date_from = fields.Date(string='Period Start', required=True)
    date_to = fields.Date(string='Period End', required=True)
    payslip_ids = fields.One2many(
        'dotbd.payslip', 'batch_id', string='Payslips')
    state = fields.Selection([
        ('draft',     'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid',      'Paid'),
    ], default='draft', string='Status', tracking=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # Computed totals
    employee_count = fields.Integer(
        string='Employees', compute='_compute_totals', store=True)
    total_gross = fields.Monetary(
        string='Total Gross', compute='_compute_totals', store=True,
        currency_field='currency_id')
    total_deductions = fields.Monetary(
        string='Total Deductions', compute='_compute_totals', store=True,
        currency_field='currency_id')
    total_net = fields.Monetary(
        string='Total Net', compute='_compute_totals', store=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('payslip_ids.gross_amount',
                 'payslip_ids.total_deductions',
                 'payslip_ids.net_amount')
    def _compute_totals(self):
        for batch in self:
            slips = batch.payslip_ids
            batch.employee_count = len(slips)
            batch.total_gross = sum(slips.mapped('gross_amount'))
            batch.total_deductions = sum(slips.mapped('total_deductions'))
            batch.total_net = sum(slips.mapped('net_amount'))

    def action_confirm(self):
        self.payslip_ids.action_confirm()
        self.write({'state': 'confirmed'})

    def action_mark_paid(self):
        self.payslip_ids.action_mark_paid()
        self.write({'state': 'paid'})

    def action_reset_draft(self):
        self.payslip_ids.action_reset_draft()
        self.write({'state': 'draft'})

    def action_export_excel(self):
        return self.payslip_ids.action_export_batch_excel()


# ─────────────────────────────────────────────────────────────────────────────
# PAYSLIP LINE
# ─────────────────────────────────────────────────────────────────────────────
class DotbdPayslipLine(models.Model):
    """A single earning or deduction line on a payslip."""
    _name = 'dotbd.payslip.line'
    _description = 'Payslip Line'
    _order = 'payslip_id, line_type, sequence, id'

    payslip_id = fields.Many2one(
        'dotbd.payslip', string='Payslip',
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Description', required=True)
    code = fields.Char(string='Code')
    line_type = fields.Selection([
        ('earning',   'Earning'),
        ('deduction', 'Deduction'),
    ], string='Type', required=True)
    amount = fields.Monetary(
        string='Amount', required=True, currency_field='currency_id')
    note = fields.Char(string='Calculation Note')
    currency_id = fields.Many2one(
        related='payslip_id.currency_id', store=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAYSLIP PAYMENT — partial / installment payments
# ─────────────────────────────────────────────────────────────────────────────
class DotbdPayslipPayment(models.Model):
    """Tracks individual payments against a payslip.
    Supports partial / installment payments common in some countries."""
    _name = 'dotbd.payslip.payment'
    _description = 'Payslip Payment'
    _order = 'payment_date desc, id desc'
    _rec_name = 'display_name'

    payslip_id = fields.Many2one(
        'dotbd.payslip', string='Payslip',
        required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(
        related='payslip_id.employee_id', store=True, string='Employee')
    amount = fields.Monetary(
        string='Payment Amount', required=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(
        related='payslip_id.currency_id', store=True)
    payment_date = fields.Date(
        string='Payment Date', required=True,
        default=fields.Date.today)
    payment_method = fields.Selection([
        ('bank',  'Bank Transfer'),
        ('cash',  'Cash'),
        ('check', 'Cheque'),
        ('mobile', 'Mobile Banking'),
        ('other', 'Other'),
    ], string='Payment Method', default='bank', required=True)
    reference = fields.Char(
        string='Reference / Transaction ID',
        help='Bank transaction reference, cheque number, etc.')
    note = fields.Text(string='Notes')

    @api.depends('payslip_id', 'amount', 'payment_date')
    def _compute_display_name(self):
        for rec in self:
            emp = rec.payslip_id.employee_id.name or ''
            amt = f"{rec.amount:,.2f}" if rec.amount else '0'
            date = rec.payment_date or ''
            rec.display_name = f"{emp} – {amt} ({date})"

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(
                    _('Payment amount must be greater than zero.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Auto-update payslip state after payment
        for rec in records:
            rec.payslip_id._update_payment_state()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'amount' in vals:
            for rec in self:
                rec.payslip_id._update_payment_state()
        return res

    def unlink(self):
        payslips = self.mapped('payslip_id')
        res = super().unlink()
        for ps in payslips:
            ps._update_payment_state()
        return res# ─────────────────────────────────────────────────────────────────────────────
# PAYSLIP
# ─────────────────────────────────────────────────────────────────────────────
class DotbdPayslip(models.Model):
    """Monthly salary payslip — standalone, works without hr_payroll."""
    _name = 'dotbd.payslip'
    _description = 'Payslip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, employee_id'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference', readonly=True, default='/', copy=False)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee',
        required=True, ondelete='restrict',
        index=True, tracking=True)
    department_id = fields.Many2one(
        related='employee_id.department_id', store=True, string='Department')
    job_id = fields.Many2one(
        related='employee_id.job_id', store=True, string='Job Position')
    salary_id = fields.Many2one(
        'dotbd.employee.salary', string='Salary Assignment',
        ondelete='restrict')
    template_id = fields.Many2one(
        related='salary_id.template_id', store=True, string='Template')
    batch_id = fields.Many2one(
        'dotbd.payslip.batch', string='Batch', ondelete='set null')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # ── Period ────────────────────────────────────────────────────────────────
    date_from = fields.Date(string='Period Start', required=True)
    date_to = fields.Date(string='Period End', required=True)
    month_label = fields.Char(
        string='Month', compute='_compute_month_label', store=True)

    @api.depends('date_from')
    def _compute_month_label(self):
        for rec in self:
            if rec.date_from:
                rec.month_label = rec.date_from.strftime('%B %Y')
            else:
                rec.month_label = ''

    # ── Employee type / pay category — linked from hr.employee ───────────────
    employee_type = fields.Selection(
        related='employee_id.employee_type', readonly=True, store=True,
        string='Employee Type')
    employee_category_ids = fields.Many2many(
        related='employee_id.category_ids', readonly=True,
        string='Pay Category')

    # ── Wage ──────────────────────────────────────────────────────────────────
    wage_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('daily',   'Daily'),
        ('hourly',  'Hourly'),
        ('fixed',   'Fixed Contract'),
    ], string='Wage Type', default='monthly',
        help='How basic_wage is interpreted (snapshot from template).')
    basic_wage = fields.Monetary(
        string='Basic Wage', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id)

    # ── Lines ─────────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'dotbd.payslip.line', 'payslip_id', string='Payslip Lines')
    earning_line_ids = fields.One2many(
        'dotbd.payslip.line', 'payslip_id', string='Earnings',
        domain=[('line_type', '=', 'earning')])
    deduction_line_ids = fields.One2many(
        'dotbd.payslip.line', 'payslip_id', string='Deductions',
        domain=[('line_type', '=', 'deduction')])

    # ── Computed totals ───────────────────────────────────────────────────────
    gross_amount = fields.Monetary(
        string='Gross', compute='_compute_totals', store=True,
        currency_field='currency_id')
    total_deductions = fields.Monetary(
        string='Total Deductions', compute='_compute_totals', store=True,
        currency_field='currency_id')
    net_amount = fields.Monetary(
        string='Net Salary', compute='_compute_totals', store=True,
        currency_field='currency_id')

    @api.depends('line_ids.amount', 'line_ids.line_type')
    def _compute_totals(self):
        for rec in self:
            earnings = sum(
                l.amount for l in rec.line_ids if l.line_type == 'earning')
            deductions = sum(
                abs(l.amount) for l in rec.line_ids if l.line_type == 'deduction')
            rec.gross_amount = round(earnings, 2)
            rec.total_deductions = round(deductions, 2)
            rec.net_amount = round(earnings - deductions, 2)

    # ── Attendance stats ──────────────────────────────────────────────────────
    manual_override = fields.Boolean(
        string='Manual Override',
        default=False,
        help='When enabled, Recalculate uses the values typed here by HR '
             'instead of re-fetching from the attendance system.')
    total_working_days = fields.Integer(
        string='Total Working Days',
        help='Total business days in this month (excludes weekends and public holidays).')
    attendance_days = fields.Integer(string='Present Days')
    absent_days = fields.Integer(string='Absent Days')
    late_count = fields.Integer(string='Late Count')
    total_late_minutes = fields.Integer(string='Total Late (min)')
    leave_days = fields.Integer(string='Leave Days')
    time_off_days = fields.Float(
        string='Time Off Days', digits=(5, 1),
        help='Approved time-off (leave) days taken in this period.')
    public_holiday_count = fields.Integer(
        string='Public Holidays',
        help='Number of public holidays in this payslip period (informational only).')
    worked_hours = fields.Float(string='Worked Hours', digits=(6, 1))

    # ── Accounting (optional — unlocked when account module is present) ──────
    # If account module is not installed, these fields are non-functional but
    # safe: Odoo logs a warning for the unknown comodel and skips the field.
    # All methods that USE them are guarded with 'account.move' not in self.env.
    journal_id = fields.Many2one(
        'account.journal', string='Salary Journal',
        domain=[('type', '=', 'general')],
        help="Journal for salary accounting entries. Set a default in "
             "Settings → Attendance/Payroll → Payroll Accounting.")
    account_move_id = fields.Many2one(
        'account.move', string='Journal Entry',
        readonly=True, copy=False, ondelete='set null')
    has_accounting = fields.Boolean(
        compute='_compute_has_accounting', store=False,
        help="True when the account module is installed.")

    def _compute_has_accounting(self):
        has_acc = 'account.move' in self.env
        for rec in self:
            rec.has_accounting = has_acc

    # ── State ─────────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',     'Draft'),
        ('confirmed', 'Confirmed'),
        ('partial',   'Partially Paid'),
        ('paid',      'Paid'),
    ], default='draft', string='Status', tracking=True)

    # ── Payments ──────────────────────────────────────────────────────────────
    payment_ids = fields.One2many(
        'dotbd.payslip.payment', 'payslip_id', string='Payments')
    payment_count = fields.Integer(
        string='Payment Count', compute='_compute_payment_info',
        store=True, compute_sudo=True)
    paid_amount = fields.Monetary(
        string='Paid Amount', compute='_compute_payment_info',
        store=True, compute_sudo=True, currency_field='currency_id')
    remaining_amount = fields.Monetary(
        string='Remaining', compute='_compute_payment_info',
        store=True, compute_sudo=True, currency_field='currency_id')

    @api.depends('payment_ids.amount', 'net_amount')
    def _compute_payment_info(self):
        for rec in self:
            total_paid = sum(rec.payment_ids.mapped('amount'))
            rec.payment_count = len(rec.payment_ids)
            rec.paid_amount = round(total_paid, 2)
            rec.remaining_amount = round(max(0, rec.net_amount - total_paid), 2)

    # ── Optional hr_payroll sync ──────────────────────────────────────────────
    hr_payslip_id = fields.Integer(
        string='HR Payslip ID', readonly=True,
        help='ID of the linked hr.payslip record if synced to Odoo Payroll.')

    # ── File attachment for Excel ─────────────────────────────────────────────
    excel_file = fields.Binary(string='Excel File', attachment=True)
    excel_filename = fields.Char(string='Excel Filename')

    # ─────────────────────────────────────────────────────────────────────────
    # ORM
    # ─────────────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'dotbd.payslip') or '/'
        return super().create(vals_list)

    # ─────────────────────────────────────────────────────────────────────────
    # STATE ACTIONS
    # ─────────────────────────────────────────────────────────────────────────
    def action_confirm(self):
        ICP = self.env['ir.config_parameter'].sudo()
        auto_email = ICP.get_param(
            'dotbd_hr_zk_attendance_suite.payslip_auto_email', False)
        template = self.env.ref(
            'dotbd_hr_zk_attendance_suite.email_template_dotbd_payslip',
            raise_if_not_found=False) if auto_email else False

        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec.write({'state': 'confirmed'})
            rec._sync_to_hr_payroll()
            rec._create_salary_journal_entry()
            if template and rec.employee_id.work_email:
                template.send_mail(rec.id, force_send=False)

    def action_mark_paid(self):
        """Mark as fully paid (creates a catch-all payment if none exist)."""
        for rec in self.filtered(lambda r: r.state in ('confirmed', 'partial')):
            if not rec.payment_ids:
                # Create a single full payment
                self.env['dotbd.payslip.payment'].create({
                    'payslip_id': rec.id,
                    'amount': rec.net_amount,
                    'payment_date': fields.Date.today(),
                    'payment_method': 'bank',
                    'note': 'Full payment',
                })
            elif rec.remaining_amount > 0:
                # Pay the remainder
                self.env['dotbd.payslip.payment'].create({
                    'payslip_id': rec.id,
                    'amount': rec.remaining_amount,
                    'payment_date': fields.Date.today(),
                    'payment_method': 'bank',
                    'note': 'Remaining balance',
                })
            rec.write({'state': 'paid'})

    def action_reset_draft(self):
        for rec in self.filtered(lambda r: r.state not in ('paid',)):
            rec._cancel_salary_journal_entry()
            rec.payment_ids.unlink()
            rec.write({'state': 'draft'})

    def action_register_payment(self):
        """Open a quick form to register a partial payment."""
        self.ensure_one()
        if self.state not in ('confirmed', 'partial'):
            raise ValidationError(_('Payments can only be registered on confirmed payslips.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Payment'),
            'res_model': 'dotbd.payslip.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payslip_id': self.id,
                'default_amount': self.remaining_amount,
            },
        }

    def action_view_payments(self):
        """View all payments for this payslip."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payments – %s') % self.employee_id.name,
            'res_model': 'dotbd.payslip.payment',
            'view_mode': 'list,form',
            'domain': [('payslip_id', '=', self.id)],
            'context': {'default_payslip_id': self.id},
        }

    def _update_payment_state(self):
        """Auto-transition state based on payments.
        Called by DotbdPayslipPayment after create/write/unlink."""
        for rec in self:
            if rec.state not in ('confirmed', 'partial', 'paid'):
                continue
            total_paid = sum(rec.payment_ids.mapped('amount'))
            if total_paid <= 0:
                rec.write({'state': 'confirmed'})
            elif total_paid >= rec.net_amount:
                rec.write({'state': 'paid'})
            else:
                rec.write({'state': 'partial'})

    def action_print_payslip(self):
        return self.env.ref(
            'dotbd_hr_zk_attendance_suite.action_report_dotbd_payslip_pdf'
        ).report_action(self)

    def action_send_email(self):
        """Open the email composer pre-filled with the payslip email template."""
        self.ensure_one()
        template = self.env.ref(
            'dotbd_hr_zk_attendance_suite.email_template_dotbd_payslip',
            raise_if_not_found=False)
        ctx = {
            'default_model': self._name,
            'default_res_ids': self.ids,
            'default_use_template': bool(template),
            'default_template_id': template.id if template else False,
            'default_composition_mode': 'comment',
            'force_email': True,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def action_view_journal_entry(self):
        """Open the linked journal entry."""
        self.ensure_one()
        if not self.account_move_id:
            raise UserError(_("No journal entry linked to this payslip."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
        }

    # ── Accounting helpers ────────────────────────────────────────────────────

    def _get_accounting_config(self):
        """Return (journal, expense_account, payable_account, deduction_account)
        from settings. Returns (False, False, False, False) if not configured."""
        ICP = self.env['ir.config_parameter'].sudo()

        def _get_account(param):
            aid = int(ICP.get_param(param, 0) or 0)
            return self.env['account.account'].browse(aid) if aid else False

        def _get_journal(param):
            jid = int(ICP.get_param(param, 0) or 0)
            return self.env['account.journal'].browse(jid) if jid else False

        journal = self.journal_id or _get_journal(
            'dotbd_hr_zk_attendance_suite.salary_journal_id')
        expense_acc = _get_account(
            'dotbd_hr_zk_attendance_suite.salary_expense_account_id')
        payable_acc = _get_account(
            'dotbd_hr_zk_attendance_suite.salary_payable_account_id')
        deduction_acc = _get_account(
            'dotbd_hr_zk_attendance_suite.salary_deduction_account_id')
        return journal, expense_acc, payable_acc, deduction_acc

    def _create_salary_journal_entry(self):
        """Create and post a journal entry for this payslip on confirmation.

        Compatible with:
        • Odoo Community account module
        • Odoo Enterprise account + account_accountant
        • om_account_accountant (community accounting)

        Silent no-op if accounting is not installed OR accounts not configured.

        Entry structure:
          DR  Salary Expense Account      = gross_amount
          CR  Salary Payable Account      = net_amount   (partner = employee)
          CR  Deduction Payable (opt.)    = total_deductions
              — or, if no deduction acct —
          CR  Salary Payable Account      = gross_amount
        """
        if 'account.move' not in self.env:
            return

        self.ensure_one()
        if self.account_move_id:
            return  # Already has an entry

        journal, expense_acc, payable_acc, deduction_acc = \
            self._get_accounting_config()

        if not journal or not expense_acc or not payable_acc:
            return  # Not configured — silent skip

        currency = self.currency_id
        gross = self.gross_amount
        net = self.net_amount
        deductions = self.total_deductions

        # Employee's partner for reconcilable payable lines
        # Works in Community, Enterprise and om_account_accountant
        partner = (
            self.employee_id.address_home_id
            or getattr(self.employee_id, 'partner_id', False)
            or False
        )
        partner_id = partner.id if partner else False

        move_lines = []

        # DR: Salary Expense (no partner needed on expense side)
        move_lines.append((0, 0, {
            'name': _('Salary — %s') % self.name,
            'account_id': expense_acc.id,
            'debit': gross,
            'credit': 0.0,
            'currency_id': currency.id,
        }))

        if deduction_acc and deductions > 0:
            # CR: Net Salary Payable (to employee)
            move_lines.append((0, 0, {
                'name': _('Net Salary Payable — %s') % self.employee_id.name,
                'account_id': payable_acc.id,
                'partner_id': partner_id,
                'debit': 0.0,
                'credit': net,
                'currency_id': currency.id,
            }))
            # CR: Deduction Payable
            move_lines.append((0, 0, {
                'name': _('Salary Deductions — %s') % self.name,
                'account_id': deduction_acc.id,
                'debit': 0.0,
                'credit': deductions,
                'currency_id': currency.id,
            }))
        else:
            # CR: Full gross to Payable
            move_lines.append((0, 0, {
                'name': _('Salary Payable — %s') % self.employee_id.name,
                'account_id': payable_acc.id,
                'partner_id': partner_id,
                'debit': 0.0,
                'credit': gross,
                'currency_id': currency.id,
            }))

        try:
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': self.date_to or fields.Date.today(),
                'ref': '%s — %s' % (self.name, self.employee_id.name),
                'line_ids': move_lines,
            })
            move.action_post()
            self.account_move_id = move
        except Exception as e:
            # Log but do not block payslip confirmation
            self.env.cr.rollback()
            self.message_post(
                body=_('⚠️ Journal entry could not be created: %s', str(e)))

    def _cancel_salary_journal_entry(self):
        """Cancel and unlink the linked journal entry.

        Handles Enterprise locked journals gracefully — if cancellation is
        blocked (e.g. hash-locked journal), logs a note and detaches the link
        so the payslip can still be reset to draft. HR can manually reverse
        the entry in accounting.
        """
        if 'account.move' not in self.env:
            return
        if not self.account_move_id:
            return
        move = self.account_move_id
        self.account_move_id = False  # Detach first

        if move.state == 'posted':
            try:
                move.button_cancel()
            except Exception:
                # Locked journal (Enterprise) — leave the move, just detach
                self.message_post(
                    body=_('Journal entry %s could not be cancelled automatically '
                           '(journal may be locked). Please reverse it manually in Accounting.',
                           move.name))
                return
        if move.state in ('draft', 'cancel'):
            try:
                move.unlink()
            except Exception:
                pass  # Already deleted or protected

    def action_recalculate(self):
        """Recalculate payslip lines (draft only).

        Normal mode (manual_override = False):
            Re-fetches attendance from the system, updates all stats,
            then rebuilds salary lines.

        Manual Override mode (manual_override = True):
            Skips attendance re-fetch entirely. Uses whatever values
            HR has typed in the attendance fields as-is, then rebuilds
            salary lines from those values.
        """
        for rec in self.filtered(lambda r: r.state == 'draft'):
            salary = rec.salary_id
            if not salary:
                continue

            # Always refresh wage from latest contract/template
            rec.basic_wage = salary.basic_wage
            rec.wage_type = salary.template_id.wage_type or 'monthly'

            if rec.manual_override:
                # HR has manually set the attendance fields — use them directly
                att_stats = {
                    'present_days': rec.attendance_days,
                    'absent_days': rec.absent_days,
                    'late_arrivals': rec.late_count,
                    'total_late_minutes': rec.total_late_minutes,
                    'leave_days': rec.leave_days,
                    'total_worked_hours': rec.worked_hours,
                }
            else:
                # Auto mode — pull fresh data from attendance system
                att_stats = rec._fetch_attendance_stats()
                rec._write_attendance_stats(att_stats)

            # Rebuild all salary lines
            rec.line_ids.unlink()
            rec._create_earning_lines(salary.template_id)
            rec._create_deduction_lines(salary.template_id, att_stats)
            rec._create_leave_lines(salary.template_id)
            rec._recalculate_festive_bonus_lines()

    # ─────────────────────────────────────────────────────────────────────────
    # CORE CALCULATION ENGINE
    # ─────────────────────────────────────────────────────────────────────────
    @api.model
    def generate_for_employee(self, employee, date_from, date_to,
                               salary=None, batch=None, template_override=None):
        """
        Generate a single payslip for one employee for a given period.
        Called by the wizard and the cron job.
        template_override: use this template instead of salary.template_id (wizard use).
        Returns the created dotbd.payslip record, or False if skipped.
        """
        # Get active salary assignment
        if not salary:
            salary = self.env['dotbd.employee.salary'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'active'),
            ], limit=1)
        if not salary:
            return False

        # Skip if a confirmed/paid payslip already exists for this period
        existing = self.search([
            ('employee_id', '=', employee.id),
            ('date_from', '=', date_from),
            ('state', 'in', ['confirmed', 'paid']),
        ], limit=1)
        if existing:
            return False

        # Delete any leftover draft for this period so we can regenerate
        draft = self.search([
            ('employee_id', '=', employee.id),
            ('date_from', '=', date_from),
            ('state', '=', 'draft'),
        ])
        draft.unlink()

        # Fetch attendance stats for the period
        att_stats = self._fetch_attendance_stats_for(
            employee, date_from, date_to)

        # Compute calendar-based working days and public holidays
        total_working_days = self._compute_working_days_in_period(
            employee, date_from, date_to)
        public_holidays = self._count_public_holidays(
            employee, date_from, date_to)
        time_off_days = self._count_time_off_days(
            employee, date_from, date_to)

        # Resolve the salary template (override takes priority over salary's own)
        template = template_override or salary.template_id

        # Use the computed basic_wage from the salary assignment,
        # which reads exactly from the active hr.contract (18) or hr.version (19).
        basic_wage = salary.basic_wage

        # Determine wage type from template
        wage_type = template.wage_type if template else 'monthly'

        # Create payslip header
        # Correct absent_days: subtract approved time-off to avoid double-deduction
        # (attendance.summary.analysis may mark a no-punch day as absent even if
        # the employee had a validated hr.leave for that day)
        corrected_absent = max(0, att_stats['absent_days'] - int(time_off_days))

        payslip = self.create({
            'employee_id': employee.id,
            'salary_id': salary.id,
            'date_from': date_from,
            'date_to': date_to,
            'wage_type': wage_type,
            'basic_wage': basic_wage,
            'currency_id': salary.currency_id.id,
            'batch_id': batch.id if batch else False,
            'total_working_days': total_working_days,
            'attendance_days': att_stats['present_days'],
            'absent_days': corrected_absent,
            'late_count': att_stats['late_arrivals'],
            'total_late_minutes': int(att_stats.get('total_late_minutes', 0)),
            'leave_days': att_stats['leave_days'],
            'time_off_days': time_off_days,
            'public_holiday_count': public_holidays,
            'worked_hours': round(att_stats.get('total_worked_hours', 0), 1),
        })

        # Create earning lines
        payslip._create_earning_lines(template)

        # Create deduction lines (stored as negative amounts)
        payslip._create_deduction_lines(template, att_stats)

        # Create leave-based lines (paid leave ignored, unpaid deducted per rule)
        payslip._create_leave_lines(template)

        # Create festive bonus earning lines (if any active bonus rules match)
        payslip._create_festive_bonus_lines()

        return payslip

    @api.model
    def _compute_working_days_in_period(self, employee, date_from, date_to):
        """Count actual business days in the period.
        Uses:
        1. Module weekend settings (from Settings → Attendance) as primary source
        2. Resource calendar attendance lines as secondary source
        3. Mon-Fri as final fallback
        Then subtracts public holidays."""

        # Determine working weekdays via the shared precedence helper:
        #   personal working schedule → company weekend policy (all-unchecked =
        #   7-day week) → default Fri+Sat. Working weekdays = all minus OFF days.
        resource_calendar = (
            employee.resource_calendar_id
            or employee.company_id.resource_calendar_id
        )
        work_weekdays = set(range(7)) - employee._dotbd_weekend_weekdays()

        # Collect public holiday dates from resource.calendar.leaves
        holiday_dates = set()
        # Search for calendar-specific AND global (calendar_id=False) public holidays
        leave_domain = [
            ('resource_id', '=', False),  # global = not employee-specific
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
        ]
        if resource_calendar:
            leave_domain.insert(0, ('calendar_id', 'in', [False, resource_calendar.id]))
        else:
            leave_domain.insert(0, ('calendar_id', '=', False))
        global_leaves = self.env['resource.calendar.leaves'].search(leave_domain)
        for leave in global_leaves:
            d = leave.date_from.date() if hasattr(leave.date_from, 'date') else leave.date_from
            end_d = leave.date_to.date() if hasattr(leave.date_to, 'date') else leave.date_to
            while d <= end_d:
                if date_from <= d <= date_to:
                    holiday_dates.add(d)
                d += timedelta(days=1)

        # Mandatory days (hr.leave.mandatory.day) make a normally-off day a
        # working day for this employee. Public holidays still take precedence.
        mandatory_dates = employee._dotbd_mandatory_dates(date_from, date_to)

        count = 0
        current = date_from
        while current <= date_to:
            is_working = current.weekday() in work_weekdays or current in mandatory_dates
            if is_working and current not in holiday_dates:
                count += 1
            current += timedelta(days=1)
        return count

    @api.model
    def _get_weekend_weekdays(self, icp=None):
        """Read the module's weekend day settings and return a set of weekday
        integers (Monday=0 .. Sunday=6) that are marked as weekends."""
        if icp is None:
            icp = self.env['ir.config_parameter'].sudo()
        mapping = {
            'dotbd_hr_zk_attendance_suite.weekend_mon': 0,
            'dotbd_hr_zk_attendance_suite.weekend_tue': 1,
            'dotbd_hr_zk_attendance_suite.weekend_wed': 2,
            'dotbd_hr_zk_attendance_suite.weekend_thu': 3,
            'dotbd_hr_zk_attendance_suite.weekend_fri': 4,
            'dotbd_hr_zk_attendance_suite.weekend_sat': 5,
            'dotbd_hr_zk_attendance_suite.weekend_sun': 6,
        }
        weekend_set = set()
        for param_key, weekday_int in mapping.items():
            if icp.get_param(param_key, 'False') == 'True':
                weekend_set.add(weekday_int)
        return weekend_set

    @api.model
    def _count_public_holidays(self, employee, date_from, date_to):
        """Count public holidays in the payslip period.
        Includes both calendar-specific and global (calendar_id=False) holidays."""
        resource_calendar = (
            employee.resource_calendar_id
            or employee.company_id.resource_calendar_id
        )
        domain = [
            ('resource_id', '=', False),
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
        ]
        if resource_calendar:
            domain.insert(0, ('calendar_id', 'in', [False, resource_calendar.id]))
        else:
            domain.insert(0, ('calendar_id', '=', False))

        global_leaves = self.env['resource.calendar.leaves'].search(domain)
        # Count actual days (a leave spanning 3 days = 3 holidays)
        count = 0
        for leave in global_leaves:
            d = leave.date_from.date() if hasattr(leave.date_from, 'date') else leave.date_from
            end_d = leave.date_to.date() if hasattr(leave.date_to, 'date') else leave.date_to
            while d <= end_d:
                if date_from <= d <= date_to:
                    count += 1
                d += timedelta(days=1)
        return count

    @api.model
    def _count_time_off_days(self, employee, date_from, date_to):
        """Count approved time-off (hr.leave) days in the period."""
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', employee.id),
            ('date_from', '>=', date_from),
            ('date_from', '<', date_to + timedelta(days=1)),
            ('state', '=', 'validate'),
        ])
        return sum(leaves.mapped('number_of_days'))

    def _fetch_attendance_stats_for(self, employee, date_from, date_to):
        """Pull attendance summary stats for one employee over a period.

        Calls get_attendance_summary() which returns a list of per-day dicts,
        then aggregates into the stats dict the payslip engine expects.
        """
        AttSummary = self.env['attendance.summary.analysis']
        day_records = AttSummary.get_attendance_summary(
            employee_ids=[employee.id],
            start_date=date_from,
            end_date=date_to,
        )

        stats = {
            'present_days': 0,
            'absent_days': 0,
            'late_arrivals': 0,
            'total_late_minutes': 0,
            'leave_days': 0,
            'total_worked_hours': 0,
        }

        for day in day_records:
            status = day.get('status', '')
            if status == 'present':
                stats['present_days'] += 1
                stats['total_worked_hours'] += day.get('worked_hours', 0)
                if day.get('is_late'):
                    stats['late_arrivals'] += 1
                    stats['total_late_minutes'] += day.get('late_minutes', 0)
            elif status == 'absent':
                stats['absent_days'] += 1
            elif status == 'leave':
                stats['leave_days'] += 1
            # weekend / public_holiday are skipped (not working days)

        stats['total_late_minutes'] = int(stats['total_late_minutes'])
        stats['total_worked_hours'] = round(stats['total_worked_hours'], 1)
        return stats

    def _fetch_attendance_stats(self):
        """Pull stats using this payslip's own employee and period."""
        return self._fetch_attendance_stats_for(
            self.employee_id, self.date_from, self.date_to)

    def _write_attendance_stats(self, stats):
        # Compute time_off once; use it to correct absent_days so that approved
        # leave days are not also counted as absences (double-deduction fix)
        time_off = self._count_time_off_days(
            self.employee_id, self.date_from, self.date_to)
        corrected_absent = max(0, stats['absent_days'] - int(time_off))
        self.write({
            'total_working_days': self._compute_working_days_in_period(
                self.employee_id, self.date_from, self.date_to),
            'attendance_days': stats['present_days'],
            'absent_days':     corrected_absent,
            'late_count':      stats['late_arrivals'],
            'total_late_minutes': int(stats.get('total_late_minutes', 0)),
            'leave_days':      stats['leave_days'],
            'time_off_days':   time_off,
            'public_holiday_count': self._count_public_holidays(
                self.employee_id, self.date_from, self.date_to),
            'worked_hours':    round(stats.get('total_worked_hours', 0), 1),
        })

    def _get_effective_basic(self):
        """Return the computed basic salary amount for this payslip.

        For allowance/deduction percentage calculations, we always use the
        actual earned basic — not the raw contract rate:
          • monthly / fixed : basic_wage (monthly rate)
          • daily           : daily_rate × attendance_days
          • hourly          : hourly_rate × worked_hours
        """
        wt = self.wage_type or 'monthly'
        if wt == 'daily':
            return round(self.basic_wage * self.attendance_days, 2)
        elif wt == 'hourly':
            return round(self.basic_wage * self.worked_hours, 2)
        return self.basic_wage  # monthly / fixed

    def _create_earning_lines(self, template):
        """Create earning lines from template components."""
        seq = 10
        wt = self.wage_type or 'monthly'
        symbol = self.currency_id.symbol or ''

        # Compute effective basic (what allowances are based on)
        effective_basic = self._get_effective_basic()

        # Label and note for the Basic Salary line
        if wt == 'daily':
            rate_label = 'Basic Salary (Daily Rate)'
            basic_note = (f"{symbol}{self.basic_wage:,.2f}/day × "
                          f"{self.attendance_days} days = "
                          f"{symbol}{effective_basic:,.2f}")
        elif wt == 'hourly':
            rate_label = 'Basic Salary (Hourly Rate)'
            basic_note = (f"{symbol}{self.basic_wage:,.2f}/hr × "
                          f"{self.worked_hours:.1f} hrs = "
                          f"{symbol}{effective_basic:,.2f}")
        elif wt == 'fixed':
            rate_label = 'Contract Salary (Fixed)'
            basic_note = 'Fixed contract amount'
        else:
            rate_label = 'Basic Salary'
            basic_note = 'Base monthly wage'

        self.env['dotbd.payslip.line'].create({
            'payslip_id': self.id,
            'sequence': seq,
            'name': rate_label,
            'code': 'BASIC',
            'line_type': 'earning',
            'amount': effective_basic,
            'note': basic_note,
        })
        seq += 10

        # Allowances — calculated on effective_basic (not the raw rate)
        for comp in template.component_ids.filtered(
                lambda c: c.active and c.component_type != 'deduction'):
            amount = comp.get_amount(effective_basic,
                                     attendance_days=self.attendance_days)
            if amount <= 0:
                continue
            if comp.calculation_type == 'percentage':
                note = (f"{comp.percentage:.0f}% of "
                        f"{symbol}{effective_basic:,.2f} = "
                        f"{symbol}{amount:,.2f}")
            elif comp.calculation_type == 'per_working_day':
                note = (f"{symbol}{comp.daily_amount:,.2f}/day × "
                        f"{self.attendance_days} days = "
                        f"{symbol}{amount:,.2f}")
            else:
                note = 'Fixed amount'

            if comp.show_in_payslip:
                self.env['dotbd.payslip.line'].create({
                    'payslip_id': self.id,
                    'sequence': seq,
                    'name': comp.name,
                    'code': comp.code,
                    'line_type': 'earning',
                    'amount': amount,
                    'note': note,
                })
            else:
                # Company provides benefit physically — deduct cash equivalent
                self.env['dotbd.payslip.line'].create({
                    'payslip_id': self.id,
                    'sequence': seq,
                    'name': comp.name,
                    'code': comp.code,
                    'line_type': 'deduction',
                    'amount': -abs(amount),
                    'note': f'Provided in kind — {note}',
                })
            seq += 10

    def _create_deduction_lines(self, template, att_stats):
        """Create deduction lines from template deduction components + fine rules.
        Amounts are stored as NEGATIVE values for proper display."""
        seq = 10

        # 1. Template deduction components (e.g. Provident Fund, Income Tax)
        #    Use effective_basic so percentages are on earned amount, not raw rate
        effective_basic = self._get_effective_basic()
        symbol = self.currency_id.symbol or ''
        for comp in template.component_ids.filtered(
                lambda c: c.active and c.component_type == 'deduction'):
            amount = comp.get_amount(effective_basic,
                                     attendance_days=self.attendance_days)
            if amount <= 0:
                continue
            if comp.calculation_type == 'percentage':
                note = (f"{comp.percentage:.0f}% of "
                        f"{symbol}{effective_basic:,.2f} = "
                        f"{symbol}{amount:,.2f}")
            else:
                note = 'Fixed deduction'
            self.env['dotbd.payslip.line'].create({
                'payslip_id': self.id,
                'sequence': seq,
                'name': comp.name,
                'code': comp.code,
                'line_type': 'deduction',
                'amount': -abs(amount),
                'note': note,
            })
            seq += 10

        # 2. Attendance-based fine rules (late arrival, absent day fines)
        #    Use self.absent_days (already corrected for approved time-off) rather
        #    than the raw att_stats value — prevents double-deduction when an
        #    employee has an approved hr.leave but no biometric punch on that day.
        late_count = att_stats.get('late_arrivals', 0)
        absent_days = int(self.absent_days or 0)
        total_late_minutes = int(self.total_late_minutes)

        for rule in template.fine_rule_ids.filtered('active'):
            amount, note = rule.compute_deduction(
                late_count, absent_days, total_late_minutes)
            if amount <= 0:
                continue
            self.env['dotbd.payslip.line'].create({
                'payslip_id': self.id,
                'sequence': seq,
                'name': rule.name,
                'code': f'DED_{rule.rule_type.upper()}',
                'line_type': 'deduction',
                'amount': -abs(amount),
                'note': note,
            })
            seq += 10

        # 3. Absence fine (from Settings, independent of template)
        #    Skip for fixed-contract employees (they get paid full amount)
        if (self.wage_type or 'monthly') == 'fixed':
            return
        ICP = self.env['ir.config_parameter'].sudo()
        enable_absence_fine = ICP.get_param(
            'dotbd_hr_zk_attendance_suite.enable_absence_fine', 'False')
        if enable_absence_fine == 'True' and absent_days > 0:
            fine_per_day = float(ICP.get_param(
                'dotbd_hr_zk_attendance_suite.absence_fine_amount', '0'))
            if fine_per_day <= 0 and self.total_working_days > 0:
                # Auto-calculate: daily wage = basic_wage / total_working_days
                fine_per_day = self.basic_wage / self.total_working_days
            if fine_per_day > 0:
                absence_amount = fine_per_day * absent_days
                symbol = self.currency_id.symbol or ''
                self.env['dotbd.payslip.line'].create({
                    'payslip_id': self.id,
                    'sequence': seq,
                    'name': 'Absence Fine',
                    'code': 'DED_ABSENCE',
                    'line_type': 'deduction',
                    'amount': -abs(absence_amount),
                    'note': (f"{absent_days} absent day(s) × "
                             f"{symbol}{fine_per_day:,.2f}/day = "
                             f"{symbol}{absence_amount:,.2f}"),
                })
                seq += 10

    def _create_leave_lines(self, template):
        """
        Create payslip lines for leave-based deductions or additions.
        Queries validated hr.leave records for this employee's period,
        matches each leave type against the template's leave rules,
        and creates payslip lines accordingly.
        Paid leaves (rule_action='ignore') generate no line.
        """
        active_rules = template.leave_rule_ids.filtered('active').sorted('sequence')
        if not active_rules:
            return

        # Fetch validated leave requests for this employee in the payslip period
        leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '>=', self.date_from),
            ('date_from', '<', self.date_to + timedelta(days=1)),
            ('state', '=', 'validate'),
        ])

        # Build {leave_type_id: total_days} from actual leave records
        type_days = {}
        for leave in leaves:
            lt_id = leave.holiday_status_id.id
            type_days[lt_id] = type_days.get(lt_id, 0.0) + leave.number_of_days

        # Gross at this point (after earning lines were already created)
        gross = sum(l.amount for l in self.line_ids if l.line_type == 'earning')
        if not gross:
            gross = self.basic_wage

        working_days = template.working_days_per_month or 26
        matched_type_ids = set()
        seq = 200  # leave lines come after fine/deduction lines

        for rule in active_rules:
            if rule.leave_type_id:
                days = type_days.get(rule.leave_type_id.id, 0.0)
                matched_type_ids.add(rule.leave_type_id.id)
            else:
                # Catch-all: days from leave types not matched by any specific rule
                matched_days = sum(v for k, v in type_days.items()
                                   if k in matched_type_ids)
                days = max(0.0, self.leave_days - matched_days)

            # Mark as matched regardless of rule_action so other catch-alls
            # don't double-count
            if rule.leave_type_id:
                matched_type_ids.add(rule.leave_type_id.id)

            if rule.rule_action == 'ignore' or days <= 0:
                continue

            # ── deduct_if_exceeded: fine only for days beyond the limit ─────
            if rule.rule_action == 'deduct_if_exceeded':
                symbol = self.currency_id.symbol or ''
                if rule.threshold_type == 'monthly_limit':
                    # Simple monthly cap — no HR allocation lookup needed
                    free_days = rule.monthly_threshold or 0
                    excess_days = max(0.0, days - free_days)
                    if excess_days <= 0:
                        continue
                    amount = rule.compute_amount(
                        self.basic_wage, gross, excess_days, working_days)
                    if amount <= 0:
                        continue
                    rate = amount / excess_days if excess_days else 0
                    note = (f"Monthly limit: {days:.1f} taken, "
                            f"{free_days} free → "
                            f"{excess_days:.1f} excess day(s) × "
                            f"{symbol}{rate:,.2f}/day = {symbol}{amount:,.2f}")
                else:
                    # HR allocation balance
                    if not rule.leave_type_id:
                        continue  # allocation check requires a specific leave type
                    allocations = self.env['hr.leave.allocation'].search([
                        ('employee_id', '=', self.employee_id.id),
                        ('holiday_status_id', '=', rule.leave_type_id.id),
                        ('state', '=', 'validate'),
                        '|',
                        ('date_to', '=', False),
                        ('date_to', '>=', self.date_from),
                    ])
                    allocated_days = sum(a.number_of_days for a in allocations)
                    excess_days = max(0.0, days - allocated_days)
                    if excess_days <= 0:
                        continue
                    amount = rule.compute_amount(
                        self.basic_wage, gross, excess_days, working_days)
                    if amount <= 0:
                        continue
                    rate = amount / excess_days if excess_days else 0
                    note = (f"Allocation exceeded: {days:.1f} taken, "
                            f"{allocated_days:.1f} allocated → "
                            f"{excess_days:.1f} excess day(s) × "
                            f"{symbol}{rate:,.2f}/day = {symbol}{amount:,.2f}")
                self.env['dotbd.payslip.line'].create({
                    'payslip_id': self.id,
                    'sequence': seq,
                    'name': rule.name,
                    'code': f'LV{rule.id}',
                    'line_type': 'deduction',
                    'amount': -abs(amount),
                    'note': note,
                })
                seq += 10
                continue

            amount = rule.compute_amount(
                self.basic_wage, gross, days, working_days)
            if amount <= 0:
                continue

            line_type = 'deduction' if rule.rule_action == 'deduct' else 'earning'
            symbol = self.currency_id.symbol or ''
            note = (f"{days:.1f} day(s) — {symbol}{amount / days:,.2f}/day"
                    if days else f"{symbol}{amount:,.2f}")

            # Deductions stored as negative amounts
            final_amount = -abs(amount) if line_type == 'deduction' else amount

            self.env['dotbd.payslip.line'].create({
                'payslip_id': self.id,
                'sequence': seq,
                'name': rule.name,
                'code': f'LV{rule.id}',
                'line_type': line_type,
                'amount': final_amount,
                'note': note,
            })
            seq += 10

    # ─────────────────────────────────────────────────────────────────────────
    # FESTIVE BONUS LINES
    # ─────────────────────────────────────────────────────────────────────────
    def _create_festive_bonus_lines(self):
        """Create earning lines for every active festive bonus matching this
        payslip's employee or salary template.

        Each bonus that matches creates a single earning line with
        ``note='Festive Bonus'`` so it can be identified and recalculated
        later without interfering with other earning lines.
        """
        bonuses = self.env['dotbd.festive.bonus'].with_context(
            active_test=True).search([('active', '=', True)])
        if not bonuses:
            return

        seq = 500  # festive bonus lines come after leave lines (seq 200+)
        symbol = self.currency_id.symbol or ''

        for bonus in bonuses:
            # ── Check eligibility ───────────────────────────────────────
            if bonus.apply_to == 'template':
                template = self.template_id or (
                    self.salary_id.template_id if self.salary_id else False)
                if not template or template not in bonus.salary_template_ids:
                    continue
            elif bonus.apply_to == 'employee':
                if self.employee_id not in bonus.employee_ids:
                    continue

            # ── Compute bonus amount ────────────────────────────────────
            amount = 0.0
            note_detail = ''
            if bonus.bonus_type == 'percentage_wages':
                base = self.basic_wage or 0.0
                amount = round(bonus.percentage / 100.0 * base, 2)
                note_detail = (
                    f"{bonus.percentage:.2f}% of Basic "
                    f"{symbol}{base:,.2f} = {symbol}{amount:,.2f}")
            elif bonus.bonus_type == 'percentage_gross':
                # Use sum of existing earning lines if gross_amount not yet
                # stored (computed field may not be flushed yet)
                gross = self.gross_amount or sum(
                    l.amount for l in self.line_ids
                    if l.line_type == 'earning')
                amount = round(bonus.percentage / 100.0 * gross, 2)
                note_detail = (
                    f"{bonus.percentage:.2f}% of Gross "
                    f"{symbol}{gross:,.2f} = {symbol}{amount:,.2f}")
            elif bonus.bonus_type == 'percentage_net':
                gross = self.gross_amount or sum(
                    l.amount for l in self.line_ids
                    if l.line_type == 'earning')
                deductions = self.total_deductions or sum(
                    abs(l.amount) for l in self.line_ids
                    if l.line_type == 'deduction')
                net_base = max(0, gross - deductions)
                amount = round(bonus.percentage / 100.0 * net_base, 2)
                note_detail = (
                    f"{bonus.percentage:.2f}% of Net "
                    f"{symbol}{net_base:,.2f} = {symbol}{amount:,.2f}")
            elif bonus.bonus_type == 'fixed':
                amount = round(bonus.fixed_amount, 2)
                note_detail = f"Fixed {symbol}{amount:,.2f}"

            if amount <= 0:
                continue

            self.env['dotbd.payslip.line'].create({
                'payslip_id': self.id,
                'sequence': seq,
                'name': bonus.name,
                'code': f'FBONUS{bonus.id}',
                'line_type': 'earning',
                'amount': amount,
                'note': 'Festive Bonus',
            })
            seq += 10

    def _recalculate_festive_bonus_lines(self):
        """Remove existing festive bonus lines and re-create them."""
        for rec in self:
            existing = rec.line_ids.filtered(
                lambda l: l.note == 'Festive Bonus')
            existing.unlink()
            rec._create_festive_bonus_lines()

    # ─────────────────────────────────────────────────────────────────────────
    # AUTO MONTHLY CRON
    # ─────────────────────────────────────────────────────────────────────────
    @api.model
    def _cron_generate_monthly_payslips(self):
        """
        Runs on the 1st of every month.
        Generates payslips for last month for all employees
        with an active salary assignment.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        if not ICP.get_param(
                'dotbd_hr_zk_attendance_suite.enable_auto_payslip', False):
            return

        today = fields.Date.today()
        last_month_end = today.replace(day=1) - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        month_label = last_month_start.strftime('%B %Y')

        # Create a batch for this run
        batch = self.env['dotbd.payslip.batch'].create({
            'name': f'Auto Payroll – {month_label}',
            'date_from': last_month_start,
            'date_to': last_month_end,
        })

        assignments = self.env['dotbd.employee.salary'].search([
            ('state', '=', 'active'),
        ])

        generated, skipped, errors = 0, 0, []

        for assignment in assignments:
            try:
                result = self.generate_for_employee(
                    employee=assignment.employee_id,
                    date_from=last_month_start,
                    date_to=last_month_end,
                    salary=assignment,
                    batch=batch,
                )
                if result:
                    generated += 1
                else:
                    skipped += 1
            except Exception as e:
                errors.append(f"{assignment.employee_id.name}: {e}")

        # Log result on the batch
        msg = (f"Auto-generation complete: "
               f"{generated} generated, {skipped} skipped.")
        if errors:
            msg += f"\nErrors ({len(errors)}):\n" + '\n'.join(errors)
        batch.message_post(body=msg)

        # Notify HR manager if configured
        if ICP.get_param(
                'dotbd_hr_zk_attendance_suite.payslip_notify_hr', False):
            self._notify_hr_manager(batch, generated, skipped, errors)

        return batch

    def _notify_hr_manager(self, batch, generated, skipped, errors):
        """Send an internal note to HR managers about the auto-generation result."""
        hr_group = self.env.ref(
            'dotbd_hr_zk_attendance_suite.group_attendance_manager',
            raise_if_not_found=False)
        if not hr_group:
            return
        partners = hr_group.users.mapped('partner_id')
        if not partners:
            return
        subject = f"Monthly Payroll Generated – {batch.name}"
        body = (f"<p>{generated} payslips generated successfully for "
                f"<b>{batch.name}</b>.</p>"
                f"<p>Skipped: {skipped}</p>")
        if errors:
            body += ("<p style='color:red;'>Errors:<br/>"
                     + '<br/>'.join(errors) + '</p>')
        batch.message_post(
            body=body, subject=subject,
            partner_ids=partners.ids,
            message_type='email',
            subtype_xmlid='mail.mt_comment')

    # ─────────────────────────────────────────────────────────────────────────
    # HR_PAYROLL SYNC (bonus — silent if not installed)
    # ─────────────────────────────────────────────────────────────────────────
    def _sync_to_hr_payroll(self):
        """
        If hr_payroll or hr_payroll_community is installed AND sync is enabled
        in Settings, push our total deduction to their payslip input lines.
        Called automatically on confirm.
        """
        if 'hr.payslip' not in self.env:
            return
        ICP = self.env['ir.config_parameter'].sudo()
        if not ICP.get_param(
                'dotbd_hr_zk_attendance_suite.enable_hr_payroll_sync', False):
            return
        if self.total_deductions <= 0:
            return

        HrPayslip = self.env['hr.payslip']
        their_slip = HrPayslip.search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '=', self.date_from),
            ('state', 'not in', ['done', 'paid', 'cancel']),
        ], limit=1)

        if not their_slip:
            return

        their_slip.write({
            'input_line_ids': [(0, 0, {
                'name': 'ZK Attendance Deduction',
                'code': 'ZK_DED',
                'amount': self.total_deductions,
            })]
        })
        self.write({'hr_payslip_id': their_slip.id})

    # ─────────────────────────────────────────────────────────────────────────
    # EXCEL EXPORT
    # ─────────────────────────────────────────────────────────────────────────
    def action_export_excel(self):
        """Export this single payslip as Excel."""
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        self._write_payslip_to_excel(workbook, self)
        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        filename = f'Payslip_{self.employee_id.name}_{self.month_label}.xlsx'
        self.write({'excel_file': file_data, 'excel_filename': filename})

        return {
            'type': 'ir.actions.act_url',
            'url': (f'/web/content/{self._name}/{self.id}'
                    f'/excel_file/{filename}?download=true'),
            'target': 'self',
        }

    def action_export_batch_excel(self):
        """Export all payslips in this batch as one Excel file."""
        if not self:
            raise UserError('No payslips to export.')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Summary sheet
        self._write_summary_sheet(workbook)

        # Individual sheet per employee
        for slip in self.sorted(lambda s: s.employee_id.name):
            self._write_payslip_to_excel(workbook, slip)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        # Use first slip's batch or period label
        first = self[0]
        label = first.batch_id.name if first.batch_id else first.month_label
        filename = f'Payroll_{label}.xlsx'

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': file_data,
            'res_model': self._name,
            'res_id': self[0].id,
            'mimetype': ('application/vnd.openxmlformats-officedocument'
                         '.spreadsheetml.sheet'),
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}/{filename}?download=true',
            'target': 'self',
        }

    def _write_summary_sheet(self, workbook):
        """Write a summary sheet with all employees on one page."""
        bold = workbook.add_format({'bold': True})
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#875A7B', 'font_color': '#ffffff',
            'border': 1, 'align': 'center'})
        money_fmt = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        cell_fmt = workbook.add_format({'border': 1})
        total_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#f0f0f0',
            'num_format': '#,##0.00', 'border': 1})

        paid_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#d1fae5', 'font_color': '#065f46',
            'num_format': '#,##0.00', 'border': 1})
        remain_fmt = workbook.add_format({
            'bg_color': '#fff7ed', 'font_color': '#c2410c',
            'num_format': '#,##0.00', 'border': 1})
        state_draft_fmt = workbook.add_format({
            'bg_color': '#e9ecef', 'font_color': '#495057', 'border': 1, 'align': 'center'})
        state_conf_fmt = workbook.add_format({
            'bg_color': '#dbeafe', 'font_color': '#1d4ed8', 'border': 1, 'align': 'center'})
        state_part_fmt = workbook.add_format({
            'bg_color': '#fff3cd', 'font_color': '#92400e', 'border': 1, 'align': 'center'})
        state_paid_fmt = workbook.add_format({
            'bg_color': '#d1fae5', 'font_color': '#065f46', 'border': 1, 'align': 'center'})

        ws = workbook.add_worksheet('Summary')
        ws.set_column(0, 0, 30)
        ws.set_column(1, 1, 22)
        ws.set_column(2, 14, 14)

        # Title
        first = self[0]
        label = first.batch_id.name if first.batch_id else first.month_label
        ws.merge_range('A1:O1', f'Payroll Summary – {label}', bold)

        # Headers
        headers = [
            'Employee', 'Department', 'Basic', 'Gross',
            'Late (min)', 'Late Fine', 'Absent', 'Absent Fine',
            'Total Deductions', 'Net Salary',
            'Paid Amount', 'Remaining', 'Status',
            'Present', 'Leave',
        ]
        for col, h in enumerate(headers):
            ws.write(2, col, h, header_fmt)

        # Data rows
        row = 3
        state_fmt_map = {
            'draft': state_draft_fmt, 'confirmed': state_conf_fmt,
            'partial': state_part_fmt, 'paid': state_paid_fmt,
        }
        for slip in self.sorted(lambda s: s.employee_id.name):
            late_fine = sum(
                l.amount for l in slip.line_ids
                if l.line_type == 'deduction'
                and 'LATE' in (l.code or '').upper())
            absent_fine = sum(
                l.amount for l in slip.line_ids
                if l.line_type == 'deduction'
                and 'ABSENT' in (l.code or '').upper())
            sfmt = state_fmt_map.get(slip.state, cell_fmt)
            ws.write(row, 0,  slip.employee_id.name, cell_fmt)
            ws.write(row, 1,  slip.department_id.name or '', cell_fmt)
            ws.write(row, 2,  slip.basic_wage, money_fmt)
            ws.write(row, 3,  slip.gross_amount, money_fmt)
            ws.write(row, 4,  slip.total_late_minutes, cell_fmt)
            ws.write(row, 5,  late_fine, money_fmt)
            ws.write(row, 6,  slip.absent_days, cell_fmt)
            ws.write(row, 7,  absent_fine, money_fmt)
            ws.write(row, 8,  slip.total_deductions, money_fmt)
            ws.write(row, 9,  slip.net_amount, money_fmt)
            ws.write(row, 10, slip.paid_amount, paid_fmt)
            ws.write(row, 11, slip.remaining_amount, remain_fmt if slip.remaining_amount > 0 else paid_fmt)
            ws.write(row, 12, slip.state.upper(), sfmt)
            ws.write(row, 13, slip.attendance_days, cell_fmt)
            ws.write(row, 14, slip.leave_days, cell_fmt)
            row += 1

        # Totals row
        ws.write(row, 0, 'TOTAL', total_fmt)
        ws.write(row, 1, '', total_fmt)
        ws.write(row, 2, sum(self.mapped('basic_wage')), total_fmt)
        ws.write(row, 3, sum(self.mapped('gross_amount')), total_fmt)
        ws.write(row, 4, sum(self.mapped('total_late_minutes')), total_fmt)
        ws.write(row, 5, '', total_fmt)
        ws.write(row, 6, sum(self.mapped('absent_days')), total_fmt)
        ws.write(row, 7, '', total_fmt)
        ws.write(row, 8, sum(self.mapped('total_deductions')), total_fmt)
        ws.write(row, 9, sum(self.mapped('net_amount')), total_fmt)
        ws.write(row, 10, sum(self.mapped('paid_amount')), total_fmt)
        ws.write(row, 11, sum(self.mapped('remaining_amount')), total_fmt)
        for col in range(12, 15):
            ws.write(row, col, '', total_fmt)

    def _write_payslip_to_excel(self, workbook, slip):
        """Write a single payslip to its own sheet."""
        bold = workbook.add_format({'bold': True})
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14,
            'bg_color': '#875A7B', 'font_color': '#ffffff',
            'align': 'center'})
        label_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#f8f9fa', 'border': 1})
        earn_hdr = workbook.add_format({
            'bold': True, 'bg_color': '#d4edda', 'border': 1})
        ded_hdr = workbook.add_format({
            'bold': True, 'bg_color': '#f8d7da', 'border': 1})
        money_fmt = workbook.add_format({
            'num_format': '#,##0.00', 'border': 1})
        cell_fmt = workbook.add_format({'border': 1})
        net_fmt = workbook.add_format({
            'bold': True, 'font_size': 12,
            'bg_color': '#cce5ff', 'num_format': '#,##0.00',
            'border': 2, 'align': 'center'})

        # Sheet name: first 31 chars of employee name
        sheet_name = slip.employee_id.name[:28] if slip.employee_id else 'Payslip'
        ws = workbook.add_worksheet(sheet_name)
        ws.set_column(0, 0, 28)
        ws.set_column(1, 1, 16)
        ws.set_column(2, 2, 28)
        ws.set_column(3, 3, 16)

        # Title
        ws.merge_range('A1:D1', f'SALARY PAYSLIP – {slip.month_label}', title_fmt)

        # Employee details
        row = 1
        details = [
            ('Employee', slip.employee_id.name),
            ('Department', slip.department_id.name or ''),
            ('Job Position', slip.job_id.name or ''),
            ('Period', f"{slip.date_from} to {slip.date_to}"),
        ]
        for label, value in details:
            ws.write(row, 0, label, label_fmt)
            ws.write(row, 1, value, cell_fmt)
            row += 1

        row += 1  # blank row

        # Earnings / Deductions headers
        ws.write(row, 0, 'EARNINGS', earn_hdr)
        ws.write(row, 1, 'Amount', earn_hdr)
        ws.write(row, 2, 'DEDUCTIONS', ded_hdr)
        ws.write(row, 3, 'Amount', ded_hdr)
        row += 1

        earnings = [l for l in slip.line_ids if l.line_type == 'earning']
        deductions = [l for l in slip.line_ids if l.line_type == 'deduction']
        max_rows = max(len(earnings), len(deductions), 1)

        for i in range(max_rows):
            e = earnings[i] if i < len(earnings) else None
            d = deductions[i] if i < len(deductions) else None
            ws.write(row, 0, e.name if e else '', cell_fmt)
            ws.write(row, 1, e.amount if e else '', money_fmt)
            ws.write(row, 2, d.name if d else '', cell_fmt)
            ws.write(row, 3, d.amount if d else '', money_fmt)
            row += 1

        # Subtotals
        ws.write(row, 0, 'Gross Total', label_fmt)
        ws.write(row, 1, slip.gross_amount, money_fmt)
        ws.write(row, 2, 'Total Deductions', label_fmt)
        ws.write(row, 3, slip.total_deductions, money_fmt)
        row += 2

        # Net salary
        ws.merge_range(row, 0, row, 1, 'NET SALARY', label_fmt)
        ws.merge_range(row, 2, row, 3, slip.net_amount, net_fmt)
        row += 2

        # Attendance summary
        ws.write(row, 0, 'Attendance Summary', bold)
        row += 1
        att_data = [
            ('Present Days', slip.attendance_days),
            ('Absent Days', slip.absent_days),
            ('Late Count', slip.late_count),
            ('Total Late (min)', slip.total_late_minutes),
            ('Leave Days', slip.leave_days),
            ('Worked Hours', slip.worked_hours),
        ]
        for label, value in att_data:
            ws.write(row, 0, label, label_fmt)
            ws.write(row, 1, value, cell_fmt)
            row += 1

        row += 1  # blank row

        # ── Payment History ──────────────────────────────────────────────────
        pmt_title_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1e3a5f', 'font_color': '#ffffff',
            'border': 1})
        pmt_hdr_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#334155', 'font_color': '#ffffff',
            'border': 1})
        pmt_paid_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#d1fae5', 'font_color': '#065f46',
            'num_format': '#,##0.00', 'border': 1})
        pmt_remain_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#fff7ed', 'font_color': '#c2410c',
            'num_format': '#,##0.00', 'border': 1})
        pmt_cell_fmt = workbook.add_format({'border': 1})
        pmt_money_fmt = workbook.add_format({
            'num_format': '#,##0.00', 'border': 1, 'font_color': '#166534'})
        date_fmt = workbook.add_format({'border': 1, 'num_format': 'dd-mmm-yyyy'})

        ws.merge_range(row, 0, row, 3, 'PAYMENT HISTORY', pmt_title_fmt)
        row += 1

        if slip.payment_ids:
            # Column headers
            ws.write(row, 0, 'Date', pmt_hdr_fmt)
            ws.write(row, 1, 'Method', pmt_hdr_fmt)
            ws.write(row, 2, 'Reference', pmt_hdr_fmt)
            ws.write(row, 3, 'Amount', pmt_hdr_fmt)
            row += 1

            pmt_method_labels = dict(
                slip.payment_ids[0].fields_get(
                    allfields=['payment_method'])['payment_method']['selection']
            )
            for pmt in slip.payment_ids:
                ws.write(row, 0, str(pmt.payment_date), pmt_cell_fmt)
                ws.write(row, 1, pmt_method_labels.get(pmt.payment_method, pmt.payment_method), pmt_cell_fmt)
                ws.write(row, 2, pmt.reference or '', pmt_cell_fmt)
                ws.write(row, 3, pmt.amount, pmt_money_fmt)
                row += 1

            # Total paid
            ws.merge_range(row, 0, row, 2, 'Total Paid', pmt_hdr_fmt)
            ws.write(row, 3, slip.paid_amount, pmt_paid_fmt)
            row += 1

            # Remaining balance
            ws.merge_range(row, 0, row, 2, 'Remaining Balance', pmt_hdr_fmt)
            if slip.remaining_amount > 0:
                ws.write(row, 3, slip.remaining_amount, pmt_remain_fmt)
            else:
                paid_full_fmt = workbook.add_format({
                    'bold': True, 'bg_color': '#d1fae5', 'font_color': '#065f46',
                    'border': 1})
                ws.write(row, 3, 'Paid in Full', paid_full_fmt)
            row += 1
        else:
            # No payments yet — show net payable as pending
            ws.write(row, 0, 'Status', pmt_hdr_fmt)
            ws.merge_range(row, 1, row, 3, 'No payment recorded', pmt_cell_fmt)
            row += 1
            ws.write(row, 0, 'Net Payable', pmt_hdr_fmt)
            ws.merge_range(row, 1, row, 3, slip.net_amount, pmt_remain_fmt)
            row += 1
