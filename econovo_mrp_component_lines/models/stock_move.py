# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    production_plan_id = fields.Many2one(
        related='raw_material_production_id.plan_id',
        string='Production Plan',
        store=True,
    )

    def _get_supply_picking(self):
        """Return the transfer that supplied this component to its source
        location (e.g. the "Choose components" transfer moving it from
        stock to the pre-production location), if any.
        """
        self.ensure_one()
        return self.move_orig_ids[:1].picking_id

    def _get_supply_production(self):
        """Return the Manufacturing Order(s) the moves in `self` supply
        components for.

        The move of a "Choose components" transfer isn't linked to the MO
        directly: only the actual consumption move further down the
        destination chain has `raw_material_production_id` set. This follows
        `move_dest_ids` until finding one that does, for every move in `self`.
        """
        productions = self.env['mrp.production']
        for move in self:
            current = move
            seen = self.browse()
            while current and not current.raw_material_production_id and current not in seen:
                seen |= current
                current = current.move_dest_ids[:1]
            productions |= current.raw_material_production_id
        return productions

    def action_open_supply_picking(self):
        """Open the form view of the transfer that supplied this component,
        reusing stock_barcode's own action_open_picking so it behaves
        exactly like every other "open transfer" button in Odoo.
        """
        picking = self._get_supply_picking()
        if not picking:
            raise UserError(_("This component has no linked supply transfer."))
        return picking.action_open_picking()

    def action_open_supply_picking_barcode(self):
        """Open the transfer that supplied this component directly in the
        Barcode app, reusing stock_barcode's own client action so it
        behaves exactly like every other "open in Barcode" button in Odoo.
        """
        picking = self._get_supply_picking()
        if not picking:
            raise UserError(_("This component has no linked supply transfer."))
        return picking.action_open_picking_client_action()
