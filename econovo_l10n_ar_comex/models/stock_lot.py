# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import _, fields, models


class StockLot(models.Model):
    """Extend stock.lot with the COMEX operations that brought it in."""

    _inherit = 'stock.lot'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    comex_operation_ids = fields.Many2many(
        'comex.operation',
        string="COMEX Operations",
        compute='_compute_comex_operation_ids',
        help="COMEX operations whose transfers moved this lot or serial number.",
    )
    comex_operation_count = fields.Integer(
        string="COMEX Operation Count",
        compute='_compute_comex_operation_ids',
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    def _compute_comex_operation_ids(self):
        operation_ids_by_lot = defaultdict(set)
        stored_lots = self.filtered('id')
        if stored_lots:
            move_lines = self.env['stock.move.line'].sudo().search([
                ('lot_id', 'in', stored_lots.ids),
                ('move_id.comex_operation_id', '!=', False),
            ])
            for move_line in move_lines:
                operation_ids_by_lot[move_line.lot_id.id].add(
                    move_line.move_id.comex_operation_id.id
                )

        Operation = self.env['comex.operation']
        for lot in self:
            operations = Operation.browse(sorted(operation_ids_by_lot[lot.id]))
            lot.comex_operation_ids = operations
            lot.comex_operation_count = len(operations)

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_view_comex_operations(self):
        """Open the COMEX operations this lot went through."""
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('COMEX Operations'),
            'res_model': 'comex.operation',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.comex_operation_ids.ids)],
            'context': {'create': False},
        }
        if len(self.comex_operation_ids) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.comex_operation_ids.id
        return action
