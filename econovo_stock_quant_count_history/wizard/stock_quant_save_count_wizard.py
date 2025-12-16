from odoo import _, api, fields, models


class StockQuantSaveCountWizard(models.TransientModel):
    _name = 'stock.quant.save.count.wizard'
    _description = 'Save Count to History Wizard'

    quant_ids = fields.Many2many(
        'stock.quant',
        string='Quants',
        required=True,
    )
    quant_count = fields.Integer(
        string='Number of Counts',
        compute='_compute_quant_count',
    )
    quant_count_display = fields.Char(
        string='Items to Save',
        compute='_compute_quant_count',
    )
    notes = fields.Text(
        string='Notes',
        help='Notes or reason for saving this count to history',
    )

    @api.depends('quant_ids')
    def _compute_quant_count(self):
        for wizard in self:
            count = len(wizard.quant_ids)
            wizard.quant_count = count
            if count == 1:
                wizard.quant_count_display = _('1 count will be saved to history')
            else:
                wizard.quant_count_display = _('%d counts will be saved to history') % count

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            quants = self.env['stock.quant'].browse(active_ids)
            # Filter only quants with inventory_quantity_set
            quants_with_count = quants.filtered(lambda q: q.inventory_quantity_set)
            res['quant_ids'] = [(6, 0, quants_with_count.ids)]
        return res

    def action_save_count_to_history(self):
        """Save counts to history with the specified notes."""
        self.ensure_one()
        
        if not self.quant_ids:
            return {'type': 'ir.actions.act_window_close'}
        
        # Filter only quants with inventory set
        quants_to_save = self.quant_ids.filtered(lambda q: q.inventory_quantity_set)
        
        if not quants_to_save:
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
        
        # Prepare history values with notes
        history_vals_list = []
        for quant in quants_to_save:
            vals = quant._prepare_count_history_values(state='saved')
            vals['notes'] = self.notes or _('Count saved manually')
            history_vals_list.append(vals)
        
        # Create history records
        self.env['stock.quant.count.history'].create(history_vals_list)
        
        # Close wizard and show notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Counts Saved'),
                'message': _('%d count(s) have been saved to history.') % len(quants_to_save),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
