# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from markupsafe import Markup

from odoo import _, api, Command, fields, models


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    origin_batch_id = fields.Many2one(
        'stock.picking.batch', string='Origin Batch Transfer',
        copy=False, index=True, readonly=True, check_company=True,
        help="Batch transfer whose validation generated the backorders of this batch.")
    backorder_batch_ids = fields.One2many(
        'stock.picking.batch', 'origin_batch_id', string='Backorder Batch Transfers')
    backorder_batch_count = fields.Integer(compute='_compute_backorder_batch_count')

    @api.depends('backorder_batch_ids')
    def _compute_backorder_batch_count(self):
        for batch in self:
            batch.backorder_batch_count = len(batch.backorder_batch_ids)

    def action_view_backorder_batches(self):
        self.ensure_one()
        xml_id = 'stock_picking_batch.action_picking_tree_wave' if self.is_wave \
            else 'stock_picking_batch.stock_picking_batch_action'
        action = self.env['ir.actions.act_window']._for_xml_id(xml_id)
        action['context'] = {}
        if len(self.backorder_batch_ids) == 1:
            action['res_id'] = self.backorder_batch_ids.id
            action['view_mode'] = 'form'
            action['views'] = [(False, 'form')]
        else:
            action['domain'] = [('id', 'in', self.backorder_batch_ids.ids)]
        return action

    def _create_backorder_batch(self, backorders):
        """Create the batch transfer grouping `backorders` under this batch."""
        self.ensure_one()
        new_batch = self.env['stock.picking.batch'].with_company(self.company_id).create(
            self._prepare_backorder_batch_values(backorders))
        if self.picking_type_id.backorder_batch_state == 'in_progress':
            new_batch.action_confirm()
        self.message_post(body=Markup("%s %s") % (
            _("The backorders have been grouped into the batch transfer"),
            new_batch._get_html_link()))
        return new_batch

    def _prepare_backorder_batch_values(self, backorders):
        self.ensure_one()
        return {
            'company_id': self.company_id.id,
            'is_wave': self.is_wave,
            'origin_batch_id': self.id,
            'picking_ids': [Command.set(backorders.ids)],
            'picking_type_id': self.picking_type_id.id,
            'user_id': self.user_id.id,
        }
