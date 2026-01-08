# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ComexPort(models.Model):
    _name = 'comex.port'
    _description = 'Port'
    _order = 'country_id, name'
    _rec_names_search = ['name', 'code']

    name = fields.Char(
        string="Port Name",
        required=True,
        translate=True,
    )
    code = fields.Char(
        string="UN/LOCODE",
        size=5,
        help="United Nations Code for Trade and Transport Locations (UN/LOCODE)",
    )
    country_id = fields.Many2one(
        'res.country',
        string="Country",
        required=True,
    )
    port_type = fields.Selection(
        selection=[
            ('sea', 'Seaport'),
            ('air', 'Airport'),
            ('land', 'Land Border'),
            ('river', 'River Port'),
        ],
        string="Port Type",
        default='sea',
        required=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )
    notes = fields.Text(
        string="Notes",
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'The UN/LOCODE must be unique!'),
    ]

    def name_get(self):
        result = []
        for port in self:
            name = port.name
            if port.code:
                name = "[%s] %s" % (port.code, name)
            result.append((port.id, name))
        return result
