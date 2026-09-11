# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RoomOffice(models.Model):
    _inherit = 'room.office'

    company_id = fields.Many2one(
        required=False,
        help="Leave empty to share this office -- and all its rooms -- with "
             "every company, instead of restricting it to a single one. "
             "Useful for a physical room shared between several companies "
             "of the same group with one common booking calendar.",
    )

    @api.depends('company_id')
    def _compute_display_name(self):
        super()._compute_display_name()
        # The core implementation appends the company's name unconditionally
        # (f"{office.name} - {office.company_id.name}"); patch it back up for
        # offices shared with every company, which have no single company.
        for office in self.filtered(lambda o: not o.company_id):
            office.display_name = office.name
