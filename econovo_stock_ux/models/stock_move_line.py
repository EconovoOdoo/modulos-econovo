from odoo import _, api, models
from odoo.exceptions import ValidationError


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.constrains('quantity')
    def _check_manual_lines(self):
        # Keep compatibility with newer upstream branches.
        if 'previous_product_qty' in self.env.context:
            return
        if self._context.get('put_in_pack', False):
            return

        invalid_lines = self.filtered(
            lambda x:
            not x.location_id.should_bypass_reservation() and
            x.picking_id.picking_type_id.block_manual_lines and
            x._check_quantity_available() < 0
        )
        if not invalid_lines:
            return

        # Mirror the upstream behavior for scheduler/superuser writes.
        if self.env.is_superuser():
            for line in invalid_lines:
                line.quantity = max(0, line._check_quantity_available() + line.quantity)
                if line.picking_id:
                    line.picking_id.message_post(
                        body=_(
                            'An automatic process attempted to transfer a '
                            'quantity greater than available stock on line %s. '
                            'The system ignored the change and kept the '
                            'original quantity.'
                        ) % line.display_name
                    )
            return

        raise ValidationError(
            _('You can\'t transfer more quantity than the quantity on stock!')
        )

    def _check_quantity_available(self):
        self.ensure_one()
        total_available = 0.0
        is_storable = getattr(
            self.product_id,
            'is_storable',
            self.product_id.detailed_type == 'product',
        )
        if (
            is_storable
            and not self.env.context.get('trigger_assign')
            and not self.env.context.get('from_inverse_qty_done')
            and not self.env.context.get('sale_automation')
            and (
                self.picking_id.id in self.env.context.get('picking_ids', [])
                or not self.env.context.get('picking_ids', [])
            )
        ):
            locations = self.env['stock.location'].search([
                ('id', 'child_of', self.picking_id.location_id.id),
                ('company_id', '=', self.picking_id.company_id.id),
            ])
            quants = self.env['stock.quant'].search([
                ('product_id', '=', self.product_id.id),
                ('location_id', 'in', locations.ids),
            ])
            total_available = sum(quants.mapped('available_quantity'))
        return total_available
