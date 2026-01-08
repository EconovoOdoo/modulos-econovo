# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ComexCustomsClearance(models.Model):
    """Customs clearance (Despacho de Aduana) for COMEX operations."""

    _name = 'comex.customs.clearance'
    _description = 'COMEX Customs Clearance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_clearance desc, name desc'

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

    # Clearance details
    clearance_type = fields.Selection(
        selection=[
            ('definitive', 'Definitive Import'),
            ('temporary', 'Temporary Import'),
            ('transit', 'Transit'),
            ('export', 'Export'),
        ],
        string="Clearance Type",
        required=True,
        default='definitive',
        tracking=True,
    )
    dispatch_number = fields.Char(
        string="Dispatch Number",
        tracking=True,
        help="Official dispatch number from ARCA (ex-AFIP).",
    )
    date_clearance = fields.Date(
        string="Clearance Date",
        tracking=True,
    )
    date_nationalization = fields.Date(
        string="Nationalization Date",
        tracking=True,
    )

    # Customs location
    customs_office = fields.Char(
        string="Customs Office",
        tracking=True,
        help="ARCA customs office code.",
    )
    fiscal_warehouse_id = fields.Many2one(
        'stock.location',
        string="Fiscal Warehouse",
        domain="[('usage', '=', 'transit')]",
        tracking=True,
    )

    # Amounts
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related='operation_id.currency_id',
    )
    amount_cif = fields.Monetary(
        string="CIF Amount",
        currency_field='currency_id',
        tracking=True,
    )
    amount_duties = fields.Monetary(
        string="Import Duties",
        currency_field='currency_id',
        tracking=True,
    )
    amount_taxes = fields.Monetary(
        string="Taxes (IVA, etc.)",
        currency_field='currency_id',
        tracking=True,
    )
    amount_fees = fields.Monetary(
        string="Other Fees",
        currency_field='currency_id',
        tracking=True,
    )
    amount_total = fields.Monetary(
        string="Total Clearance Cost",
        compute='_compute_amount_total',
        store=True,
        currency_field='currency_id',
    )

    # Documents
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted to ARCA'),
            ('approved', 'Approved'),
            ('paid', 'Paid'),
            ('released', 'Released'),
            ('cancelled', 'Cancelled'),
        ],
        string="State",
        default='draft',
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('amount_duties', 'amount_taxes', 'amount_fees')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = record.amount_duties + record.amount_taxes + record.amount_fees

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('comex.customs.clearance') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_submit(self):
        """Submit clearance to ARCA."""
        self.write({'state': 'submitted'})

    def action_approve(self):
        """Mark clearance as approved."""
        self.write({'state': 'approved'})

    def action_pay(self):
        """Mark duties as paid."""
        self.write({'state': 'paid'})

    def action_release(self):
        """Mark goods as released from customs."""
        self.write({
            'state': 'released',
            'date_nationalization': fields.Date.context_today(self),
        })
        # Update operation nationalization date
        for record in self:
            if record.operation_id and not record.operation_id.date_nationalization:
                record.operation_id.write({
                    'date_nationalization': record.date_nationalization
                })

    def action_cancel(self):
        """Cancel clearance."""
        self.write({'state': 'cancelled'})

    def action_draft(self):
        """Reset to draft."""
        self.write({'state': 'draft'})
