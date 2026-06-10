from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.constrains('quantity')
    def _check_quantity(self):
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure'
        )
        if any(self.filtered(lambda x: x.scrapped)):
            return

        moves = self.filtered(
            lambda x:
            x.picking_id.picking_type_id.block_additional_quantity and
            float_compare(
                x.product_uom_qty,
                x.quantity,
                precision_digits=precision,
            ) == -1
        )
        if not moves:
            return

        # Mirror the upstream behavior for scheduler/superuser writes.
        if self.env.is_superuser():
            for move in moves:
                move.quantity = move.product_uom_qty
                if move.picking_id:
                    move.picking_id.message_post(
                        body=_(
                            'An automatic process attempted to transfer a '
                            'quantity greater than the initial demand on move '
                            '%s. The system ignored the change and kept the '
                            'original quantity.'
                        ) % move.display_name
                    )
            return

        raise ValidationError(_('You can not transfer more than the initial demand!'))
