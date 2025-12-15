from odoo import _, api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    count_history_ids = fields.One2many(
        'stock.quant.count.history',
        'quant_id',
        string='Count History',
    )
    count_history_count = fields.Integer(
        string='Count History',
        compute='_compute_count_history_count',
    )

    @api.depends('count_history_ids')
    def _compute_count_history_count(self):
        for quant in self:
            quant.count_history_count = len(quant.count_history_ids)

    def _prepare_count_history_values(self, state='applied'):
        """Prepare values for creating count history record.
        
        This method is designed to be easily extensible in child modules.
        
        Args:
            state: The state of the count history ('saved' or 'applied')
            
        Returns:
            dict: Values for stock.quant.count.history creation
        """
        self.ensure_one()
        return {
            'quant_id': self.id,
            'company_id': self.company_id.id,
            'product_id': self.product_id.id,
            'location_id': self.location_id.id,
            'lot_id': self.lot_id.id if self.lot_id else False,
            'package_id': self.package_id.id if self.package_id else False,
            'owner_id': self.owner_id.id if self.owner_id else False,
            'quantity_on_hand': self.quantity,
            'quantity_counted': self.inventory_quantity,
            'user_id': self.env.user.id,
            'count_datetime': fields.Datetime.now(),
            'state': state,
            'was_applied': state == 'applied' and self.inventory_diff_quantity != 0,
        }

    def action_apply_inventory(self):
        """Extend to create count history when applying inventory adjustment.
        
        This extension follows non-invasive patterns:
        1. Capture values BEFORE applying (quantities may change)
        2. Call original method
        3. Create history records AFTER successful application
        """
        # Capture values before applying (only for quants with inventory set)
        history_vals_list = []
        for quant in self.filtered(lambda q: q.inventory_quantity_set):
            history_vals_list.append(quant._prepare_count_history_values(state='applied'))
        
        # Call original method
        result = super().action_apply_inventory()
        
        # Create history records after successful application
        if history_vals_list:
            self.env['stock.quant.count.history'].create(history_vals_list)
        
        return result

    def action_save_count_to_history(self):
        """Save current count to history without applying adjustment.
        
        This allows users to record a count for audit purposes
        without actually adjusting the inventory.
        """
        history_vals_list = []
        for quant in self.filtered(lambda q: q.inventory_quantity_set):
            history_vals_list.append(quant._prepare_count_history_values(state='saved'))
        
        if history_vals_list:
            self.env['stock.quant.count.history'].create(history_vals_list)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Count Saved'),
                'message': _('The counted quantity has been saved to history.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_count_history(self):
        """Open the count history for this quant."""
        self.ensure_one()
        return {
            'name': _('Count History'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant.count.history',
            'view_mode': 'tree,form',
            'domain': [('quant_id', '=', self.id)],
            'context': {
                'default_quant_id': self.id,
                'default_product_id': self.product_id.id,
                'default_location_id': self.location_id.id,
                'default_lot_id': self.lot_id.id if self.lot_id else False,
            },
        }
