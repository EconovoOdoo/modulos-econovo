# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ComexOperation(models.Model):
    """Main model for COMEX (foreign trade) operations."""

    _name = 'comex.operation'
    _description = 'COMEX Operation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_operation desc, name desc'

    # -------------------------------------------------------------------------
    # DEFAULT METHODS
    # -------------------------------------------------------------------------
    def _default_stage(self):
        """Get default stage based on operation type from context."""
        operation_type = self.env.context.get('default_operation_type', 'import')
        return self.env['comex.operation.stage'].get_default_stage(operation_type)

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default='/',
        tracking=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    operation_type = fields.Selection(
        selection=[
            ('import', 'Import'),
            ('export', 'Export'),
        ],
        string="Operation Type",
        required=True,
        default='import',
        tracking=True,
    )
    stage_id = fields.Many2one(
        'comex.operation.stage',
        string="Stage",
        compute='_compute_stage_from_shipments',
        store=True,
        readonly=False,
        default=_default_stage,
        tracking=True,
        group_expand='_read_group_stage_ids',
        domain="['|', ('operation_type', '=', 'all'), ('operation_type', '=', operation_type)]",
        copy=False,
        help="Operation stage automatically computed from shipment stages. "
             "Reflects the most advanced stage among all shipments. "
             "To update, modify shipment stages instead.",
    )
    current_location_id = fields.Many2one(
        'stock.location',
        string="Current COMEX Location",
        domain="[('usage', 'in', ('transit', 'internal'))]",
        tracking=True,
        help="Current location where goods are located in the COMEX transit chain. "
             "Can be a transit or internal location.",
    )
    color = fields.Integer(
        string="Color Index",
        default=0,
    )
    priority = fields.Selection(
        selection=[
            ('0', 'Normal'),
            ('1', 'Low'),
            ('2', 'High'),
            ('3', 'Urgent'),
        ],
        string="Priority",
        default='0',
        tracking=True,
    )
    tag_ids = fields.Many2many(
        'comex.operation.tag',
        string="Tags",
    )
    description = fields.Html(
        string="Description",
    )

    # Dates
    date_operation = fields.Date(
        string="Operation Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    date_eta = fields.Date(
        string="ETA (Estimated Time of Arrival)",
        tracking=True,
        help="Estimated arrival date at destination port.",
    )
    date_etd = fields.Date(
        string="ETD (Estimated Time of Departure)",
        tracking=True,
        help="Estimated departure date from origin port.",
    )
    date_arrival = fields.Date(
        string="Actual Arrival Date",
        compute='_compute_date_arrival',
        store=True,
        tracking=True,
    )
    date_nationalization = fields.Date(
        string="Nationalization Date",
        tracking=True,
        help="Date when goods were nationalized (cleared customs).",
    )

    # Partners
    partner_id = fields.Many2one(
        'res.partner',
        string="Supplier/Customer",
        required=True,
        tracking=True,
    )
    customs_broker_id = fields.Many2one(
        'res.partner',
        string="Customs Broker",
        domain="[('is_customs_broker', '=', True)]",
        tracking=True,
    )
    freight_forwarder_id = fields.Many2one(
        'res.partner',
        string="Freight Forwarder",
        domain="[('is_freight_forwarder', '=', True)]",
        tracking=True,
    )

    # Related records
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'comex_operation_id',
        string="Purchase Orders",
    )
    purchase_order_count = fields.Integer(
        string="Purchase Order Count",
        compute='_compute_purchase_order_count',
    )
    sale_order_ids = fields.One2many(
        'sale.order',
        'comex_operation_id',
        string="Sale Orders",
    )
    sale_order_count = fields.Integer(
        string="Sale Order Count",
        compute='_compute_sale_order_count',
    )
    shipment_ids = fields.One2many(
        'comex.shipment',
        'operation_id',
        string="Shipments",
    )
    shipment_count = fields.Integer(
        string="Shipment Count",
        compute='_compute_shipment_count',
    )
    customs_clearance_ids = fields.One2many(
        'comex.customs.clearance',
        'operation_id',
        string="Customs Clearances",
    )
    customs_clearance_count = fields.Integer(
        string="Customs Clearance Count",
        compute='_compute_customs_clearance_count',
    )
    mulc_ids = fields.One2many(
        'comex.mulc',
        'operation_id',
        string="MULC Operations",
    )
    mulc_count = fields.Integer(
        string="MULC Count",
        compute='_compute_mulc_count',
    )
    picking_ids = fields.One2many(
        'stock.picking',
        'comex_operation_id',
        string="Stock Transfers",
    )
    picking_count = fields.Integer(
        string="Transfer Count",
        compute='_compute_picking_count',
    )

    # Invoices and Bills
    invoice_ids = fields.Many2many(
        'account.move',
        'comex_operation_invoice_rel',
        'operation_id',
        'invoice_id',
        string="Invoices/Bills",
        compute='_compute_invoice_ids',
        inverse='_inverse_invoice_ids',
        store=True,
        domain="[('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund'])]",
        help="All invoices and bills: from purchase orders, customs clearances (DI), and landed costs (despachante, local freight, etc.)",
    )
    invoice_count = fields.Integer(
        string="Invoice Count",
        compute='_compute_invoice_count',
    )
    dispatch_invoice_numbers = fields.Char(
        string="N° Despacho",
        compute='_compute_dispatch_invoice_numbers',
        help="Document numbers of Import Dispatch invoices (Document Type 66)",
    )

    # Product Lines (Auto-synchronized from PO/SO lines)
    product_line_ids = fields.One2many(
        'comex.operation.product.line',
        'operation_id',
        string="Product Lines",
        help="Auto-synchronized from PO/SO lines when accessing the Product Lines view",
    )
    product_line_count = fields.Integer(
        string="Product Line Count",
        compute='_compute_product_line_count',
    )

    # Container/Package Count
    container_total_count = fields.Integer(
        string="Total Containers",
        compute='_compute_container_total_count',
        store=True,
        help="Total number of containers/packages in all shipments",
    )

    # Amounts
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        tracking=True,
    )
    
    # Payment Terms (COMEX-specific: Instrument + Timing)
    payment_instrument_id = fields.Many2one(
        'comex.payment.instrument',
        string="Payment Instrument",
        tracking=True,
        help="Method of payment (e.g., TT, L/C, D/P, D/A)",
    )
    payment_timing_id = fields.Many2one(
        'comex.payment.timing',
        string="Payment Timing",
        tracking=True,
        help="When payment is due (e.g., Advance, At Sight, 180 days)",
    )
    payment_terms_display = fields.Char(
        string="Payment Terms",
        compute='_compute_payment_terms_display',
        store=True,
        help="Combined display of payment instrument and timing",
    )
    
    # Bank Intervention (computed from payment instrument)
    requires_bank_intervention = fields.Boolean(
        compute='_compute_requires_bank_intervention',
        store=True,
        string="Requires Bank",
        help="Indicates if payment instrument requires bank intervention (L/C, D/P, D/A)",
    )
    
    # Nominated Bank
    nominated_bank_id = fields.Many2one(
        'res.partner',
        string="Nominated Bank",
        domain="[('is_company', '=', True)]",
        tracking=True,
        help="Bank nominated for this COMEX operation (for L/C, payments, etc.)",
    )
    
    amount_fob = fields.Monetary(
        string="FOB Amount",
        currency_field='currency_id',
        tracking=True,
    )
    amount_freight = fields.Monetary(
        string="Freight Amount",
        currency_field='currency_id',
        tracking=True,
    )
    amount_insurance = fields.Monetary(
        string="Insurance Amount",
        currency_field='currency_id',
        tracking=True,
    )
    amount_cif = fields.Monetary(
        string="CIF Amount",
        compute='_compute_amount_cif',
        store=True,
        currency_field='currency_id',
    )
    
    # VEP (Volante Electrónico de Pago) - Always in ARS
    currency_ars_id = fields.Many2one(
        'res.currency',
        string="ARS Currency",
        default=lambda self: self.env.ref('base.ARS', raise_if_not_found=False),
        readonly=True,
    )
    vep_amount = fields.Monetary(
        string="VEP Amount",
        compute='_compute_vep_amount',
        store=True,
        currency_field='currency_ars_id',
        help="Total VEP (Volante Electrónico de Pago) amount from AFIP/ARCA. "
             "Sum of all customs clearance tributes (DIE, VAT, statistics, perceptions). "
             "Always in ARS as per Argentine customs regulations.",
    )

    # === PAYMENT STATUS - COMMERCIAL ===
    commercial_payment_status = fields.Selection(
        selection=[
            ('not_paid', 'Not Paid'),
            ('partial', 'Partially Paid'),
            ('in_payment', 'Paid (Pending Reconciliation)'),
            ('paid', 'Fully Paid'),
        ],
        string="Commercial Payment Status",
        compute='_compute_commercial_payment_status',
        store=True,
        help="Payment status of commercial invoices (suppliers and customers, excluding customs tributes). "
             "'Paid (Pending Reconciliation)' means payments are registered but not yet reconciled.",
    )
    commercial_total_amount = fields.Monetary(
        string="Commercial Total",
        compute='_compute_commercial_totals',
        store=True,
        currency_field='currency_id',
        help="Total amount of commercial invoices (from purchase orders and sales orders).",
    )
    commercial_paid_amount = fields.Monetary(
        string="Commercial Paid",
        compute='_compute_commercial_totals',
        store=True,
        currency_field='currency_id',
        help="Amount paid on commercial invoices.",
    )
    commercial_due_amount = fields.Monetary(
        string="Commercial Due",
        compute='_compute_commercial_totals',
        store=True,
        currency_field='currency_id',
        help="Amount pending on commercial invoices.",
    )

    # === PAYMENT STATUS - CUSTOMS ===
    customs_payment_status = fields.Selection(
        selection=[
            ('not_paid', 'Not Paid'),
            ('partial', 'Partially Paid'),
            ('in_payment', 'Paid (Pending Reconciliation)'),
            ('paid', 'Fully Paid'),
        ],
        string="Customs Payment Status",
        compute='_compute_customs_payment_status',
        store=True,
        help="Payment status of customs tributes (VEP - Volante Electrónico de Pago from ARCA). "
             "'Paid (Pending Reconciliation)' means payments are registered but not yet reconciled.",
    )
    customs_total_amount = fields.Monetary(
        string="Customs Total",
        compute='_compute_customs_totals',
        store=True,
        currency_field='currency_ars_id',
        help="Total amount of customs tributes (VEP payments to ARCA). Always in ARS.",
    )
    customs_paid_amount = fields.Monetary(
        string="Customs Paid",
        compute='_compute_customs_totals',
        store=True,
        currency_field='currency_ars_id',
        help="Amount paid on customs tributes. Always in ARS.",
    )
    customs_due_amount = fields.Monetary(
        string="Customs Due",
        compute='_compute_customs_totals',
        store=True,
        currency_field='currency_ars_id',
        help="Amount pending on customs tributes. Always in ARS.",
    )

    # === PAYMENT STATUS - PURCHASE ORDERS (IMPORTS) ===
    purchase_order_payment_status = fields.Selection(
        selection=[
            ('not_paid', 'Not Paid'),
            ('partial', 'Partially Paid'),
            ('in_payment', 'Paid (Pending Reconciliation)'),
            ('paid', 'Fully Paid'),
        ],
        string="Purchase Order Payment Status",
        compute='_compute_purchase_order_payment_status',
        store=True,
        help="Payment status of vendor invoices from purchase orders (imports only). "
             "'Paid (Pending Reconciliation)' means payments are registered but not yet reconciled.",
    )
    purchase_order_total_amount = fields.Monetary(
        string="Purchase Order Total",
        compute='_compute_purchase_order_totals',
        store=True,
        currency_field='currency_id',
        help="Total amount of vendor invoices from purchase orders.",
    )
    purchase_order_paid_amount = fields.Monetary(
        string="Purchase Order Paid",
        compute='_compute_purchase_order_totals',
        store=True,
        currency_field='currency_id',
        help="Amount paid on vendor invoices.",
    )
    purchase_order_due_amount = fields.Monetary(
        string="Purchase Order Due",
        compute='_compute_purchase_order_totals',
        store=True,
        currency_field='currency_id',
        help="Amount pending on vendor invoices.",
    )

    # === PAYMENT STATUS - SALE ORDERS (EXPORTS) ===
    sale_order_payment_status = fields.Selection(
        selection=[
            ('not_paid', 'Not Collected'),
            ('partial', 'Partially Collected'),
            ('in_payment', 'Collected (Pending Reconciliation)'),
            ('paid', 'Fully Collected'),
        ],
        string="Sale Order Payment Status",
        compute='_compute_sale_order_payment_status',
        store=True,
        help="Collection status of customer invoices from sales orders (exports only). "
             "'Collected (Pending Reconciliation)' means payments are registered but not yet reconciled.",
    )
    sale_order_total_amount = fields.Monetary(
        string="Sale Order Total",
        compute='_compute_sale_order_totals',
        store=True,
        currency_field='currency_id',
        help="Total amount of customer invoices from sales orders.",
    )
    sale_order_paid_amount = fields.Monetary(
        string="Sale Order Paid",
        compute='_compute_sale_order_totals',
        store=True,
        currency_field='currency_id',
        help="Amount collected from customers.",
    )
    sale_order_due_amount = fields.Monetary(
        string="Sale Order Due",
        compute='_compute_sale_order_totals',
        store=True,
        currency_field='currency_id',
        help="Amount pending collection from customers.",
    )

    # Incoterms (aggregated from PO/SO)
    incoterm_ids = fields.Many2many(
        'account.incoterms',
        string="Incoterms",
        compute='_compute_incoterm_ids',
        store=True,
        readonly=True,
        help="Unique incoterms from all linked purchase and sale orders. "
             "To modify, update incoterms in the respective PO/SO.",
    )

    # Transport
    transport_mode = fields.Selection(
        selection=[
            ('sea', 'Sea'),
            ('air', 'Air'),
            ('land', 'Land'),
            ('multimodal', 'Multimodal'),
        ],
        string="Transport Mode",
        default='sea',
        tracking=True,
    )
    origin_country_id = fields.Many2one(
        'res.country',
        string="Origin Country",
        tracking=True,
    )
    destination_country_id = fields.Many2one(
        'res.country',
        string="Destination Country",
        default=lambda self: self.env.ref('base.ar', raise_if_not_found=False),
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to assign sequence when name is '/'."""
        for vals in vals_list:
            if 'company_id' in vals:
                self = self.with_company(vals['company_id'])
            if vals.get('name', '/') == '/':
                operation_type = vals.get('operation_type', 'import')
                seq_code = f'comex.operation.{operation_type}'
                vals['name'] = self.env['ir.sequence'].next_by_code(seq_code) or '/'
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('payment_instrument_id.name', 'payment_timing_id.name')
    def _compute_payment_terms_display(self):
        """Compute combined payment terms display."""
        for record in self:
            if record.payment_instrument_id and record.payment_timing_id:
                instrument = record.payment_instrument_id.code
                timing = record.payment_timing_id.name
                record.payment_terms_display = f"{instrument} - {timing}"
            elif record.payment_instrument_id:
                record.payment_terms_display = record.payment_instrument_id.code
            elif record.payment_timing_id:
                record.payment_terms_display = record.payment_timing_id.name
            else:
                record.payment_terms_display = False

    @api.depends('payment_instrument_id.bank_intervention')
    def _compute_requires_bank_intervention(self):
        """Determine if payment instrument requires bank intervention."""
        for record in self:
            record.requires_bank_intervention = bool(
                record.payment_instrument_id and 
                record.payment_instrument_id.bank_intervention
            )

    @api.depends('amount_fob', 'amount_freight', 'amount_insurance')
    def _compute_amount_cif(self):
        for record in self:
            record.amount_cif = record.amount_fob + record.amount_freight + record.amount_insurance

    @api.depends('customs_clearance_ids.vep_amount')
    def _compute_vep_amount(self):
        """Calculate total VEP amount from all customs clearances.
        
        VEP (Volante Electrónico de Pago) is the electronic payment voucher
        generated in AFIP/ARCA system for customs duty payments.
        
        The VEP amount is entered manually in each clearance record.
        Details of tributes (DIE, VAT, Statistics, etc.) are found in
        Document Type 66 (Despacho de Importación) in Accounting.
        
        Always in ARS as per Argentine customs regulations.
        """
        for record in self:
            record.vep_amount = sum(record.customs_clearance_ids.mapped('vep_amount'))

    @api.depends('invoice_ids.amount_total', 'invoice_ids.amount_residual', 'invoice_ids.state')
    def _compute_commercial_totals(self):
        """Calculate commercial payment totals (excluding customs invoices and refunds).
        
        Counts ONLY invoices (not refunds) for amount calculations.
        Refunds/credit notes should only affect the payment_state of the original invoice
        (which Odoo handles automatically), but should NOT be counted as separate amounts.
        
        Filters out:
        - Refunds (in_refund, out_refund) - handled via payment_state
        - Document Type 66 (Despacho de Importación) - goes to Customs status
        
        Includes:
        - Supplier invoices (from purchase orders)
        - Customer invoices (from sales orders)
        - Local costs: customs brokers, freight forwarders, local transport, storage, etc.
        
        Uses native Odoo amount_residual field for automatic payment tracking.
        """
        for record in self:
            # Filter: Posted invoices (EXCLUDE refunds and type 66)
            commercial_invoices = record.invoice_ids.filtered(
                lambda inv: inv.state == 'posted' and
                inv.move_type in ('out_invoice', 'in_invoice', 'out_receipt', 'in_receipt') and
                (not hasattr(inv, 'l10n_latam_document_type_id') or
                 not inv.l10n_latam_document_type_id or
                 inv.l10n_latam_document_type_id.code != '66')
            )
            
            # Calculate totals from invoices only (not refunds)
            record.commercial_total_amount = sum(commercial_invoices.mapped('amount_total'))
            record.commercial_paid_amount = sum(
                inv.amount_total - inv.amount_residual
                for inv in commercial_invoices
            )
            record.commercial_due_amount = sum(commercial_invoices.mapped('amount_residual'))

    @api.depends('invoice_ids.payment_state', 'invoice_ids.state', 'invoice_ids.move_type',
                 'invoice_ids.amount_total', 'invoice_ids.amount_residual')
    def _compute_commercial_payment_status(self):
        """Determine commercial payment status based on actual invoice payments.

        Reflects the payment reality of existing posted commercial invoices,
        independent of PO/SO invoicing progress (invoice_status).

        Logic:
        - No posted invoices → 'not_paid'
        - All invoices fully paid & reconciled → 'paid'
        - All invoices fully paid, pending reconciliation → 'in_payment'
        - Some amount paid but residual remains → 'partial'
        - Invoices exist but nothing paid → 'not_paid'
        """
        for record in self:
            # Get commercial invoices (exclude type 66)
            commercial_invoices = record.invoice_ids.filtered(
                lambda inv: inv.state == 'posted' and
                inv.move_type in ('out_invoice', 'in_invoice', 'out_receipt', 'in_receipt') and
                (not hasattr(inv, 'l10n_latam_document_type_id') or
                 not inv.l10n_latam_document_type_id or
                 inv.l10n_latam_document_type_id.code != '66')
            )

            # Get commercial refunds (credit notes)
            commercial_refunds = record.invoice_ids.filtered(
                lambda inv: inv.state == 'posted' and
                inv.move_type in ('out_refund', 'in_refund') and
                (not hasattr(inv, 'l10n_latam_document_type_id') or
                 not inv.l10n_latam_document_type_id or
                 inv.l10n_latam_document_type_id.code != '66')
            )

            if not commercial_invoices and not commercial_refunds:
                record.commercial_payment_status = 'not_paid'
                continue

            # Calculate net amounts (invoices - refunds)
            invoice_total = sum(commercial_invoices.mapped('amount_total'))
            invoice_residual = sum(commercial_invoices.mapped('amount_residual'))
            refund_total = sum(commercial_refunds.mapped('amount_total'))

            net_total = invoice_total - refund_total
            paid_amount = invoice_total - invoice_residual
            net_residual = invoice_residual - refund_total

            if net_total <= 0:
                record.commercial_payment_status = 'not_paid'
            elif net_residual <= 0:
                # Fully paid, check reconciliation
                if all(inv.payment_state == 'paid' for inv in commercial_invoices):
                    record.commercial_payment_status = 'paid'
                else:
                    record.commercial_payment_status = 'in_payment'
            elif paid_amount > 0:
                record.commercial_payment_status = 'partial'
            else:
                record.commercial_payment_status = 'not_paid'

    @api.depends('invoice_ids.amount_total', 'invoice_ids.amount_residual', 'invoice_ids.state')
    def _compute_purchase_order_totals(self):
        """Calculate purchase order payment totals (only invoices from purchase orders, excluding customs).
        
        Counts ONLY invoices from purchase orders (not refunds) for amount calculations.
        Filters out Document Type 66 (customs clearances).
        
        Includes:
        - Supplier invoices linked to purchase orders in this operation
        
        Excludes:
        - Customer invoices (sales orders)
        - Local cost invoices not linked to POs (customs brokers, freight forwarders, etc.)
        - Document Type 66 (customs clearances)
        - Refunds (handled via payment_state)
        """
        for record in self:
            # Get all invoices from purchase orders in this operation
            po_invoices = self.env['account.move']
            for po in record.purchase_order_ids:
                po_invoices |= po.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted' and
                    inv.move_type in ('in_invoice', 'in_receipt') and
                    (not hasattr(inv, 'l10n_latam_document_type_id') or
                     not inv.l10n_latam_document_type_id or
                     inv.l10n_latam_document_type_id.code != '66')
                )
            
            # Calculate totals from purchase order invoices only
            record.purchase_order_total_amount = sum(po_invoices.mapped('amount_total'))
            record.purchase_order_paid_amount = sum(
                inv.amount_total - inv.amount_residual
                for inv in po_invoices
            )
            record.purchase_order_due_amount = sum(po_invoices.mapped('amount_residual'))

    @api.depends('invoice_ids.payment_state', 'invoice_ids.state', 'invoice_ids.move_type',
                 'invoice_ids.amount_total', 'invoice_ids.amount_residual')
    def _compute_purchase_order_payment_status(self):
        """Determine purchase order payment status based on actual invoice payments.

        Reflects the payment reality of existing posted invoices from purchase
        orders, independent of PO invoicing progress (invoice_status).

        Logic:
        - No posted invoices → 'not_paid'
        - All invoices fully paid & reconciled → 'paid'
        - All invoices fully paid, pending reconciliation → 'in_payment'
        - Some amount paid but residual remains → 'partial'
        - Invoices exist but nothing paid → 'not_paid'
        """
        for record in self:
            # Get invoices from purchase orders (exclude type 66 customs clearances)
            po_invoices = self.env['account.move']
            for po in record.purchase_order_ids:
                po_invoices |= po.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted' and
                    inv.move_type in ('in_invoice', 'in_receipt') and
                    (not hasattr(inv, 'l10n_latam_document_type_id') or
                     not inv.l10n_latam_document_type_id or
                     inv.l10n_latam_document_type_id.code != '66')
                )

            # Get refunds from purchase orders
            po_refunds = self.env['account.move']
            for po in record.purchase_order_ids:
                po_refunds |= po.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted' and
                    inv.move_type == 'in_refund' and
                    (not hasattr(inv, 'l10n_latam_document_type_id') or
                     not inv.l10n_latam_document_type_id or
                     inv.l10n_latam_document_type_id.code != '66')
                )

            if not po_invoices and not po_refunds:
                record.purchase_order_payment_status = 'not_paid'
                continue

            # Calculate net amounts (invoices - refunds)
            invoice_total = sum(po_invoices.mapped('amount_total'))
            invoice_residual = sum(po_invoices.mapped('amount_residual'))
            refund_total = sum(po_refunds.mapped('amount_total'))

            net_total = invoice_total - refund_total
            paid_amount = invoice_total - invoice_residual
            net_residual = invoice_residual - refund_total

            if net_total <= 0:
                record.purchase_order_payment_status = 'not_paid'
            elif net_residual <= 0:
                # Fully paid, check reconciliation
                if all(inv.payment_state == 'paid' for inv in po_invoices):
                    record.purchase_order_payment_status = 'paid'
                else:
                    record.purchase_order_payment_status = 'in_payment'
            elif paid_amount > 0:
                record.purchase_order_payment_status = 'partial'
            else:
                record.purchase_order_payment_status = 'not_paid'

    @api.depends('invoice_ids.amount_total', 'invoice_ids.amount_residual', 'invoice_ids.state')
    def _compute_sale_order_totals(self):
        """Calculate sale order payment totals (only invoices from sales orders, excluding customs).
        
        Counts ONLY invoices from sales orders (not refunds) for amount calculations.
        Filters out Document Type 66 (customs clearances).
        
        Includes:
        - Customer invoices linked to sales orders in this operation
        
        Excludes:
        - Supplier invoices (purchase orders)
        - Local cost invoices not linked to SOs
        - Document Type 66 (customs clearances)
        - Refunds (handled via payment_state)
        """
        for record in self:
            # Get all invoices from sales orders in this operation
            so_invoices = self.env['account.move']
            for so in record.sale_order_ids:
                so_invoices |= so.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted' and
                    inv.move_type in ('out_invoice', 'out_receipt') and
                    (not hasattr(inv, 'l10n_latam_document_type_id') or
                     not inv.l10n_latam_document_type_id or
                     inv.l10n_latam_document_type_id.code != '66')
                )
            
            # Calculate totals from sales order invoices only
            record.sale_order_total_amount = sum(so_invoices.mapped('amount_total'))
            record.sale_order_paid_amount = sum(
                inv.amount_total - inv.amount_residual
                for inv in so_invoices
            )
            record.sale_order_due_amount = sum(so_invoices.mapped('amount_residual'))

    @api.depends('invoice_ids.payment_state', 'invoice_ids.state', 'invoice_ids.move_type',
                 'invoice_ids.amount_total', 'invoice_ids.amount_residual')
    def _compute_sale_order_payment_status(self):
        """Determine sale order payment status based on actual invoice payments.

        Reflects the payment reality of existing posted invoices from sales
        orders, independent of SO invoicing progress (invoice_status).

        Logic:
        - No posted invoices → 'not_paid'
        - All invoices fully paid & reconciled → 'paid'
        - All invoices fully paid, pending reconciliation → 'in_payment'
        - Some amount paid but residual remains → 'partial'
        - Invoices exist but nothing paid → 'not_paid'
        """
        for record in self:
            # Get invoices from sales orders (exclude type 66 customs clearances)
            so_invoices = self.env['account.move']
            for so in record.sale_order_ids:
                so_invoices |= so.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted' and
                    inv.move_type in ('out_invoice', 'out_receipt') and
                    (not hasattr(inv, 'l10n_latam_document_type_id') or
                     not inv.l10n_latam_document_type_id or
                     inv.l10n_latam_document_type_id.code != '66')
                )

            # Get refunds from sales orders
            so_refunds = self.env['account.move']
            for so in record.sale_order_ids:
                so_refunds |= so.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted' and
                    inv.move_type == 'out_refund' and
                    (not hasattr(inv, 'l10n_latam_document_type_id') or
                     not inv.l10n_latam_document_type_id or
                     inv.l10n_latam_document_type_id.code != '66')
                )

            if not so_invoices and not so_refunds:
                record.sale_order_payment_status = 'not_paid'
                continue

            # Calculate net amounts (invoices - refunds)
            invoice_total = sum(so_invoices.mapped('amount_total'))
            invoice_residual = sum(so_invoices.mapped('amount_residual'))
            refund_total = sum(so_refunds.mapped('amount_total'))

            net_total = invoice_total - refund_total
            paid_amount = invoice_total - invoice_residual
            net_residual = invoice_residual - refund_total

            if net_total <= 0:
                record.sale_order_payment_status = 'not_paid'
            elif net_residual <= 0:
                # Fully paid, check reconciliation
                if all(inv.payment_state == 'paid' for inv in so_invoices):
                    record.sale_order_payment_status = 'paid'
                else:
                    record.sale_order_payment_status = 'in_payment'
            elif paid_amount > 0:
                record.sale_order_payment_status = 'partial'
            else:
                record.sale_order_payment_status = 'not_paid'

    @api.depends('purchase_order_ids.incoterm_id', 'sale_order_ids.incoterm')
    def _compute_incoterm_ids(self):
        """Aggregate unique incoterms from all linked purchase and sale orders.
        
        This computed field automatically collects all unique incoterms from:
        - Purchase Orders (for imports): uses incoterm_id
        - Sale Orders (for exports): uses incoterm
        
        Example:
            PO1: Incoterm FOB
            PO2: Incoterm FOB (duplicate, ignored)
            PO3: Incoterm CIF
            Result: [FOB, CIF]
        
        The field is readonly to force users to set incoterms on PO/SO.
        """
        for record in self:
            incoterms = self.env['account.incoterms']
            
            # Collect incoterms from purchase orders
            for po in record.purchase_order_ids:
                if po.incoterm_id:
                    incoterms |= po.incoterm_id
            
            # Collect incoterms from sale orders (field name: 'incoterm', not 'incoterm_id')
            for so in record.sale_order_ids:
                if so.incoterm:
                    incoterms |= so.incoterm
            
            record.incoterm_ids = incoterms

    @api.depends('invoice_ids.amount_total', 'invoice_ids.amount_residual', 
                 'invoice_ids.state', 'customs_clearance_ids.vep_amount')
    def _compute_customs_totals(self):
        """Calculate customs payment totals (Document Type 66 only, exclude refunds).
        
        Counts ONLY invoices (not refunds) for amount calculations.
        Refunds/credit notes should only affect the payment_state of the original invoice
        (which Odoo handles automatically), but should NOT be counted as separate amounts.
        
        Filters ONLY Document Type 66 invoices (Despacho de Importación).
        Total expected is based on VEP amounts entered in clearances.
        Paid amount is tracked automatically from invoice payments.
        
        Always in ARS as per Argentine customs regulations.
        """
        for record in self:
            # Filter: Posted invoices (EXCLUDE refunds), ONLY Document Type 66
            customs_invoices = self.env['account.move']
            if hasattr(self.env['account.move'], '_fields') and \
               'l10n_latam_document_type_id' in self.env['account.move']._fields:
                customs_invoices = record.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted' and
                    inv.move_type in ('out_invoice', 'in_invoice', 'out_receipt', 'in_receipt') and
                    inv.l10n_latam_document_type_id and
                    inv.l10n_latam_document_type_id.code == '66'
                )
            
            # Total = VEP amounts (entered manually once per clearance)
            record.customs_total_amount = sum(record.customs_clearance_ids.mapped('vep_amount'))
            
            # If no VEP amounts entered yet, use invoice amounts as fallback
            if record.customs_total_amount == 0 and customs_invoices:
                record.customs_total_amount = sum(customs_invoices.mapped('amount_total'))
            
            # Paid amount from invoices (automatic from Odoo payment tracking)
            record.customs_paid_amount = sum(
                inv.amount_total - inv.amount_residual
                for inv in customs_invoices
            )
            
            # Due = Total - Paid
            record.customs_due_amount = record.customs_total_amount - record.customs_paid_amount

    @api.depends('invoice_ids.payment_state', 'invoice_ids.state', 'invoice_ids.move_type',
                 'invoice_ids.amount_total', 'invoice_ids.amount_residual', 'customs_clearance_ids.vep_amount')
    def _compute_customs_payment_status(self):
        """Determine customs payment status considering invoices, refunds, and payments.
        
        Logic:
        1. Calculate net amounts (invoices - refunds)
        2. If net due amount > 0 → pending payment
        3. If net due amount <= 0 → paid
        
        This correctly handles:
        - Invoice paid → Credit note → New invoice paid = "Paid" (if net is covered)
        - Invoice paid → Credit note → Not reinvoiced = "Not Paid" (net is negative)
        """
        for record in self:
            # Get customs invoices (type 66 only)
            customs_invoices = self.env['account.move']
            customs_refunds = self.env['account.move']
            
            if hasattr(self.env['account.move'], '_fields') and \
               'l10n_latam_document_type_id' in self.env['account.move']._fields:
                customs_invoices = record.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted' and
                    inv.move_type in ('out_invoice', 'in_invoice', 'out_receipt', 'in_receipt') and
                    inv.l10n_latam_document_type_id and
                    inv.l10n_latam_document_type_id.code == '66'
                )
                
                customs_refunds = record.invoice_ids.filtered(
                    lambda inv: inv.state == 'posted' and
                    inv.move_type in ('out_refund', 'in_refund') and
                    inv.l10n_latam_document_type_id and
                    inv.l10n_latam_document_type_id.code == '66'
                )
            
            if not customs_invoices and not customs_refunds:
                record.customs_payment_status = 'not_paid'
                continue
            
            # Calculate net amounts (invoices - refunds)
            invoice_total = sum(customs_invoices.mapped('amount_total'))
            invoice_residual = sum(customs_invoices.mapped('amount_residual'))
            refund_total = sum(customs_refunds.mapped('amount_total'))
            
            net_total = invoice_total - refund_total
            net_residual = invoice_residual - refund_total
            paid_amount = invoice_total - invoice_residual
            
            # Status based on net amounts
            if net_total <= 0:
                # No net amount to pay (refunds >= invoices)
                record.customs_payment_status = 'not_paid'
            elif net_residual <= 0:
                # All paid, check if reconciled
                # If all invoices have payment_state='paid', they are fully reconciled
                # If any invoice has payment_state='in_payment', payments exist but not reconciled
                if all(inv.payment_state == 'paid' for inv in customs_invoices):
                    record.customs_payment_status = 'paid'  # Fully paid & reconciled
                else:
                    record.customs_payment_status = 'in_payment'  # Paid but not reconciled
            elif paid_amount == 0:
                # No payments registered yet
                record.customs_payment_status = 'not_paid'
            else:
                # Partial payment (some amount paid but not all)
                record.customs_payment_status = 'partial'

    @api.depends('picking_ids.date_done')
    def _compute_date_arrival(self):
        for record in self:
            done_pickings = record.picking_ids.filtered(
                lambda p: p.state == 'done' and p.date_done
            )
            if done_pickings:
                max_date = max(done_pickings.mapped('date_done'))
                record.date_arrival = fields.Date.context_today(self, timestamp=max_date)
            else:
                record.date_arrival = False

    def _compute_purchase_order_count(self):
        for record in self:
            record.purchase_order_count = len(record.purchase_order_ids)

    def _compute_sale_order_count(self):
        for record in self:
            record.sale_order_count = len(record.sale_order_ids)

    def _compute_shipment_count(self):
        for record in self:
            record.shipment_count = len(record.shipment_ids)

    def _compute_customs_clearance_count(self):
        for record in self:
            record.customs_clearance_count = len(record.customs_clearance_ids)

    def _compute_mulc_count(self):
        for record in self:
            record.mulc_count = len(record.mulc_ids)

    def _compute_picking_count(self):
        for record in self:
            record.picking_count = len(record.picking_ids)

    @api.depends(
        'purchase_order_ids.invoice_ids',
        'customs_clearance_ids.vendor_bill_id',
        'customs_clearance_ids.landed_cost_id.vendor_bill_id',
    )
    def _compute_invoice_ids(self):
        """Auto-add all related invoices: POs + Despachos + Landed Costs.

        Merges auto-computed invoices with any manually-added invoices
        already stored in the M2M relation, so manual additions are
        never lost when this compute re-triggers.
        """
        for record in self:
            computed = self.env['account.move']

            # 1. Invoices from purchase orders
            computed |= record.purchase_order_ids.mapped('invoice_ids')

            # 2. Vendor bills from customs clearances (Despacho DI)
            computed |= record.customs_clearance_ids.mapped('vendor_bill_id')

            # 3. Vendor bills from landed costs
            computed |= record.customs_clearance_ids.mapped(
                'landed_cost_id.vendor_bill_id'
            )

            # Preserve manually-added invoices (stored value from M2M)
            existing = record.invoice_ids

            # Merge computed + existing, then filter out cancelled
            all_invoices = (existing | computed).filtered(
                lambda inv: inv.state != 'cancel'
            )

            record.invoice_ids = [(6, 0, all_invoices.ids)]
    
    def _inverse_invoice_ids(self):
        """Allow manual editing of invoice_ids field."""
        # No action needed - field is stored and editable
        pass

    def _compute_invoice_count(self):
        """Count total invoices."""
        for record in self:
            record.invoice_count = len(record.invoice_ids)

    @api.depends('invoice_ids')
    def _compute_dispatch_invoice_numbers(self):
        """Extract document numbers from Import Dispatch invoices (Type 66)."""
        for record in self:
            dispatch_invoices = self.env['account.move']
            
            # Filter invoices with document type 66 (Despacho de Importación)
            # Check if l10n_latam fields exist (requires l10n_ar module)
            if hasattr(self.env['account.move'], '_fields') and 'l10n_latam_document_type_id' in self.env['account.move']._fields:
                dispatch_invoices = record.invoice_ids.filtered(
                    lambda inv: inv.l10n_latam_document_type_id and inv.l10n_latam_document_type_id.code == '66'
                )
            
            if dispatch_invoices:
                # Get document numbers (l10n_latam_document_number is the official number)
                numbers = dispatch_invoices.mapped('l10n_latam_document_number')
                # Remove False/empty values
                numbers = [n for n in numbers if n]
                record.dispatch_invoice_numbers = ', '.join(numbers[:3]) + (f' (+{len(numbers) - 3})' if len(numbers) > 3 else '')
            else:
                record.dispatch_invoice_numbers = False

    @api.depends('shipment_ids.package_ids')
    def _compute_container_total_count(self):
        """Calculate total number of containers from all shipments."""
        for record in self:
            record.container_total_count = len(record.shipment_ids.mapped('package_ids'))

    def _compute_product_line_count(self):
        """Calculate number of product lines (triggers sync if needed)."""
        # Ensure product lines are synced before computing count
        operations_to_sync = self.filtered('purchase_order_ids')
        if operations_to_sync:
            self.env['comex.operation.product.line'].sudo()._sync_operations(operations_to_sync)
        
        for record in self:
            record.product_line_count = len(record.product_line_ids)

    # -------------------------------------------------------------------------
    # PRODUCT LINE SYNCHRONIZATION (Manual trigger)
    # -------------------------------------------------------------------------
    def _sync_product_lines_from_purchase(self):
        """Synchronize product lines from purchase order lines.
        
        Creates/updates product lines when PO lines are added/modified.
        This method should be called when purchase orders change.
        """
        ProductLine = self.env['comex.operation.product.line']
        
        for operation in self:
            # Get existing product lines from purchase orders
            existing_lines = operation.product_line_ids.filtered(
                lambda l: l.origin_type == 'purchase' and l.purchase_line_id
            )
            existing_po_lines = existing_lines.mapped('purchase_line_id')
            
            # Get all PO lines from operation's purchase orders
            current_po_lines = operation.purchase_order_ids.mapped('order_line')
            
            # Lines to create (new PO lines not yet in product_line_ids)
            lines_to_create = current_po_lines - existing_po_lines
            
            # Lines to delete (product lines whose PO line no longer exists)
            lines_to_delete = existing_lines.filtered(
                lambda l: l.purchase_line_id not in current_po_lines
            )
            
            # Create new product lines
            for po_line in lines_to_create:
                ProductLine.create({
                    'operation_id': operation.id,
                    'product_id': po_line.product_id.id,
                    'name': po_line.name,
                    'product_qty': po_line.product_qty,
                    'product_uom': po_line.product_uom.id,
                    'price_unit': po_line.price_unit,
                    'qty_received': po_line.qty_received,
                    'origin_type': 'purchase',
                    'purchase_line_id': po_line.id,
                })
            
            # Delete obsolete lines
            if lines_to_delete:
                lines_to_delete.unlink()
            
            # Update existing lines with latest PO data
            for product_line in existing_lines - lines_to_delete:
                po_line = product_line.purchase_line_id
                product_line.write({
                    'product_qty': po_line.product_qty,
                    'qty_received': po_line.qty_received,
                    'price_unit': po_line.price_unit,
                })

    # -------------------------------------------------------------------------
    # STAGE SYNCHRONIZATION
    # -------------------------------------------------------------------------
    @api.depends('shipment_ids.stage_id')
    def _compute_stage_from_shipments(self):
        """Compute operation stage from shipment stages.
        
        Edge cases handled:
        - Edge Case 1: Shipments without stage are filtered out
        - Edge Case 2: If no shipments, maintain current stage (don't reset)
        - Edge Case 3: Allow automatic regression (stage can go backwards)
        - Edge Case 6: Filter by operation_type compatibility
        - Edge Case 8: Use context to prevent infinite loops
        
        The stage is computed as the most advanced stage among all shipments.
        Manual overrides are allowed (readonly=False) but will recalculate when shipments change.
        """
        for record in self:
            # Prevent infinite loops (Edge Case 8)
            if self.env.context.get('skip_stage_sync'):
                continue
                
            # Filter shipments with stage (Edge Case 1)
            shipments_with_stage = record.shipment_ids.filtered('stage_id')
            
            if not shipments_with_stage:
                # Edge Case 2: No shipments or none have stage → maintain current stage
                # Don't reset to default, keep what user has set
                continue
            
            # Edge Case 6: Filter stages by operation_type compatibility
            # Only consider stages compatible with this operation's type
            compatible_stages = shipments_with_stage.mapped('stage_id').filtered(
                lambda s: s.operation_type in ('all', record.operation_type)
            )
            
            if not compatible_stages:
                # No compatible stages found, maintain current
                continue
            
            # Get most advanced stage (highest sequence)
            # Edge Case 3: This allows automatic regression if a shipment goes back
            most_advanced_stage = max(compatible_stages, key=lambda s: s.sequence)
            
            # Update only if different (avoid unnecessary writes)
            if record.stage_id != most_advanced_stage:
                record.stage_id = most_advanced_stage

    # -------------------------------------------------------------------------
    # KANBAN METHODS
    # -------------------------------------------------------------------------
    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Show all active stages in Kanban view."""
        search_domain = [
            ('active', '=', True),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', self.env.company.id),
        ]
        # Filter by operation_type if present in domain
        for dom in domain:
            if len(dom) == 3 and dom[0] == 'operation_type' and dom[1] == '=':
                search_domain.extend([
                    '|',
                    ('operation_type', '=', dom[2]),
                    ('operation_type', '=', 'all'),
                ])
                break
        return stages.search(search_domain, order=order)

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    @api.onchange('operation_type')
    def _onchange_operation_type(self):
        """Reset stage when operation type changes."""
        self.stage_id = self._default_stage()

    @api.onchange('stage_id')
    def _onchange_stage_id(self):
        """Reset location when stage changes, update domain."""
        self.current_location_id = False
        if self.stage_id and self.stage_id.parent_location_id:
            return {
                'domain': {
                    'current_location_id': [
                        ('usage', '=', 'transit'),
                        ('id', 'child_of', self.stage_id.parent_location_id.id),
                    ]
                }
            }

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Set origin country from partner."""
        if self.partner_id and self.partner_id.country_id:
            self.origin_country_id = self.partner_id.country_id

    @api.onchange('payment_instrument_id', 'nominated_bank_id')
    def _onchange_check_bank_required(self):
        """Warning if payment instrument requires bank but no bank is nominated."""
        if self.requires_bank_intervention and not self.nominated_bank_id:
            return {
                'warning': {
                    'title': _('Bank Required'),
                    'message': _(
                        'Payment instrument "%s" typically requires bank intervention. '
                        'Consider nominating a bank for this operation.'
                    ) % self.payment_instrument_id.name,
                }
            }

    def write(self, vals):
        # Prevent stage change if actionable pickings exist (draft or assigned).
        # Pickings in 'waiting' or 'confirmed' are normal in the push chain
        # and should NOT block stage advancement.
        if 'stage_id' in vals:
            for record in self:
                blocking_pickings = record.picking_ids.filtered(
                    lambda p: p.state in ('draft', 'assigned')
                )
                if blocking_pickings:
                    raise UserError(_(
                        "Cannot change stage while there are actionable transfers:\n%(pickings)s\n\n"
                        "Please validate or cancel these transfers first.",
                        pickings='\n'.join(blocking_pickings.mapped('name'))
                    ))
        
        res = super().write(vals)
        
        # Sync dates to purchase orders (prevent infinite loop with context flag)
        if 'date_eta' in vals and not self.env.context.get('skip_comex_sync'):
            self.with_context(skip_comex_sync=True)._sync_dates_to_purchase_stock()
        
        # Create stage transfer picking if stage changed
        if 'stage_id' in vals:
            self._on_stage_change()
        
        return res

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------
    def _sync_dates_to_purchase_stock(self):
        """Sync ETA date to related purchase orders and pickings."""
        for record in self:
            if not record.date_eta:
                continue
            eta_datetime = fields.Datetime.to_datetime(record.date_eta)
            if record.purchase_order_ids:
                record.purchase_order_ids.with_context(skip_comex_sync=True).write({
                    'date_planned': eta_datetime
                })
                record.purchase_order_ids.order_line.with_context(skip_comex_sync=True).write({
                    'date_planned': eta_datetime
                })
            # Update scheduled date on pending pickings
            pending_pickings = record.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel')
            )
            if pending_pickings:
                pending_pickings.write({'scheduled_date': eta_datetime})

    def _on_stage_change(self):
        """Handle stage change - create internal transfer if needed."""
        for record in self:
            # Validate stock location before creating transfer
            record._validate_stage_change_stock_location()
            # Future: Create internal transfer picking here

    def _validate_stage_change_stock_location(self):
        """Verify stock exists in expected location before stage change."""
        self.ensure_one()
        if not self.current_location_id:
            return
        
        comex_root = self.env.ref(
            'econovo_l10n_ar_comex.comex_location_root',
            raise_if_not_found=False
        )
        if not comex_root:
            return
        
        product_ids = self.purchase_order_ids.order_line.product_id.ids
        if not product_ids:
            return
        
        quants = self.env['stock.quant'].search([
            ('product_id', 'in', product_ids),
            ('location_id', 'child_of', comex_root.id),
            ('quantity', '>', 0),
        ])
        
        if quants:
            actual_locations = quants.mapped('location_id')
            if self.current_location_id not in actual_locations:
                raise UserError(_(
                    "Stock is not in the expected location.\n"
                    "Expected: %(expected)s\n"
                    "Actual: %(actual)s",
                    expected=self.current_location_id.complete_name,
                    actual=', '.join(actual_locations.mapped('complete_name'))
                ))

    def _get_default_transit_location(self):
        """Get default transit location for first stage."""
        self.ensure_one()
        if self.stage_id and self.stage_id.parent_location_id:
            # Get first child transit location
            return self.env['stock.location'].search([
                ('usage', '=', 'transit'),
                ('location_id', '=', self.stage_id.parent_location_id.id),
            ], limit=1)
        return False

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_create_shipment(self):
        """Create a new shipment linked to this operation."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Shipment'),
            'res_model': 'comex.shipment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_operation_id': self.id,
                'default_partner_id': self.partner_id.id if self.partner_id else False,
            },
        }

    def action_create_customs_clearance(self):
        """Create a new customs clearance linked to this operation."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Customs Clearance'),
            'res_model': 'comex.customs.clearance',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_operation_id': self.id,
                'default_operation_type': self.operation_type,
            },
        }

    def action_create_mulc(self):
        """Create a new MULC operation linked to this operation."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create MULC'),
            'res_model': 'comex.mulc',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_operation_id': self.id,
                'default_currency_id': self.currency_id.id if self.currency_id else False,
            },
        }

    def action_view_purchase_orders(self):
        """Open related purchase orders."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.purchase_order_ids.ids)],
            'context': {
                'default_comex_operation_id': self.id,
                'default_partner_id': self.partner_id.id if self.partner_id else False,
            },
        }

    def action_view_sale_orders(self):
        """Open related sale orders."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Orders'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.sale_order_ids.ids)],
            'context': {
                'default_comex_operation_id': self.id,
                'default_partner_id': self.partner_id.id if self.partner_id else False,
            },
        }

    def action_view_shipments(self):
        """Open related shipments."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Shipments'),
            'res_model': 'comex.shipment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.shipment_ids.ids)],
            'context': {
                'default_operation_id': self.id,
                'default_partner_id': self.partner_id.id if self.partner_id else False,
            },
        }

    def action_view_customs_clearances(self):
        """Open related customs clearances."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customs Clearances'),
            'res_model': 'comex.customs.clearance',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.customs_clearance_ids.ids)],
            'context': {'default_operation_id': self.id},
        }

    def action_view_mulc(self):
        """Open related MULC operations."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('MULC Operations'),
            'res_model': 'comex.mulc',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.mulc_ids.ids)],
            'context': {'default_operation_id': self.id},
        }

    def action_view_pickings(self):
        """Open related stock transfers."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Transfers'),
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
            'context': {'default_comex_operation_id': self.id},
        }

    def action_view_invoices(self):
        """Open all related invoices and bills."""
        self.ensure_one()
        # Default move type based on operation type
        default_move_type = 'in_invoice' if self.operation_type == 'import' else 'out_invoice'
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices & Bills'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': dict(
                self.env.context,
                default_move_type=default_move_type,
                move_type=default_move_type,
                default_partner_id=self.partner_id.id if self.partner_id else False,
            ),
        }

    def action_view_containers(self):
        """Open all containers/packages from shipments."""
        self.ensure_one()
        # Get all packages from all shipments
        packages = self.shipment_ids.mapped('package_ids')
        
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Containers'),
            'res_model': 'stock.quant.package',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', packages.ids)],
            'context': {'default_comex_operation_id': self.id},
        }
        
        # If only one package, open form view directly
        if len(packages) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = packages.id
        
        return action

    def action_view_product_lines(self):
        """Open product lines for this operation."""
        self.ensure_one()
        
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Product Lines'),
            'res_model': 'comex.operation.product.line',
            'view_mode': 'tree,form',
            'domain': [('operation_id', '=', self.id)],
            'context': {
                'default_operation_id': self.id,
                'search_default_group_product': 1,  # Default grouping by product
            },
        }
        
        return action

    def action_sync_product_lines(self):
        """Manually trigger synchronization of product lines.
        
        Forces immediate sync of this operation's product lines.
        """
        self.ensure_one()
        # Use the product line model's sync method
        ProductLine = self.env['comex.operation.product.line']
        ProductLine._sync_operation(self)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Product Lines Refreshed'),
                'message': _('Product lines have been refreshed from purchase orders.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_create_shipment(self):
        """Create a new shipment linked to this operation."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Shipment'),
            'res_model': 'comex.shipment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_operation_id': self.id,
                'default_operation_type': self.operation_type,
                'default_transport_mode': self.transport_mode,
                'default_etd': self.date_etd,
                'default_eta': self.date_eta,
            },
        }

    def action_create_purchase_order(self):
        """Create a new purchase order pre-linked to this COMEX operation.

        Sets the COMEX/IN picking type so the PO's receipts go directly
        to the COMEX transit location (En Viaje).
        """
        self.ensure_one()
        context = {
            'default_comex_operation_id': self.id,
            'default_partner_id': self.partner_id.id if self.partner_id else False,
        }
        # Set COMEX receipt picking type for imports
        if self.operation_type == 'import':
            comex_in_pt = self.company_id._get_comex_picking_type('in')
            if comex_in_pt:
                context['default_picking_type_id'] = comex_in_pt.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Purchase Order'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }

    def action_create_mulc(self):
        """Create a new MULC operation linked to this operation with smart defaults."""
        self.ensure_one()
        
        # Prepare context with all smart defaults
        context = {
            'default_operation_id': self.id,
            'default_mulc_type': 'import_payment' if self.operation_type == 'import' else 'export_collection',
            'default_currency_id': self.currency_id.id if self.currency_id else False,
        }
        
        # Note: Bank, due_date, and concept_code will be auto-filled by default_get()
        # in comex.mulc model based on operation's nominated_bank_id and payment terms
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create MULC Operation'),
            'res_model': 'comex.mulc',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }
