from odoo import api, fields, models


class StockQuantPutawaySingleLine(models.TransientModel):
    _name = 'stock.quant.putaway.single.line'
    _description = 'Stock Quant Putaway Single Line'

    wizard_id = fields.Many2one(
        comodel_name='stock.quant.putaway.single',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    putaway_rule_id = fields.Many2one(
        comodel_name='stock.putaway.rule',
        string='Putaway Rule',
        readonly=True,
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        readonly=True,
    )
    location_in_id = fields.Many2one(
        comodel_name='stock.location',
        string='When Product Arrives In',
        readonly=True,
    )
    location_out_id = fields.Many2one(
        comodel_name='stock.location',
        string='Store To',
        readonly=True,
    )
    sequence = fields.Integer(
        string='Priority',
        readonly=True,
    )
    is_current_location = fields.Boolean(
        string='Is Current Location',
        compute='_compute_is_current_location',
        help='True if this rule points to the same location as the quant',
    )

    @api.depends('location_out_id', 'wizard_id.quant_id.location_id')
    def _compute_is_current_location(self):
        for line in self:
            line.is_current_location = (
                line.location_out_id == line.wizard_id.quant_id.location_id
            )

    def action_delete_rule(self):
        """Delete the associated putaway rule."""
        self.ensure_one()
        if self.putaway_rule_id:
            self.putaway_rule_id.unlink()
        return {'type': 'ir.actions.act_window_close'}
