from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockQuantCountHistory(models.Model):
    _name = 'stock.quant.count.history'
    _description = 'Inventory Count History'
    _order = 'count_datetime desc, id desc'
    _rec_name = 'name'

    # Identification
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default='/',
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    # Quant reference (can be null if quant is deleted)
    quant_id = fields.Many2one(
        'stock.quant',
        string='Quant',
        index=True,
        ondelete='set null',
    )

    # Product information (stored independently for audit trail)
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        index=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        related='product_id.uom_id',
        store=True,
    )

    # Location information
    location_id = fields.Many2one(
        'stock.location',
        string='Location',
        required=True,
        index=True,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        compute='_compute_warehouse_id',
        store=True,
        index=True,
    )

    # Tracking information
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lot/Serial Number',
        index=True,
    )
    package_id = fields.Many2one(
        'stock.quant.package',
        string='Package',
    )
    owner_id = fields.Many2one(
        'res.partner',
        string='Owner',
    )

    # Quantities
    quantity_on_hand = fields.Float(
        string='Quantity On Hand',
        required=True,
        digits='Product Unit of Measure',
        help='Quantity on hand at the moment of the count',
    )
    quantity_counted = fields.Float(
        string='Quantity Counted',
        required=True,
        digits='Product Unit of Measure',
        help='Quantity counted by the user',
    )
    difference = fields.Float(
        string='Difference',
        compute='_compute_difference',
        store=True,
        digits='Product Unit of Measure',
        help='Difference between counted and on-hand quantities',
    )

    # Audit information
    counted_by_id = fields.Many2one(
        'res.users',
        string='Counted By',
        index=True,
        help='User who physically counted the inventory (from quant assignment)',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Registered By',
        required=True,
        index=True,
        default=lambda self: self.env.user,
        help='User who saved or applied the count in the system',
    )
    count_datetime = fields.Datetime(
        string='Count Date/Time',
        required=True,
        index=True,
        default=fields.Datetime.now,
    )

    # State
    state = fields.Selection(
        selection=[
            ('saved', 'Saved Manually'),
            ('applied', 'Saved on Apply'),
        ],
        string='State',
        required=True,
        default='saved',
        index=True,
        help='Saved Manually: Count saved without applying adjustment. '
             'Saved on Apply: Count saved when applying inventory adjustment.',
    )
    was_applied = fields.Boolean(
        string='Adjustment Applied',
        default=False,
        help='Indicates if an inventory adjustment was applied (difference != 0)',
    )

    # Notes
    notes = fields.Text(
        string='Notes',
    )

    @api.depends('location_id', 'location_id.warehouse_id')
    def _compute_warehouse_id(self):
        for record in self:
            record.warehouse_id = record.location_id.warehouse_id

    @api.depends('quantity_on_hand', 'quantity_counted')
    def _compute_difference(self):
        for record in self:
            record.difference = record.quantity_counted - record.quantity_on_hand

    @api.constrains('quantity_counted', 'product_id', 'lot_id')
    def _check_serial_tracking(self):
        for record in self:
            if (record.product_id.tracking == 'serial' and
                    record.lot_id and
                    record.quantity_counted > 1):
                raise ValidationError(_(
                    "Product '%(product)s' has serial tracking. "
                    "Counted quantity cannot be greater than 1.",
                    product=record.product_id.display_name
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'stock.quant.count.history'
                ) or '/'
        return super().create(vals_list)
