# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockRequestCount(models.TransientModel):
    _inherit = 'stock.request.count'

    assign_mode = fields.Selection(
        [
            ('none', 'Do Not Assign'),
            ('new', 'Create New Inventory Adjustment Group'),
            ('existing', 'Assign to Existing Inventory Adjustment Group'),
        ],
        default='none',
        string='Inventory Adjustment Group',
        help='Optionally assign the selected quants to a stock.inventory '
        '(Inventory Adjustment Group) in addition to requesting a count.',
    )
    new_inventory_name = fields.Char(string='New Group Name')
    inventory_id = fields.Many2one(
        'stock.inventory',
        string='Existing Group',
        domain="[('state', 'in', ('draft', 'in_progress'))]",
    )

    @api.onchange('assign_mode')
    def _onchange_assign_mode(self):
        if self.assign_mode != 'new':
            self.new_inventory_name = False
        if self.assign_mode != 'existing':
            self.inventory_id = False

    def action_request_count(self):
        super().action_request_count()
        messages = []
        for wizard in self:
            message = wizard._assign_quants_to_inventory()
            if message:
                messages.append(message)
        if messages:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Inventory Adjustment Group'),
                    'message': '\n'.join(messages),
                    'type': 'success',
                    'sticky': False,
                },
            }
        return True

    def _assign_quants_to_inventory(self):
        self.ensure_one()
        if self.assign_mode == 'none' or not self.quant_ids:
            return None

        quants = self.quant_ids.filtered(
            lambda quant: quant.location_id.usage == 'internal'
        )
        skipped_count = len(self.quant_ids) - len(quants)
        if not quants:
            raise UserError(_(
                'None of the selected quants are in internal locations; '
                'there is nothing to assign to an Inventory Adjustment '
                'Group.'
            ))

        if self.assign_mode == 'new':
            inventory = self.env['stock.inventory']._bridge_create_from_quants(
                quants, name=self.new_inventory_name
            )
        else:
            if not self.inventory_id:
                raise UserError(_(
                    'Select an existing Inventory Adjustment Group.'
                ))
            inventory = self.inventory_id
            inventory._bridge_assign_quants(quants)

        message = _(
            '%(count)s quant(s) assigned to %(name)s.',
            count=len(quants), name=inventory.display_name,
        )
        if skipped_count:
            message = '%s %s' % (message, _(
                '%(count)s quant(s) skipped (non-internal location).',
                count=skipped_count,
            ))
        return message
