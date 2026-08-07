# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    delivered_lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        string='Delivered Lots & Serial Numbers',
        compute='_compute_delivered_lot_ids',
    )
    delivered_lot_count = fields.Integer(
        string='Delivered Lots & Serial Numbers Count',
        compute='_compute_delivered_lot_count',
    )

    def _get_lots_by_delivery_partner(self):
        """Map delivery partner id -> stock.lot recordset delivered to it.

        ``stock.lot.last_delivery_partner_id`` is not a stored/searchable
        field on this database, so any ORM domain on it (``search``,
        ``read_group``, or a plain ``One2many`` inverse) is silently dropped
        instead of raising, matching every record. It is read once for all
        lots and grouped in Python instead of filtered server-side.
        """
        lots = self.env['stock.lot'].search_fetch(
            [], ['last_delivery_partner_id'], order='id',
        )
        mapping = defaultdict(lambda: self.env['stock.lot'])
        for lot in lots:
            if lot.last_delivery_partner_id:
                mapping[lot.last_delivery_partner_id.id] |= lot
        return mapping

    def _compute_delivered_lot_count(self):
        mapping = self._get_lots_by_delivery_partner()
        for partner in self:
            partner.delivered_lot_count = len(mapping[partner.id])

    def _compute_delivered_lot_ids(self):
        mapping = self._get_lots_by_delivery_partner()
        for partner in self:
            partner.delivered_lot_ids = mapping[partner.id]

    def action_view_delivered_lots(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'stock.action_production_lot_form'
        )
        action.update({
            'name': _('Lots & Serial Numbers'),
            'domain': [('id', 'in', self.delivered_lot_ids.ids)],
            'context': {
                'search_default_group_by_product': 1,
                'display_complete': True,
                'default_company_id': self.env.company.id,
                'default_last_delivery_partner_id': self.id,
            },
        })
        return action
