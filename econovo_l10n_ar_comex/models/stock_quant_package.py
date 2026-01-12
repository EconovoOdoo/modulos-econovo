# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class StockQuantPackage(models.Model):
    """Extend stock.quant.package for COMEX container tracking.
    
    This extension allows using Odoo's native package system for tracking
    shipping containers in COMEX operations, providing:
    - Automatic location tracking
    - Product-container linkage via quant_ids
    - Native stock movement integration
    - Barcode support
    """
    
    _inherit = 'stock.quant.package'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    # COMEX Relationships
    comex_shipment_id = fields.Many2one(
        'comex.shipment',
        string="COMEX Shipment",
        ondelete='set null',
        index=True,
        help="COMEX shipment to which this container belongs",
    )
    comex_operation_id = fields.Many2one(
        'comex.operation',
        string="COMEX Operation",
        related='comex_shipment_id.operation_id',
        store=True,
        help="COMEX operation (derived from shipment)",
    )

    # Container Identification
    comex_container_number = fields.Char(
        string="Container Number",
        copy=False,
        index=True,
        help="Official container number (e.g., MAEU1234567890). "
             "Standard format: 4 letters (owner) + 6 digits + 1 check digit",
    )
    comex_seal_number = fields.Char(
        string="Seal Number",
        copy=False,
        help="Customs seal number",
    )
    
    # Physical Characteristics
    comex_volume = fields.Float(
        string="Volume (m³)",
        digits=(10, 2),
        help="Container volume in cubic meters",
    )
    comex_weight_net = fields.Float(
        string="Net Weight",
        digits='Stock Weight',
        help="Net weight (cargo only, excluding tare)",
    )
    comex_weight_tare = fields.Float(
        string="Tare Weight",
        digits='Stock Weight',
        compute='_compute_comex_weight_tare',
        store=True,
        help="Container tare weight (from package type)",
    )
    comex_weight_gross = fields.Float(
        string="Gross Weight",
        digits='Stock Weight',
        compute='_compute_comex_weight_gross',
        inverse='_inverse_comex_weight_gross',
        store=True,
        help="Gross weight including tare (net weight + tare weight)",
    )
    
    # Technical
    is_comex_container = fields.Boolean(
        string="Is COMEX Container",
        compute='_compute_is_comex_container',
        store=True,
        search='_search_is_comex_container',
        help="Whether this package is a COMEX shipping container",
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('comex_shipment_id')
    def _compute_is_comex_container(self):
        """Determine if package is COMEX container."""
        for package in self:
            package.is_comex_container = bool(package.comex_shipment_id)

    def _search_is_comex_container(self, operator, value):
        """Search domain for COMEX containers."""
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('comex_shipment_id', '!=', False)]
        return [('comex_shipment_id', '=', False)]

    @api.depends('package_type_id.base_weight')
    def _compute_comex_weight_tare(self):
        """Get tare weight from package type."""
        for package in self:
            package.comex_weight_tare = package.package_type_id.base_weight or 0.0

    @api.depends('comex_weight_net', 'comex_weight_tare')
    def _compute_comex_weight_gross(self):
        """Calculate gross weight as net + tare."""
        for package in self:
            package.comex_weight_gross = package.comex_weight_net + package.comex_weight_tare

    def _inverse_comex_weight_gross(self):
        """Allow setting gross weight directly (calculates net = gross - tare)."""
        for package in self:
            if package.comex_weight_gross and package.comex_weight_tare:
                package.comex_weight_net = package.comex_weight_gross - package.comex_weight_tare

    # -------------------------------------------------------------------------
    # CONSTRAINS & ONCHANGE
    # -------------------------------------------------------------------------
    @api.onchange('comex_weight_net', 'comex_weight_tare')
    def _onchange_comex_weights(self):
        """Auto-calculate gross weight from net + tare."""
        for package in self:
            if package.comex_weight_net and package.comex_weight_tare:
                package.comex_weight_gross = package.comex_weight_net + package.comex_weight_tare

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-set name from container number if provided."""
        for vals in vals_list:
            # Use container number as name if not provided
            if vals.get('comex_container_number') and not vals.get('name'):
                vals['name'] = vals['comex_container_number']
            
            # Set location from shipment's current location if available
            if vals.get('comex_shipment_id') and not vals.get('location_id'):
                shipment = self.env['comex.shipment'].browse(vals['comex_shipment_id'])
                if shipment.current_location_id:
                    vals['location_id'] = shipment.current_location_id.id
        
        return super().create(vals_list)

    def write(self, vals):
        """Handle special cases when updating COMEX containers."""
        # Sync container number changes to name
        if 'comex_container_number' in vals and vals['comex_container_number']:
            if not vals.get('name'):
                vals['name'] = vals['comex_container_number']
        
        return super().write(vals)

    # -------------------------------------------------------------------------
    # DISPLAY METHODS
    # -------------------------------------------------------------------------
    def name_get(self):
        """Show container number for COMEX packages."""
        result = []
        for package in self:
            if package.is_comex_container and package.comex_container_number:
                # Format: MAEU1234567 (40HC) @ Puerto Buenos Aires
                parts = [package.comex_container_number]
                if package.package_type_id:
                    parts.append(f"({package.package_type_id.name})")
                if package.location_id and package.location_id.usage == 'transit':
                    parts.append(f"@ {package.location_id.name}")
                name = ' '.join(parts)
            else:
                name = super(StockQuantPackage, package).name_get()[0][1]
            result.append((package.id, name))
        return result

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_view_comex_shipment(self):
        """Open related COMEX shipment."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('COMEX Shipment'),
            'res_model': 'comex.shipment',
            'res_id': self.comex_shipment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_stock_moves(self):
        """View stock moves for this container."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Moves'),
            'res_model': 'stock.move.line',
            'view_mode': 'tree,form',
            'domain': [('result_package_id', '=', self.id)],
            'context': {
                'search_default_done': 1,
                'search_default_todo': 1,
            },
        }
