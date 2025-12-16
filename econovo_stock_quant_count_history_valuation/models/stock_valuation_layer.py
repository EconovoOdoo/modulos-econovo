# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class StockValuationLayer(models.Model):
    """Extension of SVL to link to count history."""

    _inherit = 'stock.valuation.layer'

    count_history_id = fields.Many2one(
        comodel_name='stock.quant.count.history',
        string='Count History',
        readonly=True,
        index=True,
        help='Count history that generated this valuation layer',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to link SVL to count history if in context."""
        records = super().create(vals_list)

        # Check if we have count history context
        count_history_ids = self.env.context.get('count_history_ids')
        if count_history_ids:
            self._link_to_count_history(records, count_history_ids)

        return records

    def _link_to_count_history(self, svl_records, count_history_ids):
        """Link SVL records to count history records.

        Matches by product_id and quantity.
        """
        CountHistory = self.env['stock.quant.count.history']
        histories = CountHistory.browse(count_history_ids).exists()

        for svl in svl_records:
            # Find matching history
            matching_history = histories.filtered(
                lambda h: (
                    h.product_id.id == svl.product_id.id
                    and h.difference == svl.quantity
                )
            )
            if matching_history:
                svl.count_history_id = matching_history[0].id
                # Also update the valuation link
                if matching_history[0].valuation_id:
                    matching_history[0].valuation_id.write({
                        'valuation_layer_ids': [(4, svl.id)],
                    })
