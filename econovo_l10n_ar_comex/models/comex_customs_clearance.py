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
        string="Customs Office (Text)",
    )
    customs_office_id = fields.Many2one(
        'comex.customs.office',
        string="Customs Office",
        tracking=True,
    )
    fiscal_warehouse_id = fields.Many2one(
        'stock.location',
        string="Fiscal Warehouse",
        domain="[('usage', '=', 'transit')]",
        tracking=True,
    )

    # Channel
    channel = fields.Selection(
        selection=[
            ('green', 'Green'),
            ('orange', 'Orange'),
            ('red', 'Red'),
            ('purple', 'Purple'),
        ],
        string="Customs Channel",
        tracking=True,
        help="Inspection channel assigned by customs.",
    )

    # === INTEGRATION WITH ODOO NATIVE ===
    # Link to vendor bill (Despacho de Importación - Document Type 66)
    vendor_bill_id = fields.Many2one(
        'account.move',
        string="Vendor Bill (DI)",
        domain=[('move_type', '=', 'in_invoice'), ('state', '!=', 'cancel')],
        tracking=True,
        copy=False,
        help="Link to the Despacho de Importación (Document Type 66) in Accounting. Preferably use invoices with Document Type 66 (Import Dispatch).",
    )
    # Link to Landed Costs
    landed_cost_id = fields.Many2one(
        'stock.landed.cost',
        string="Landed Cost",
        tracking=True,
        copy=False,
        help="Link to the Landed Cost record for cost distribution.",
    )

    # Amounts - Currency for taxes is always ARS
    currency_ars_id = fields.Many2one(
        'res.currency',
        string="Currency (ARS)",
        default=lambda self: self.env.ref('base.ARS', raise_if_not_found=False),
    )
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
    # Tributes in ARS
    amount_duties = fields.Monetary(
        string="Import Duties (DIE)",
        currency_field='currency_ars_id',
        tracking=True,
        help="Derecho de Importación Extrazona",
    )
    amount_statistics = fields.Monetary(
        string="Statistics Fee",
        currency_field='currency_ars_id',
        tracking=True,
        help="Tasa de Estadística (3%)",
    )
    amount_vat = fields.Monetary(
        string="VAT",
        currency_field='currency_ars_id',
        tracking=True,
    )
    amount_vat_additional = fields.Monetary(
        string="Additional VAT",
        currency_field='currency_ars_id',
        tracking=True,
        help="IVA Adicional",
    )
    amount_income_tax = fields.Monetary(
        string="Income Tax Perception",
        currency_field='currency_ars_id',
        tracking=True,
        help="Percepción de Ganancias",
    )
    amount_gross_income = fields.Monetary(
        string="Gross Income Perception",
        currency_field='currency_ars_id',
        tracking=True,
        help="Percepción de IIBB",
    )
    amount_taxes = fields.Monetary(
        string="Other Taxes",
        currency_field='currency_ars_id',
        tracking=True,
    )
    amount_fees = fields.Monetary(
        string="Other Fees",
        currency_field='currency_ars_id',
        tracking=True,
    )
    amount_total = fields.Monetary(
        string="Total Clearance Cost",
        compute='_compute_amount_total',
        store=True,
        currency_field='currency_ars_id',
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
    @api.depends('amount_duties', 'amount_statistics', 'amount_vat', 'amount_vat_additional',
                 'amount_income_tax', 'amount_gross_income', 'amount_taxes', 'amount_fees')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = (
                record.amount_duties +
                record.amount_statistics +
                record.amount_vat +
                record.amount_vat_additional +
                record.amount_income_tax +
                record.amount_gross_income +
                record.amount_taxes +
                record.amount_fees
            )

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    @api.onchange('operation_id')
    def _onchange_operation_id_vendor_bill_domain(self):
        """Return domain for vendor_bill_id to filter only Document Type 66."""
        domain = [('move_type', '=', 'in_invoice'), ('state', '!=', 'cancel')]
        
        # Check if l10n_latam fields exist
        if hasattr(self.env['account.move'], '_fields') and 'l10n_latam_document_type_id' in self.env['account.move']._fields:
            domain.append(('l10n_latam_document_type_id.code', '=', '66'))
        
        return {'domain': {'vendor_bill_id': domain}}

    @api.onchange('vendor_bill_id')
    def _onchange_vendor_bill_id_dispatch_number(self):
        """Auto-fill dispatch_number from vendor bill document number."""
        if self.vendor_bill_id:
            # Check if l10n_latam_document_number field exists
            if hasattr(self.vendor_bill_id, 'l10n_latam_document_number'):
                doc_number = self.vendor_bill_id.l10n_latam_document_number
                if doc_number:
                    self.dispatch_number = doc_number

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
