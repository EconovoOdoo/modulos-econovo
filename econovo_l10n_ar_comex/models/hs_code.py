# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HsCode(models.Model):
    _name = 'hs.code'
    _description = 'HS Code (NCM)'
    _order = 'local_code'
    _rec_names_search = ['local_code', 'description']

    local_code = fields.Char(
        string="NCM Code",
        required=True,
        size=14,
        help="Nomenclatura Común del Mercosur (8-14 digits)",
    )
    hs_code = fields.Char(
        string="HS Code",
        size=6,
        compute='_compute_hs_code',
        store=True,
        help="Harmonized System code (first 6 digits)",
    )
    description = fields.Text(
        string="Description",
        required=True,
        translate=True,
    )
    chapter = fields.Char(
        string="Chapter",
        compute='_compute_hierarchy',
        store=True,
    )
    heading = fields.Char(
        string="Heading",
        compute='_compute_hierarchy',
        store=True,
    )
    subheading = fields.Char(
        string="Subheading",
        compute='_compute_hierarchy',
        store=True,
    )
    
    # === DUTIES AND TAXES ===
    import_duty_rate = fields.Float(
        string="Import Duty Rate (%)",
        help="Derecho de Importación Extrazona (DIE)",
    )
    export_duty_rate = fields.Float(
        string="Export Duty Rate (%)",
        help="Derecho de Exportación (Retención)",
    )
    statistics_rate = fields.Float(
        string="Statistics Rate (%)",
        default=3.0,
        help="Tasa de Estadística (normally 3%)",
    )
    vat_rate = fields.Float(
        string="VAT Rate (%)",
        default=21.0,
    )
    vat_additional_rate = fields.Float(
        string="Additional VAT Rate (%)",
        default=21.0,
        help="IVA Adicional for resellers (21%) or consumers (10.5%)",
    )
    income_tax_rate = fields.Float(
        string="Income Tax Perception (%)",
        default=6.0,
        help="Percepción de Ganancias",
    )
    
    # === REQUIREMENTS ===
    requires_license = fields.Boolean(
        string="Requires Import License",
    )
    requires_certificate = fields.Boolean(
        string="Requires Certificate",
    )
    certificate_type = fields.Char(
        string="Certificate Type",
        help="SENASA, ANMAT, INTI, etc.",
    )
    
    # === MULC ===
    mulc_days = fields.Integer(
        string="MULC Access Days",
        help="Days after shipment to access foreign exchange market",
    )
    
    notes = fields.Text(
        string="Notes",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )
    
    product_ids = fields.One2many(
        'product.template',
        'hs_code_id',
        string="Products",
    )
    product_count = fields.Integer(
        string="Product Count",
        compute='_compute_product_count',
    )

    _sql_constraints = [
        ('local_code_uniq', 'unique(local_code)', 'The NCM code must be unique!'),
    ]

    @api.depends('local_code')
    def _compute_hs_code(self):
        for record in self:
            if record.local_code and len(record.local_code) >= 6:
                record.hs_code = record.local_code[:6]
            else:
                record.hs_code = False

    @api.depends('local_code')
    def _compute_hierarchy(self):
        for record in self:
            code = record.local_code or ''
            record.chapter = code[:2] if len(code) >= 2 else False
            record.heading = code[:4] if len(code) >= 4 else False
            record.subheading = code[:6] if len(code) >= 6 else False

    @api.depends('product_ids')
    def _compute_product_count(self):
        for record in self:
            record.product_count = len(record.product_ids)

    @api.constrains('local_code')
    def _check_local_code(self):
        for record in self:
            if record.local_code and not record.local_code.isdigit():
                raise ValidationError(_("NCM code must contain only digits."))
            if record.local_code and len(record.local_code) < 8:
                raise ValidationError(_("NCM code must have at least 8 digits."))

    def name_get(self):
        result = []
        for record in self:
            name = record.local_code
            if record.description:
                desc = record.description[:50]
                if len(record.description) > 50:
                    desc += '...'
                name = "%s - %s" % (record.local_code, desc)
            result.append((record.id, name))
        return result


class ProductTemplateHsCode(models.Model):
    _inherit = 'product.template'

    hs_code_id = fields.Many2one(
        'hs.code',
        string="NCM Code",
        help="Nomenclatura Común del Mercosur",
    )
    origin_country_id = fields.Many2one(
        'res.country',
        string="Country of Origin",
        help="Country of origin for customs purposes",
    )
