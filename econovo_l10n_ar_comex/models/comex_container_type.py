# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ComexContainerType(models.Model):
    _name = 'comex.container.type'
    _description = 'Container Type'
    _order = 'sequence, name'

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
    )
    code = fields.Char(
        string="ISO Code",
        size=4,
        help="ISO 6346 container size and type code",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    size_feet = fields.Selection(
        selection=[
            ('20', "20'"),
            ('40', "40'"),
            ('45', "45'"),
        ],
        string="Size (Feet)",
        required=True,
        default='20',
    )
    container_type = fields.Selection(
        selection=[
            ('dry', 'Dry (Standard)'),
            ('hc', 'High Cube'),
            ('reefer', 'Refrigerated'),
            ('open_top', 'Open Top'),
            ('flat_rack', 'Flat Rack'),
            ('tank', 'Tank'),
        ],
        string="Type",
        default='dry',
        required=True,
    )
    max_weight_kg = fields.Float(
        string="Max Weight (Kg)",
        help="Maximum cargo weight in kilograms",
    )
    tare_weight_kg = fields.Float(
        string="Tare Weight (Kg)",
        help="Empty container weight in kilograms",
    )
    capacity_cbm = fields.Float(
        string="Capacity (CBM)",
        help="Internal capacity in cubic meters",
    )
    internal_length_m = fields.Float(
        string="Internal Length (m)",
    )
    internal_width_m = fields.Float(
        string="Internal Width (m)",
    )
    internal_height_m = fields.Float(
        string="Internal Height (m)",
    )
    notes = fields.Text(
        string="Notes",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    def name_get(self):
        result = []
        for container in self:
            name = container.name
            if container.code:
                name = "[%s] %s" % (container.code, name)
            result.append((container.id, name))
        return result
