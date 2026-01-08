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
        default=lambda self: _('New'),
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
        default=_default_stage,
        tracking=True,
        group_expand='_read_group_stage_ids',
        domain="['|', ('operation_type', '=', 'all'), ('operation_type', '=', operation_type)]",
        copy=False,
    )
    current_location_id = fields.Many2one(
        'stock.location',
        string="Current COMEX Location",
        domain="[('usage', '=', 'transit')]",
        tracking=True,
        help="Specific transit location where goods are currently located. "
             "Should be a child of the stage's parent location.",
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

    # Amounts
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        tracking=True,
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

    # Incoterm
    incoterm_id = fields.Many2one(
        'account.incoterms',
        string="Incoterm",
        tracking=True,
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
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('amount_fob', 'amount_freight', 'amount_insurance')
    def _compute_amount_cif(self):
        for record in self:
            record.amount_cif = record.amount_fob + record.amount_freight + record.amount_insurance

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

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                operation_type = vals.get('operation_type', 'import')
                if operation_type == 'import':
                    vals['name'] = self.env['ir.sequence'].next_by_code('comex.operation.import') or _('New')
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code('comex.operation.export') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        # Prevent stage change if pending pickings exist
        if 'stage_id' in vals:
            for record in self:
                pending_pickings = record.picking_ids.filtered(
                    lambda p: p.state not in ('done', 'cancel')
                )
                if pending_pickings:
                    raise UserError(_(
                        "Cannot change stage while there are pending transfers:\n%(pickings)s\n\n"
                        "Please validate or cancel these transfers first.",
                        pickings='\n'.join(pending_pickings.mapped('name'))
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
    def action_view_purchase_orders(self):
        """Open related purchase orders."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.purchase_order_ids.ids)],
            'context': {'default_comex_operation_id': self.id},
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
            'context': {'default_operation_id': self.id},
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
