# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _get_subcontracting_purchase_orders(self):
        """Purchase order(s) behind the subcontracting Manufacturing
        Order(s) the moves in `self` resupply components for (e.g. a
        "Resupply Subcontractor" transfer), if any.

        A resupply move is never linked to the purchase order directly:
        the only real link is the procurement group it shares with the
        subcontracting MO, which in turn points to the incoming shipment
        that MO was created for.
        """
        productions = self.mapped('group_id').mapped('mrp_production_ids')
        return productions.mapped('incoming_picking').mapped('purchase_id')
