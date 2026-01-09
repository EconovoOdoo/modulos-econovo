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
    stage_id = fields.Many2one(
        'comex.operation.stage',
        string="Shipment Stage",
        tracking=True,
        help="Individual stage for this shipment (may differ from operation stage).",
    )
    current_location_id = fields.Many2one(
        'stock.location',
        string="Current Location",
        domain="[('usage', '=', 'transit')]",
        tracking=True,
    )

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
    bl_number = fields.Char(
        string="BL/AWB Number",
        tracking=True,
        help="Bill of Lading or Air Waybill number.",
    )
    bl_date = fields.Date(
        string="BL/AWB Date",
        tracking=True,
    )

    # Container details
    container_ids = fields.One2many(
        'comex.shipment.container',
        'shipment_id',
        string="Containers",
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
    # Keep char fields for backwards compatibility
    origin_port = fields.Char(
        string="Origin Port (Text)",
    )
    destination_port = fields.Char(
        string="Destination Port (Text)",
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
    def _compute_container_count(self):
        for record in self:
            record.container_count = len(record.container_ids)

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
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('comex.shipment') or _('New')
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


class ComexShipmentContainer(models.Model):
    """Container details for shipments."""

    _name = 'comex.shipment.container'
    _description = 'COMEX Shipment Container'
    _order = 'container_number'

    shipment_id = fields.Many2one(
        'comex.shipment',
        string="Shipment",
        required=True,
        ondelete='cascade',
    )
    container_number = fields.Char(
        string="Container Number",
        required=True,
    )
    container_type_id = fields.Many2one(
        'comex.container.type',
        string="Container Type",
    )
    # Keep selection for backwards compatibility
    container_type = fields.Selection(
        selection=[
            ('20GP', "20' General Purpose"),
            ('40GP', "40' General Purpose"),
            ('40HC', "40' High Cube"),
            ('20RF', "20' Reefer"),
            ('40RF', "40' Reefer"),
            ('other', "Other"),
        ],
        string="Container Type (Legacy)",
        default='40HC',
    )
    seal_number = fields.Char(
        string="Seal Number",
    )
    weight_gross = fields.Float(
        string="Gross Weight (kg)",
    )
    weight_net = fields.Float(
        string="Net Weight (kg)",
    )
    volume = fields.Float(
        string="Volume (m³)",
    )
