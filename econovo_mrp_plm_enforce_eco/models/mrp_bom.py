# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    mo_count = fields.Integer(
        string='# Manufacturing Orders',
        compute='_compute_mo_count',
        search='_search_mo_count',
        help='Number of Manufacturing Orders that reference this Bill of Materials.',
    )

    def _compute_mo_count(self):
        if not self.ids:
            for bom in self:
                bom.mo_count = 0
            return
        rows = self.env['mrp.production'].sudo()._read_group(
            domain=[('bom_id', 'in', self.ids)],
            groupby=['bom_id'],
            aggregates=['__count'],
        )
        counts = {bom.id: count for bom, count in rows}
        for bom in self:
            bom.mo_count = counts.get(bom.id, 0)

    @api.model
    def _search_mo_count(self, operator, value):
        # Only the operators needed by the record rule are implemented.
        # Anything else degrades to a no-match domain so callers cannot abuse it.
        if operator not in ('=', '!=') or value != 0:
            return [('id', 'in', [])]
        rows = self.env['mrp.production'].sudo()._read_group(
            domain=[('bom_id', '!=', False)],
            groupby=['bom_id'],
        )
        used_ids = [row[0].id for row in rows]
        if operator == '=':
            return [('id', 'not in', used_ids)]
        return [('id', 'in', used_ids)]

    def apply_new_version(self):
        # The PLM apply flow needs to set active=False on the previous BoM and
        # active=True on the revision. Controlled editors have no direct write
        # access to active BoMs; running this method as sudo lets the validated
        # PLM flow complete after the user has already passed all approvals.
        return super(MrpBom, self.sudo()).apply_new_version()

    def action_create_eco(self):
        # Mass-action helper exposed in the BoM list view: open a draft ECO
        # of type "bom" for each selected production-ready Bill of Materials.
        EcoType = self.env['mrp.eco.type']
        EcoStage = self.env['mrp.eco.stage']
        Eco = self.env['mrp.eco']

        eco_type = EcoType.search([], limit=1)
        if not eco_type:
            return False
        eco_stage = EcoStage.search(
            [('type_ids', 'in', eco_type.ids)], order='sequence', limit=1)

        created = Eco
        for bom in self.filtered(lambda b: b.active):
            created |= Eco.create({
                'name': _('Cambios en %s') % bom.display_name,
                'type_id': eco_type.id,
                'stage_id': eco_stage.id,
                'type': 'bom',
                'product_tmpl_id': bom.product_tmpl_id.id,
                'bom_id': bom.id,
            })

        if not created:
            return False
        if len(created) == 1:
            return {
                'name': _('Engineering Change Order'),
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.eco',
                'view_mode': 'form',
                'res_id': created.id,
            }
        return {
            'name': _('Engineering Change Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.eco',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created.ids)],
        }
