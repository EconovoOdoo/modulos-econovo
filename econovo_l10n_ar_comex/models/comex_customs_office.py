# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ComexCustomsOffice(models.Model):
    _name = 'comex.customs.office'
    _description = 'Customs Office'
    _order = 'code'
    _rec_names_search = ['name', 'code']

    name = fields.Char(
        string="Name",
        required=True,
    )
    code = fields.Char(
        string="Code",
        required=True,
        size=3,
        help="ARCA (ex-AFIP) customs office code",
    )
    office_type = fields.Selection(
        selection=[
            ('main', 'Main Customs'),
            ('secondary', 'Secondary Customs'),
            ('checkpoint', 'Border Checkpoint'),
        ],
        string="Office Type",
        default='main',
    )
    address = fields.Text(
        string="Address",
    )
    city = fields.Char(
        string="City",
    )
    state_id = fields.Many2one(
        'res.country.state',
        string="Province",
        domain="[('country_id.code', '=', 'AR')]",
    )
    phone = fields.Char(
        string="Phone",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The customs office code must be unique!'),
    ]

    def name_get(self):
        result = []
        for office in self:
            name = "[%s] %s" % (office.code, office.name)
            result.append((office.id, name))
        return result
