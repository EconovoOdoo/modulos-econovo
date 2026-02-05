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
        help="CIF (Cost, Insurance, Freight): FOB + Insurance + Freight. This is the customs value in foreign currency.",
    )
    # Tributes in ARS (Computed from invoice, editable before invoice creation)
    amount_duties = fields.Monetary(
        string="Import Duties (DIE)",
        currency_field='currency_ars_id',
        compute='_compute_tribute_amounts',
        inverse='_inverse_amount_duties',
        store=True,
        tracking=True,
        help="DIE (Derecho de Importación Extrazona): Import duties charged by customs on CIF value. Synced with invoice lines when vendor bill is linked.",
    )
    amount_statistics = fields.Monetary(
        string="Statistics Fee",
        currency_field='currency_ars_id',
        compute='_compute_tribute_amounts',
        inverse='_inverse_amount_statistics',
        store=True,
        tracking=True,
        help="Statistics Fee (Tasa de Estadística): Usually 3% of CIF value for statistical purposes. Synced with invoice lines when vendor bill is linked.",
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
    
    amount_fees = fields.Monetary(
        string="Other Fees",
        currency_field='currency_ars_id',
        compute='_compute_tribute_amounts',
        inverse='_inverse_amount_fees',
        store=True,
        tracking=True,
        help="Other Fees: Warehouse service, customs broker fees, or other administrative charges. Synced with invoice lines when vendor bill is linked.",
    )
    amount_total = fields.Monetary(
        string="Total Clearance Cost",
        compute='_compute_amount_total',
        store=True,
        currency_field='currency_ars_id',
        help="Total = Duties + Statistics + VAT + Additional VAT + Income Tax + Gross Income + Other Taxes + Fees. "
             "This is the declared total; actual invoice total may differ due to automatic tax calculation.",
    )
    vep_amount = fields.Monetary(
        string="VEP Amount",
        currency_field='currency_ars_id',
        tracking=True,
        help="Total amount paid via VEP (Volante Electrónico de Pago) to ARCA. Found in Document Type 66 (Despacho de Importación).",
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
    @api.depends('vendor_bill_id.invoice_line_ids.price_subtotal', 
                 'vendor_bill_id.invoice_line_ids.product_id')
    def _compute_tribute_amounts(self):
        """Compute tribute amounts from vendor bill invoice lines.
        
        Smart bidirectional sync:
        - If vendor_bill_id exists: read from invoice lines (single source of truth)
        - If no vendor_bill_id: preserve manual values (editable before invoice creation)
        
        This ensures amounts are always in sync with the invoice when linked.
        """
        for record in self:
            if not record.vendor_bill_id or not record.vendor_bill_id.invoice_line_ids:
                # No invoice: keep current values (manual entry or defaults)
                # Important: Don't set to 0, preserve what user entered
                continue
            
            # Parse invoice lines to compute amounts
            record._compute_from_invoice_lines()
    
    def _compute_from_invoice_lines(self):
        """Helper: Parse invoice lines and compute tribute amounts.
        
        Called by:
        - _compute_tribute_amounts (automatic trigger)
        - write() method when vendor_bill_id changes
        """
        self.ensure_one()
        
        if not self.vendor_bill_id:
            return
        
        # Load product mappings
        ProductMapping = self.env['comex.tribute.product.mapping'].sudo()
        product_mappings = ProductMapping.search([
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ])
        
        # Build fast lookup: product_id → tribute_field_name
        product_to_field = {
            m.product_id.id: m.tribute_field_id.technical_name
            for m in product_mappings
        }
        
        # Load keyword mappings
        KeywordMapping = self.env['comex.tribute.keyword.mapping'].sudo()
        keyword_mappings = KeywordMapping.search([
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ], order='priority desc, sequence')
        
        # Initialize amounts
        amounts = {
            'amount_duties': 0,
            'amount_statistics': 0,
            'amount_fees': 0,
        }
        
        # Parse invoice lines
        for line in self.vendor_bill_id.invoice_line_ids:
            amount = abs(line.price_subtotal)
            matched_field = None
            
            # Try product mapping
            if line.product_id and line.product_id.id in product_to_field:
                matched_field = product_to_field[line.product_id.id]
            
            # Try keyword mapping
            if not matched_field and keyword_mappings:
                line_text = (line.name or '') + ' ' + (line.product_id.name or '') if line.product_id else (line.name or '')
                line_text = line_text.lower().strip()
                
                for mapping in keyword_mappings:
                    if mapping.check_match(line_text):
                        matched_field = mapping.tribute_field_id.technical_name
                        if mapping.stop_on_match:
                            break
            
            # Accumulate amount
            if matched_field and matched_field in amounts:
                amounts[matched_field] += amount
        
        # Update fields (this will NOT trigger inverse because we're in compute)
        self.amount_duties = amounts['amount_duties']
        self.amount_statistics = amounts['amount_statistics']
        self.amount_fees = amounts['amount_fees']
    
    def _update_parse_logs(self):
        """Update parse logs for audit trail.
        
        Creates parse log entries for each invoice line showing how it was matched.
        Called after vendor_bill_id changes to maintain audit trail.
        """
        self.ensure_one()
        
        if not self.vendor_bill_id or not self.vendor_bill_id.invoice_line_ids:
            return
        
        # Delete old logs
        self.env['comex.tribute.parse.log'].sudo().search([
            ('customs_clearance_id', '=', self.id)
        ]).unlink()
        
        # Load mappings
        ProductMapping = self.env['comex.tribute.product.mapping'].sudo()
        product_mappings = ProductMapping.search([
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ])
        
        product_to_mapping = {m.product_id.id: m for m in product_mappings}
        
        KeywordMapping = self.env['comex.tribute.keyword.mapping'].sudo()
        keyword_mappings = KeywordMapping.search([
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ], order='priority desc, sequence')
        
        ParseLog = self.env['comex.tribute.parse.log'].sudo()
        
        # Create logs for each line
        for line in self.vendor_bill_id.invoice_line_ids:
            amount = abs(line.price_subtotal)
            matched = False
            match_info = {}
            
            # Try product mapping
            if line.product_id and line.product_id.id in product_to_mapping:
                mapping = product_to_mapping[line.product_id.id]
                matched = True
                match_info = {
                    'matched_by': 'product',
                    'mapping_record': f'comex.tribute.product.mapping,{mapping.id}',
                    'tribute_field': mapping.tribute_field_id.technical_name,
                }
            
            # Try keyword mapping
            if not matched and keyword_mappings:
                line_text = (line.name or '') + ' ' + (line.product_id.name or '') if line.product_id else (line.name or '')
                line_text = line_text.lower().strip()
                
                for mapping in keyword_mappings:
                    if mapping.check_match(line_text):
                        matched = True
                        match_info = {
                            'matched_by': 'keyword',
                            'mapping_record': f'comex.tribute.keyword.mapping,{mapping.id}',
                            'tribute_field': mapping.tribute_field_id.technical_name,
                        }
                        if mapping.stop_on_match:
                            break
            
            # Create log
            log_vals = {
                'customs_clearance_id': self.id,
                'invoice_id': self.vendor_bill_id.id,
                'invoice_line_id': line.id,
                'amount_parsed': amount if matched else 0,
                'currency_id': self.vendor_bill_id.currency_id.id,
                'line_description': line.name or '',
                'product_name': line.product_id.name if line.product_id else '',
            }
            
            if matched:
                log_vals.update(match_info)
            else:
                log_vals['matched_by'] = 'unmatched'
            
            ParseLog.create(log_vals)
    
    def _inverse_amount_duties(self):
        """Update invoice line when amount_duties is edited manually."""
        self._inverse_tribute_amount('amount_duties')
    
    def _inverse_amount_statistics(self):
        """Update invoice line when amount_statistics is edited manually."""
        self._inverse_tribute_amount('amount_statistics')
    
    def _inverse_amount_fees(self):
        """Update invoice line when amount_fees is edited manually."""
        self._inverse_tribute_amount('amount_fees')
    
    def _inverse_tribute_amount(self, field_name):
        """Update corresponding invoice line when tribute amount is edited.
        
        Args:
            field_name: 'amount_duties', 'amount_statistics', or 'amount_fees'
        
        Behavior:
        - If no invoice: do nothing (manual value preserved for later invoice creation)
        - If invoice exists: find corresponding line and update price_unit
        - If line doesn't exist: create new line with configured product
        """
        for record in self:
            if not record.vendor_bill_id:
                # No invoice yet: manual value will be used when creating invoice
                continue
            
            if record.vendor_bill_id.state == 'posted':
                # Don't modify posted invoices
                continue
            
            new_amount = getattr(record, field_name)
            
            # Find the invoice line for this tribute field
            line = record._find_invoice_line_for_field(field_name)
            
            if line:
                # Update existing line
                if new_amount > 0:
                    line.price_unit = new_amount
                else:
                    # Remove line if amount is 0
                    line.unlink()
            elif new_amount > 0:
                # Create new line if amount > 0 and no line exists
                record._create_invoice_line_for_field(field_name, new_amount)
    
    def _find_invoice_line_for_field(self, field_name):
        """Find the invoice line corresponding to a tribute field.
        
        Returns:
            account.move.line or False
        """
        self.ensure_one()
        
        if not self.vendor_bill_id:
            return False
        
        # Load product mappings for this field
        ProductMapping = self.env['comex.tribute.product.mapping'].sudo()
        mapping = ProductMapping.search([
            ('tribute_field_id.technical_name', '=', field_name),
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not mapping or not mapping.product_id:
            return False
        
        # Find line with this product
        return self.vendor_bill_id.invoice_line_ids.filtered(
            lambda l: l.product_id == mapping.product_id
        )[:1]  # First match
    
    def _create_invoice_line_for_field(self, field_name, amount):
        """Create invoice line for a tribute field.
        
        Args:
            field_name: 'amount_duties', 'amount_statistics', or 'amount_fees'
            amount: Amount to set
        """
        self.ensure_one()
        
        if not self.vendor_bill_id or self.vendor_bill_id.state == 'posted':
            return
        
        # Load product mapping
        ProductMapping = self.env['comex.tribute.product.mapping'].sudo()
        mapping = ProductMapping.search([
            ('tribute_field_id.technical_name', '=', field_name),
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not mapping or not mapping.product_id:
            return
        
        # Create invoice line
        self.env['account.move.line'].with_context(check_move_validity=False).create({
            'move_id': self.vendor_bill_id.id,
            'product_id': mapping.product_id.id,
            'name': mapping.product_id.name,
            'quantity': 1,
            'price_unit': amount,
            'account_id': mapping.product_id.property_account_expense_id.id or 
                         mapping.product_id.categ_id.property_account_expense_categ_id.id,
        })

    @api.depends('amount_duties', 'amount_statistics', 'amount_fees')
    def _compute_amount_total(self):
        """Calculate total clearance cost (base amounts only - taxes calculated on invoice)."""
        for record in self:
            record.amount_total = (
                record.amount_duties +
                record.amount_statistics +
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
        - vep_amount: From total invoice amount (sum of all tributes)
        
        Note: Tribute parsing happens after save (in create/write) to avoid
        constraint violations with NewId during onchange.
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
        
        # Note: Tribute parsing will happen automatically after save

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
            'amount_duties', 'amount_statistics', 'amount_fees'
        ]
        for field in tribute_fields:
            setattr(self, field, 0)
        
        # Load active product mappings
        ProductMapping = self.env['comex.tribute.product.mapping'].sudo()
        product_mappings = ProductMapping.search([
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ])
        
        # Build fast lookup: product_id → (tribute_field_name, mapping_id)
        product_to_field = {
            m.product_id.id: (m.tribute_field_id.technical_name, m.id) 
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
            amount = abs(line.price_subtotal)
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
                        field_name = mapping.tribute_field_id.technical_name
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
        records = super().create(vals_list)
        
        # Parse logs are created automatically via compute dependency
        # No need to manually call _parse_tribute_lines_from_invoice
        # The compute method handles synchronization
        
        return records
    
    def write(self, vals):
        result = super().write(vals)
        
        # Manage parse logs when vendor_bill_id changes
        if 'vendor_bill_id' in vals:
            for record in self:
                if record.vendor_bill_id:
                    # Trigger parse log creation for audit
                    record._update_parse_logs()
                else:
                    # Clear logs if vendor bill removed (amounts are preserved by compute)
                    self.env['comex.tribute.parse.log'].sudo().search([
                        ('customs_clearance_id', '=', record.id)
                    ]).unlink()
        
        return result

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

    def action_create_tribute_invoice(self):
        """Create tribute invoice and link it to this customs clearance.
        
        Configuration via Settings > General Settings > COMEX:
        - Default vendor
        - Default document type
        """
        self.ensure_one()
        
        # Check if invoice already exists
        existing_invoice = self.env['account.move'].search([
            ('ref', '=', self.dispatch_number or self.name),
            ('move_type', '=', 'in_invoice'),
            ('state', '!=', 'cancel')
        ], limit=1)
        
        if existing_invoice:
            return {
                'name': _('Tribute Invoice'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': existing_invoice.id,
                'view_mode': 'form',
                'view_id': self.env.ref('account.view_move_form').id,
                'target': 'current',
            }
        
        ICP = self.env['ir.config_parameter'].sudo()
        default_vendor_id = int(ICP.get_param('econovo_l10n_ar_comex.default_tribute_vendor_id', default='0'))
        default_doc_type_id = int(ICP.get_param('econovo_l10n_ar_comex.default_tribute_doc_type_id', default='0'))
        
        if not default_vendor_id:
            raise UserError(_('Please configure the default tribute vendor in Settings > COMEX Configuration'))
        
        # Prepare invoice lines
        invoice_lines = self._prepare_tribute_invoice_lines()
        if not invoice_lines:
            raise UserError(_('No tribute amounts to invoice. Please enter duties, statistics, or fees.'))
        
        # Create invoice
        invoice_vals = {
            'move_type': 'in_invoice',
            'partner_id': default_vendor_id,
            'invoice_date': fields.Date.context_today(self),
            'ref': self.dispatch_number or f"Despacho {self.name}",
            'invoice_line_ids': invoice_lines,
        }
        
        if default_doc_type_id:
            invoice_vals['l10n_latam_document_type_id'] = default_doc_type_id
        
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Link invoice to clearance
        self.vendor_bill_id = invoice.id
        self.message_post(
            body=_("Tribute invoice created: %s", invoice.name),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )
        
        return {
            'name': _('Tribute Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'view_id': self.env.ref('account.view_move_form').id,
            'target': 'current',
        }

    def _prepare_tribute_invoice_lines(self):
        """Prepare invoice lines based on configuration.
        
        Returns:
            list: List of (0, 0, vals) tuples for invoice lines
        """
        ICP = self.env['ir.config_parameter'].sudo()
        line_filter = ICP.get_param('econovo_l10n_ar_comex.tribute_line_filter', default='all')
        
        # Get product mappings for fallback labels
        ProductMapping = self.env['comex.tribute.product.mapping'].sudo()
        mappings = ProductMapping.search([
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
        ])
        
        field_to_product = {}
        for mapping in mappings:
            field_name = mapping.tribute_field_id.technical_name
            if field_name not in field_to_product:
                field_to_product[field_name] = mapping.product_id
        
        tribute_field_labels = {
            'amount_duties': _('Import Duties (DIE)'),
            'amount_statistics': _('Statistics Fee'),
            'amount_vat': _('VAT'),
            'amount_vat_additional': _('Additional VAT'),
            'amount_income_tax': _('Income Tax Perception'),
            'amount_gross_income': _('Gross Income Perception'),
            'amount_taxes': _('Other Taxes'),
            'amount_fees': _('Other Fees'),
        }
        
        lines = []
        
        # Build lines based on filter mode
        if line_filter == 'selected':
            # Use configured tribute lines (ordered by sequence)
            LineConfig = self.env['comex.tribute.invoice.line.config'].sudo()
            configured_lines = LineConfig.search([
                ('company_id', '=', self.company_id.id),
                ('active', '=', True)
            ], order='sequence, id')
            
            if not configured_lines:
                # No configuration found, return empty
                return lines
            
            for config_line in configured_lines:
                field_name = config_line.tribute_field_id.technical_name
                amount = getattr(self, field_name, 0)
                
                # Skip if zero and not configured to include
                if amount == 0 and not config_line.include_if_zero:
                    continue
                
                # Use override product if specified, otherwise fallback to mapping
                product = config_line.product_id or field_to_product.get(field_name)
                
                # Use custom description if provided, otherwise use product name or field label
                if config_line.description:
                    description = config_line.description
                elif product:
                    description = product.name
                else:
                    description = tribute_field_labels.get(field_name, field_name)
                
                line_vals = {
                    'product_id': product.id if product else False,
                    'name': description,
                    'quantity': 1,
                    'price_unit': amount,
                }
                
                if product and product.property_account_expense_id:
                    line_vals['account_id'] = product.property_account_expense_id.id
                
                lines.append((0, 0, line_vals))
        
        else:
            # Include all non-zero tributes (default behavior)
            all_fields = [
                'amount_duties', 'amount_statistics', 'amount_vat', 'amount_vat_additional',
                'amount_income_tax', 'amount_gross_income', 'amount_taxes', 'amount_fees'
            ]
            
            for field_name in all_fields:
                amount = getattr(self, field_name, 0)
                if amount > 0:
                    product = field_to_product.get(field_name)
                    
                    line_vals = {
                        'product_id': product.id if product else False,
                        'name': product.name if product else tribute_field_labels.get(field_name, field_name),
                        'quantity': 1,
                        'price_unit': amount,
                    }
                    
                    if product and product.property_account_expense_id:
                        line_vals['account_id'] = product.property_account_expense_id.id
                    
                    lines.append((0, 0, line_vals))
        
        return lines

