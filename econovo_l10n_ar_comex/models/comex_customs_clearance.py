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
        help="IVA de Importación (21%)",
    )
    
    # Parse logs for audit
    parse_log_ids = fields.One2many(
        'comex.tribute.parse.log',
        'customs_clearance_id',
        string="Parse Logs",
    )
    parse_log_count = fields.Integer(
        string="Parse Logs",
        compute='_compute_parse_log_count',
    )
    parse_log_unmatched_count = fields.Integer(
        string="Unmatched Lines",
        compute='_compute_parse_log_count',
    )
    
    @api.depends('parse_log_ids')
    def _compute_parse_log_count(self):
        """Count parse logs and unmatched lines."""
        for record in self:
            record.parse_log_count = len(record.parse_log_ids)
            record.parse_log_unmatched_count = len(record.parse_log_ids.filtered(
                lambda l: l.matched_by == 'unmatched'
            ))
    
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
    vep_amount = fields.Monetary(
        string="VEP Amount",
        currency_field='currency_ars_id',
        tracking=True,
        help="VEP (Volante Electrónico de Pago) total amount paid to ARCA for this clearance. Details are in Document Type 66 (Despacho de Importación).",
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
    def _onchange_vendor_bill_id_auto_fill(self):
        """Auto-fill data from vendor bill (Document Type 66).
        
        This populates:
        - dispatch_number: From l10n_latam_document_number
        - amount_cif: From first invoice line (usually contains CIF value)
        - vep_amount: From total invoice amount (sum of all tributes)
        - Individual tributes: Parsed from invoice lines based on product/account
        
        User only needs to register the Type 66 invoice once with proper line items.
        """
        if not self.vendor_bill_id:
            return
        
        bill = self.vendor_bill_id
        
        # 1. Auto-fill dispatch number
        if hasattr(bill, 'l10n_latam_document_number') and bill.l10n_latam_document_number:
            self.dispatch_number = bill.l10n_latam_document_number
        
        # 2. Auto-fill VEP amount (total of invoice)
        if bill.amount_total:
            self.vep_amount = bill.amount_total
        
        # 3. Parse invoice lines to fill individual tribute amounts
        # Parse tribute amounts using configured mappings with audit logging
        self._parse_tribute_lines_from_invoice(bill)

    def _parse_tribute_lines_from_invoice(self, invoice):
        """Parse invoice lines using configured mappings with comprehensive audit logging.
        
        Parsing logic (three-layer approach):
        1. Try product mapping (exact match by product_id)
        2. If no product match, try keyword mapping (text pattern matching)
        3. Log every line (matched or unmatched) for audit trail
        
        Benefits:
        - Zero hardcoding - all mappings configurable from UI
        - Handles lines with or without products
        - Full audit trail of all parsing decisions
        - Unmatched lines easily identified for refinement
        - Multiple patterns can map to same tribute field (amounts summed)
        - Multi-company compatible
        
        Examples:
            Layer 1 (Product): Product "DIE - Derecho de Importación" → amount_duties
            Layer 2 (Keyword): Line with text "tasa estadística" → amount_statistics
            Layer 3 (Audit): Every line logged with match result
        
        See Settings > COMEX > Tribute Mappings for configuration.
        See Settings > COMEX > Parsing Logs for audit trail.
        """
        if not invoice or not invoice.invoice_line_ids:
            return
        
        # Delete old logs for this clearance (clean slate)
        self.env['comex.tribute.parse.log'].sudo().search([
            ('customs_clearance_id', '=', self.id)
        ]).unlink()
        
        # Reset amounts before parsing
        tribute_fields = [
            'amount_duties', 'amount_statistics', 'amount_vat', 'amount_vat_additional',
            'amount_income_tax', 'amount_gross_income', 'amount_taxes', 'amount_fees'
        ]
        for field in tribute_fields:
            setattr(self, field, 0)
        
        # Load active product mappings
        ProductMapping = self.env['comex.tribute.product.mapping'].sudo()
        product_mappings = ProductMapping.search([
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ])
        
        # Build fast lookup: product_id → (tribute_field, mapping_id)
        product_to_field = {
            m.product_id.id: (m.tribute_field, m.id) 
            for m in product_mappings
        }
        
        # Load active keyword mappings (ordered by priority desc)
        KeywordMapping = self.env['comex.tribute.keyword.mapping'].sudo()
        keyword_mappings = KeywordMapping.search([
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ], order='priority desc, sequence')
        
        ParseLog = self.env['comex.tribute.parse.log'].sudo()
        
        # Parse invoice lines
        for line in invoice.invoice_line_ids:
            amount = abs(line.price_subtotal)  # Use abs to handle credit notes
            matched = False
            match_info = {}
            
            # LAYER 1: Try product mapping (exact match)
            if line.product_id and line.product_id.id in product_to_field:
                field_name, mapping_id = product_to_field[line.product_id.id]
                current_value = getattr(self, field_name, 0)
                setattr(self, field_name, current_value + amount)
                matched = True
                match_info = {
                    'matched_by': 'product',
                    'mapping_record': f'comex.tribute.product.mapping,{mapping_id}',
                    'tribute_field': field_name,
                }
            
            # LAYER 2: Try keyword mapping (if no product match)
            if not matched and keyword_mappings:
                # Combine line description and product name for searching
                line_text = (line.name or '') + ' ' + (line.product_id.name or '') if line.product_id else (line.name or '')
                line_text = line_text.lower().strip()
                
                for mapping in keyword_mappings:
                    if mapping.check_match(line_text):
                        field_name = mapping.tribute_field
                        current_value = getattr(self, field_name, 0)
                        setattr(self, field_name, current_value + amount)
                        matched = True
                        match_info = {
                            'matched_by': 'keyword',
                            'mapping_record': f'comex.tribute.keyword.mapping,{mapping.id}',
                            'tribute_field': field_name,
                        }
                        
                        if mapping.stop_on_match:
                            break  # Stop checking other keywords
            
            # LAYER 3: Create audit log for this line
            log_vals = {
                'customs_clearance_id': self.id,
                'invoice_id': invoice.id,
                'invoice_line_id': line.id,
                'amount_parsed': amount if matched else 0,
                'currency_id': invoice.currency_id.id,
                'line_description': line.name or '',
                'product_name': line.product_id.name if line.product_id else '',
            }
            
            if matched:
                log_vals.update(match_info)
            else:
                log_vals['matched_by'] = 'unmatched'
            
            ParseLog.create(log_vals)
        
        # Show notification if there are unmatched lines
        unmatched_count = self.parse_log_unmatched_count
        if unmatched_count > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Parsing Warning'),
                    'message': _('%s invoice lines could not be matched. Check Parsing Logs to refine your configuration.', unmatched_count),
                    'type': 'warning',
                    'sticky': False,
                }
            }

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_view_parse_logs(self):
        """Open parse logs for this customs clearance."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tribute Parsing Logs'),
            'res_model': 'comex.tribute.parse.log',
            'view_mode': 'tree,form',
            'domain': [('customs_clearance_id', '=', self.id)],
            'context': {'default_customs_clearance_id': self.id},
        }

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
