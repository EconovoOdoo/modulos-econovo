# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class StockInventory(models.Model):
    _inherit = 'stock.inventory'

    product_selection = fields.Selection(
        selection_add=[('preselected', 'Preselected Quants')],
        ondelete={'preselected': 'set default'},
    )

    preselected_quant_ids = fields.Many2many(
        'stock.quant',
        relation='stock_inventory_preselected_quant_rel',
        string='Preselected Quants',
        domain="['|', ('company_id', '=', company_id), ('company_id', '=', False)]",
        copy=False,
        help='Quants manually assigned through the "Request a Count" bridge. '
        'Used as the quant source when "Preselected Quants" is the '
        'selection mode.',
    )

    def _get_quants(self, locations):
        if self.product_selection == 'preselected':
            return self.preselected_quant_ids
        return super()._get_quants(locations)

    def _bridge_has_own_criteria(self):
        self.ensure_one()
        return bool(
            self.product_ids or self.location_ids
            or self.category_id or self.lot_ids
        )

    def _bridge_create_from_quants(self, quants, name=None):
        """Create a new draft Inventory Adjustment Group from arbitrary
        stock.quant records selected in the classic quant list view."""
        companies = quants.company_id
        if len(companies) > 1:
            raise UserError(_(
                'Selected stock quants belong to different companies '
                '(%(names)s). Assign them separately, one company at a '
                'time.',
                names=', '.join(companies.mapped('name')),
            ))
        return self.create({
            'name': name or _(
                'Inventory - %(date)s', date=fields.Date.context_today(self)
            ),
            'company_id': companies.id if companies else self.env.company.id,
            'product_selection': 'preselected',
            'preselected_quant_ids': [(6, 0, quants.ids)],
            'location_ids': [(6, 0, quants.location_id.ids)],
            'exclude_sublocation': True,
        })

    def _bridge_assign_quants(self, quants):
        """Assign existing stock.quant records to this Inventory Adjustment
        Group, without forcing a state change (draft stays draft, in
        progress stays in progress)."""
        self.ensure_one()
        if self.state in ('done', 'cancel'):
            raise UserError(_(
                'You cannot assign quants to %(name)s because it is '
                '%(state)s.',
                name=self.display_name, state=self.state,
            ))
        mismatched = quants.filtered(
            lambda quant: quant.company_id and quant.company_id != self.company_id
        )
        if mismatched:
            raise UserError(_(
                "Some selected quants do not belong to %(name)s's company "
                '(%(company)s).',
                name=self.display_name, company=self.company_id.name,
            ))

        can_manage_criteria = (
            self.product_selection == 'preselected'
            or not self._bridge_has_own_criteria()
        )
        if self.state == 'draft' and not can_manage_criteria:
            raise UserError(_(
                "%(name)s already uses the '%(mode)s' selection mode. "
                'Assigning individual quants would override its criteria; '
                'create a new adjustment group instead.',
                name=self.display_name,
                mode=dict(self._fields['product_selection'].selection).get(
                    self.product_selection
                ),
            ))

        if self.state == 'in_progress':
            conflicting = quants.filtered(
                lambda quant: quant.to_do and quant.current_inventory_id
                and quant.current_inventory_id != self
            )
            if conflicting:
                raise ValidationError(_(
                    'Some quants are already being counted in another '
                    'in-progress adjustment: %(names)s',
                    names=', '.join(
                        conflicting.mapped('current_inventory_id.display_name')
                    ),
                ))
            quants.write({
                'to_do': True,
                'user_id': self.responsible_id.id,
                'inventory_date': self.date,
                'current_inventory_id': self.id,
            })
            self.stock_quant_ids = [(4, quant.id) for quant in quants]

        values = {
            'preselected_quant_ids': [(4, quant.id) for quant in quants],
        }
        if can_manage_criteria:
            values.update({
                'product_selection': 'preselected',
                'location_ids': [(4, location.id) for location in quants.location_id],
                'exclude_sublocation': True,
            })
        self.write(values)
        self.message_post(body=_(
            '%(count)s stock quant(s) assigned by %(user)s via the '
            'Request a Count bridge.',
            count=len(quants), user=self.env.user.name,
        ))
