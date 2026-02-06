# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ComexShipment(models.Model):
    """Shipment model for tracking individual cargo shipments within a COMEX operation."""

    _name = 'comex.shipment'
    _description = 'COMEX Shipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_departure desc, name desc'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="BL/AWB Number",
        required=True,
        copy=False,
        tracking=True,
        index='trigram',
        help="Bill of Lading or Air Waybill number - Primary identifier for this shipment.",
    )
    internal_reference = fields.Char(
        string="Internal Reference",
        readonly=True,
        copy=False,
        default=lambda self: _('New'),
        help="Internal tracking number (auto-generated for audit purposes).",
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
    stage_id = fields.Many2one(
        'comex.operation.stage',
        string="Shipment Stage",
        compute='_compute_default_stage',
        store=True,
        readonly=False,
        tracking=True,
        domain="['|', ('operation_type', '=', 'all'), ('operation_type', '=', operation_id.operation_type)]",
        help="Individual stage for this shipment (may differ from operation stage). "
             "Automatically inherits operation stage on creation. "
             "Only shows stages compatible with the operation type.",
    )
    current_location_id = fields.Many2one(
        'stock.location',
        string="Current Location",
        domain="[('usage', '=', 'transit')]",
        tracking=True,
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('operation_id.stage_id')
    def _compute_default_stage(self):
        """Set default stage from operation when shipment is created.
        
        Edge cases handled:
        - Edge Case 1: Assign operation's stage as default on create
        - Edge Case 8: Use context to prevent infinite loops with operation stage sync
        - Edge Case 10: Maintain default= in field definition
        
        This only runs on creation. After that, stage can be modified independently.
        """
        for record in self:
            # Only set if stage is not already set
            if not record.stage_id and record.operation_id and record.operation_id.stage_id:
                record.stage_id = record.operation_id.stage_id

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to prevent infinite loops when syncing stages.
        
        Edge Case 8: Use context to prevent operation stage recalculation
        during shipment creation, avoiding circular dependencies.
        """
        # Create shipments with context to skip operation stage sync
        shipments = super(ComexShipment, self.with_context(skip_stage_sync=True)).create(vals_list)
        return shipments

    def write(self, vals):
        """Override write to handle stage changes properly.
        
        When stage_id changes on a shipment, allow operation stage to recalculate
        (don't use skip_stage_sync context).
        """
        # Normal write - will trigger operation stage recalculation via @api.depends
        return super(ComexShipment, self).write(vals)

    # Transport details
    transport_mode = fields.Selection(
        selection=[
            ('sea', 'Sea'),
            ('air', 'Air'),
            ('land', 'Land'),
        ],
        string="Transport Mode",
        default='sea',
        tracking=True,
    )
    vessel_name = fields.Char(
        string="Vessel/Flight/Vehicle",
        tracking=True,
    )
    voyage_number = fields.Char(
        string="Voyage/Flight Number",
        tracking=True,
    )
    bl_date = fields.Date(
        string="BL/AWB Date",
        tracking=True,
        help="Issue date of Bill of Lading or Air Waybill.",
    )

    # Containers (using native stock.quant.package)
    package_ids = fields.One2many(
        'stock.quant.package',
        'comex_shipment_id',
        string="Containers",
        domain="[('comex_shipment_id', '!=', False)]",
        help="Shipping containers for this shipment (tracked as packages)",
    )
    container_count = fields.Integer(
        string="Container Count",
        compute='_compute_container_count',
    )

    # Dates
    date_departure = fields.Date(
        string="Departure Date",
        tracking=True,
    )
    date_eta = fields.Date(
        string="ETA",
        tracking=True,
    )
    date_arrival = fields.Date(
        string="Actual Arrival",
        tracking=True,
    )

    # Ports
    origin_port_id = fields.Many2one(
        'comex.port',
        string="Origin Port",
        tracking=True,
    )
    destination_port_id = fields.Many2one(
        'comex.port',
        string="Destination Port",
        tracking=True,
    )

    # Carrier
    carrier_id = fields.Many2one(
        'res.partner',
        string="Carrier",
        domain="[('is_shipping_line', '=', True)]",
        tracking=True,
    )

    # Weights and measures
    weight_gross = fields.Float(
        string="Gross Weight (Kg)",
    )
    weight_net = fields.Float(
        string="Net Weight (Kg)",
    )
    volume = fields.Float(
        string="Volume (m³)",
    )
    packages_qty = fields.Integer(
        string="Packages",
    )
    packages_type = fields.Char(
        string="Package Type",
    )

    # State (computed from pickings)
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('in_transit', 'In Transit'),
            ('at_port', 'At Port'),
            ('at_fiscal', 'At Fiscal Depot'),
            ('nationalized', 'Nationalized'),
        ],
        string="State",
        compute='_compute_state',
        store=True,
        tracking=True,
    )
    transit_days = fields.Integer(
        string="Transit Days",
        compute='_compute_transit_days',
        store=True,
    )

    # Related stock
    picking_ids = fields.One2many(
        'stock.picking',
        'comex_shipment_id',
        string="Stock Transfers",
    )
    picking_count = fields.Integer(
        string="Transfer Count",
        compute='_compute_picking_count',
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    def name_get(self):
        """Show BL number when available, otherwise shipment reference."""
        result = []
        for shipment in self:
            if shipment.bl_number:
                name = shipment.bl_number
            else:
                name = shipment.name
            result.append((shipment.id, name))
        return result

    def _compute_container_count(self):
        """Count shipping containers (packages) for this shipment."""
        for record in self:
            record.container_count = len(record.package_ids)

    def _compute_picking_count(self):
        for record in self:
            record.picking_count = len(record.picking_ids)

    @api.depends('picking_ids.state', 'picking_ids.picking_type_id.sequence_code')
    def _compute_state(self):
        """Compute shipment state based on related picking states."""
        for shipment in self:
            pickings = shipment.picking_ids
            if not pickings:
                shipment.state = 'pending'
                continue

            # Check pickings by type (most advanced first)
            nat_pickings = pickings.filtered(lambda p: p.picking_type_id.sequence_code == 'COMEX/NAC')
            fiscal_pickings = pickings.filtered(lambda p: p.picking_type_id.sequence_code == 'COMEX/FIS')
            port_pickings = pickings.filtered(lambda p: p.picking_type_id.sequence_code == 'COMEX/ARR')
            receipt_pickings = pickings.filtered(lambda p: p.picking_type_id.sequence_code == 'COMEX/IN')

            # Determine state based on most advanced completed picking type
            if nat_pickings and all(p.state == 'done' for p in nat_pickings):
                shipment.state = 'nationalized'
            elif fiscal_pickings and all(p.state == 'done' for p in fiscal_pickings):
                shipment.state = 'at_fiscal'
            elif port_pickings and all(p.state == 'done' for p in port_pickings):
                shipment.state = 'at_port'
            elif receipt_pickings and all(p.state == 'done' for p in receipt_pickings):
                shipment.state = 'in_transit'
            else:
                shipment.state = 'pending'

    @api.depends('date_departure', 'date_arrival')
    def _compute_transit_days(self):
        for record in self:
            if record.date_departure and record.date_arrival:
                record.transit_days = (record.date_arrival - record.date_departure).days
            elif record.date_departure and record.date_eta:
                record.transit_days = (record.date_eta - record.date_departure).days
            else:
                record.transit_days = 0

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('internal_reference', _('New')) == _('New'):
                vals['internal_reference'] = self.env['ir.sequence'].next_by_code('comex.shipment') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_view_pickings(self):
        """Open related stock transfers."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Transfers'),
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
            'context': {'default_comex_shipment_id': self.id},
        }
    def action_view_containers(self):
        """Open related containers (packages)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Containers'),
            'res_model': 'stock.quant.package',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.package_ids.ids)],
            'context': {
                'default_comex_shipment_id': self.id,
                'search_default_comex_shipment_id': self.id,
            },
        }
