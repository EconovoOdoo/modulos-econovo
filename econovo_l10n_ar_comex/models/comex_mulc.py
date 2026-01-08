# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ComexMulc(models.Model):
    """MULC (Mercado Único y Libre de Cambios) operations for COMEX."""

    _name = 'comex.mulc'
    _description = 'COMEX MULC Operation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )
    operation_id = fields.Many2one(
        'comex.operation',
        string="COMEX Operation",
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        related='operation_id.company_id',
        store=True,
    )

    # MULC details
    mulc_type = fields.Selection(
        selection=[
            ('import_payment', 'Import Payment'),
            ('export_collection', 'Export Collection'),
            ('service_payment', 'Service Payment'),
            ('other', 'Other'),
        ],
        string="MULC Type",
        required=True,
        default='import_payment',
        tracking=True,
    )
    date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    due_date = fields.Date(
        string="Due Date",
        tracking=True,
        help="Date when foreign exchange access expires.",
    )

    # Bank details
    bank_id = fields.Many2one(
        'res.bank',
        string="Bank",
        tracking=True,
    )
    bank_partner_id = fields.Many2one(
        'res.partner',
        string="Bank (Partner)",
        domain="[('is_company', '=', True)]",
        tracking=True,
        help="Bank as a partner for accounting purposes.",
    )
    swift_code = fields.Char(
        string="SWIFT/BIC Code",
        related='bank_id.bic',
    )

    # === INTEGRATION WITH ODOO NATIVE ===
    # Link to payment (for tracking the actual payment made)
    payment_id = fields.Many2one(
        'account.payment',
        string="Payment",
        tracking=True,
        copy=False,
        help="Link to the payment record in Accounting.",
    )
    # Link to vendor bill being paid
    vendor_bill_id = fields.Many2one(
        'account.move',
        string="Vendor Bill",
        domain="[('move_type', '=', 'in_invoice'), ('state', '=', 'posted')]",
        tracking=True,
        copy=False,
        help="The vendor bill being paid through this MULC operation.",
    )

    # Amounts
    currency_id = fields.Many2one(
        'res.currency',
        string="Foreign Currency",
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        tracking=True,
    )
    amount_foreign = fields.Monetary(
        string="Foreign Amount",
        currency_field='currency_id',
        required=True,
        tracking=True,
    )
    # Exchange rate details
    rate_type = fields.Selection(
        selection=[
            ('official', 'Official'),
            ('mep', 'MEP'),
            ('ccl', 'CCL'),
            ('blue', 'Blue'),
            ('other', 'Other'),
        ],
        string="Rate Type",
        default='official',
        tracking=True,
    )
    exchange_rate = fields.Float(
        string="Exchange Rate",
        digits=(16, 6),
        required=True,
        default=1.0,
        tracking=True,
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string="Company Currency",
        default=lambda self: self.env.company.currency_id,
    )
    amount_local = fields.Monetary(
        string="Local Amount",
        compute='_compute_amount_local',
        store=True,
        currency_field='company_currency_id',
    )

    # Regulatory
    boleto_number = fields.Char(
        string="Boleto Number",
        tracking=True,
        help="BCRA forex transaction reference.",
    )
    concept_code = fields.Char(
        string="BCRA Concept Code",
        tracking=True,
        help="BCRA concept code for the transaction.",
    )

    # State
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('requested', 'Requested'),
            ('approved', 'Approved'),
            ('executed', 'Executed'),
            ('cancelled', 'Cancelled'),
        ],
        string="State",
        default='draft',
        tracking=True,
    )

    # Days tracking
    days_since_shipment = fields.Integer(
        string="Days Since Shipment",
        compute='_compute_days',
        help="Days elapsed since goods were shipped.",
    )
    days_to_due = fields.Integer(
        string="Days to Due",
        compute='_compute_days',
        help="Days remaining until forex access expires.",
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('amount_foreign', 'exchange_rate')
    def _compute_amount_local(self):
        for record in self:
            record.amount_local = record.amount_foreign * record.exchange_rate

    @api.depends('operation_id.date_etd', 'due_date')
    def _compute_days(self):
        today = fields.Date.context_today(self)
        for record in self:
            # Days since shipment
            if record.operation_id.date_etd:
                delta = today - record.operation_id.date_etd
                record.days_since_shipment = delta.days
            else:
                record.days_since_shipment = 0
            
            # Days to due
            if record.due_date:
                delta = record.due_date - today
                record.days_to_due = delta.days
            else:
                record.days_to_due = 0

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains('exchange_rate')
    def _check_exchange_rate(self):
        for record in self:
            if record.exchange_rate <= 0:
                raise ValidationError(_("Exchange rate must be greater than zero."))

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('comex.mulc') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_request(self):
        """Request forex access."""
        self.write({'state': 'requested'})

    def action_approve(self):
        """Mark as approved by bank/BCRA."""
        self.write({'state': 'approved'})

    def action_execute(self):
        """Mark forex transaction as executed."""
        self.write({'state': 'executed'})

    def action_cancel(self):
        """Cancel MULC request."""
        self.write({'state': 'cancelled'})

    def action_draft(self):
        """Reset to draft."""
        self.write({'state': 'draft'})
