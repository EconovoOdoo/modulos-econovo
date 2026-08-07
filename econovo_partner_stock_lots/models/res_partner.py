# -*- coding: utf-8 -*-

from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    delivered_lot_ids = fields.One2many(
        comodel_name='stock.lot',
        inverse_name='last_delivery_partner_id',
        string='Delivered Lots & Serial Numbers',
    )
    delivered_lot_count = fields.Integer(
        string='Delivered Lots & Serial Numbers Count',
        compute='_compute_delivered_lot_count',
    )

    def _compute_delivered_lot_count(self):
        lot_model = self.env['stock.lot']
        for partner in self:
            partner.delivered_lot_count = lot_model.search_count([
                ('last_delivery_partner_id', 'child_of', partner.id),
            ])

    def action_view_delivered_lots(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'stock.action_production_lot_form'
        )
        action.update({
            'name': _('Lots & Serial Numbers'),
            'domain': [('last_delivery_partner_id', 'child_of', self.id)],
            'context': {
                'search_default_group_by_product': 1,
                'display_complete': True,
                'default_company_id': self.env.company.id,
                'default_last_delivery_partner_id': self.id,
            },
        })
        return action
