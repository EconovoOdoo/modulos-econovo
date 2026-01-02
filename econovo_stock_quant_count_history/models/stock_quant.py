from odoo import _, api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    count_history_ids = fields.One2many(
        'stock.quant.count.history',
        'quant_id',
        string='Count History',
    )
    count_history_count = fields.Integer(
        string='# Counts',
        compute='_compute_count_history_count',
        help='Number of count history records for this quant',
    )

    # Fields from last count history record
    last_count_quantity = fields.Float(
        string='Last Counted Qty',
        compute='_compute_last_count_info',
        store=True,
        digits='Product Unit of Measure',
        help='Quantity counted in the last count history record',
    )
    last_count_user_id = fields.Many2one(
        'res.users',
        string='Last Counted By',
        compute='_compute_last_count_info',
        store=True,
        help='User who performed the last count',
    )
    last_count_difference = fields.Float(
        string='Diff vs Last Count',
        compute='_compute_last_count_difference',
        digits='Product Unit of Measure',
        help='Difference between current inventory quantity and last counted quantity',
    )

    @api.depends('count_history_ids')
    def _compute_count_history_count(self):
        for quant in self:
            quant.count_history_count = len(quant.count_history_ids)

    @api.depends('count_history_ids.quantity_counted', 'count_history_ids.counted_by_id')
    def _compute_last_count_info(self):
        """Compute fields from the most recent count history record."""
        for quant in self:
            # count_history_ids is ordered by count_datetime desc, id desc
            last_history = quant.count_history_ids[:1]
            if last_history:
                quant.last_count_quantity = last_history.quantity_counted
                quant.last_count_user_id = last_history.counted_by_id
            else:
                quant.last_count_quantity = 0.0
                quant.last_count_user_id = False

    @api.depends('inventory_quantity', 'last_count_quantity')
    def _compute_last_count_difference(self):
        """Compute difference between current inventory qty and last counted qty."""
        for quant in self:
            quant.last_count_difference = quant.inventory_quantity - quant.last_count_quantity

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
            'counted_by_id': self.user_id.id if self.user_id else False,
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
        
        The inventory_name from context (set by stock.inventory.adjustment.name wizard)
        is captured and used as the notes for the history records.
        """
        # Get the inventory adjustment reference from context (if any)
        inventory_name = self.env.context.get('inventory_name', False)
        
        # Capture values before applying (only for quants with inventory set)
        history_vals_list = []
        for quant in self.filtered(lambda q: q.inventory_quantity_set):
            vals = quant._prepare_count_history_values(state='applied')
            # Use inventory_name as notes if available
            if inventory_name:
                vals['notes'] = inventory_name
            else:
                vals['notes'] = _('Inventory adjustment applied')
            history_vals_list.append(vals)
        
        # Call original method
        result = super().action_apply_inventory()
        
        # Create history records after successful application
        if history_vals_list:
            self.env['stock.quant.count.history'].create(history_vals_list)
        
        return result

    def action_open_save_count_wizard(self):
        """Open wizard to save count to history with notes."""
        quants_with_count = self.filtered(lambda q: q.inventory_quantity_set)
        
        if not quants_with_count:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Counts to Save'),
                    'message': _('No quants have a counted quantity set.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        return {
            'name': _('Save Count to History'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant.save.count.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': quants_with_count.ids,
                'active_model': 'stock.quant',
            },
        }

    def action_save_count_to_history(self, notes=False):
        """Save current count to history without applying adjustment.
        
        This allows users to record a count for audit purposes
        without actually adjusting the inventory.
        
        Args:
            notes: Optional notes to add to the history records
        """
        history_vals_list = []
        for quant in self.filtered(lambda q: q.inventory_quantity_set):
            vals = quant._prepare_count_history_values(state='saved')
            vals['notes'] = notes or _('Count saved manually')
            history_vals_list.append(vals)
        
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
