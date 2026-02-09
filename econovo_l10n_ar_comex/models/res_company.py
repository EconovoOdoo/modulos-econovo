# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


COMEX_SEQUENCE_DEFINITIONS = [
    {
        'name': '%s COMEX Import Operation',
        'code': 'comex.operation.import',
        'prefix': 'IMP/%(year)s/',
        'padding': 5,
    },
    {
        'name': '%s COMEX Export Operation',
        'code': 'comex.operation.export',
        'prefix': 'EXP/%(year)s/',
        'padding': 5,
    },
    {
        'name': '%s COMEX Shipment',
        'code': 'comex.shipment',
        'prefix': 'SHP/%(year)s/',
        'padding': 5,
    },
    {
        'name': '%s COMEX Customs Clearance',
        'code': 'comex.customs.clearance',
        'prefix': 'DSP/%(year)s/',
        'padding': 5,
    },
    {
        'name': '%s COMEX MULC Operation',
        'code': 'comex.mulc',
        'prefix': 'MULC/%(year)s/',
        'padding': 5,
    },
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    # -------------------------------------------------------------------------
    # PRIVATE METHODS
    # -------------------------------------------------------------------------
    def _create_comex_sequences(self):
        """Create COMEX sequences for the given companies.

        Each company gets its own set of sequences for import/export
        operations, shipments, customs clearances, and MULC operations.
        Skips creation if a sequence with the same code already exists
        for the company.
        """
        seq_vals = []
        for company in self:
            existing_codes = set(
                self.env['ir.sequence'].sudo().search([
                    ('company_id', '=', company.id),
                    ('code', 'in', [s['code'] for s in COMEX_SEQUENCE_DEFINITIONS]),
                ]).mapped('code')
            )
            for seq_def in COMEX_SEQUENCE_DEFINITIONS:
                if seq_def['code'] not in existing_codes:
                    seq_vals.append({
                        'name': seq_def['name'] % company.name,
                        'code': seq_def['code'],
                        'prefix': seq_def['prefix'],
                        'padding': seq_def['padding'],
                        'company_id': company.id,
                        'number_next': 1,
                        'number_increment': 1,
                    })
        if seq_vals:
            self.env['ir.sequence'].sudo().create(seq_vals)

    @api.model
    def create_missing_comex_sequences(self):
        """Hook called on module install to create COMEX sequences
        for all existing companies that don't have them yet.

        Also migrates any legacy sequences (company_id set to a specific
        company or without proper company assignment) by keeping them
        for company 1 and creating new ones for other companies.
        """
        companies = self.env['res.company'].sudo().search([])
        companies._create_comex_sequences()

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Override to create COMEX sequences for new companies."""
        companies = super().create(vals_list)
        companies.sudo()._create_comex_sequences()
        return companies
