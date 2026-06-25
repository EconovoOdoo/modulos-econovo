# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    # Fields whose modification requires an ECO when the BoM is in production.
    # Listed as a class attribute so inheriting modules can extend the set:
    #   class MrpBom(models.Model):
    #       _inherit = 'mrp.bom'
    #       _BOM_LOCKED_FIELDS = MrpBom._BOM_LOCKED_FIELDS | {'extra_field'}
    _BOM_LOCKED_FIELDS = frozenset({
        # Group A — structural header fields
        'type', 'product_tmpl_id', 'product_id',
        'product_qty', 'product_uom_id', 'picking_type_id',
        'consumption', 'ready_to_produce', 'company_id', 'code',
        # Group B — One2many structural fields
        # (each item added/updated/deleted changes the BoM structure)
        'bom_line_ids', 'operation_ids', 'byproduct_ids',
    })

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

    # ------------------------------------------------------------------
    # Computed field for view readonly expressions
    # ------------------------------------------------------------------

    bom_locked_for_editor = fields.Boolean(
        string='BoM Locked for Current User',
        compute='_compute_bom_locked_for_editor',
        help='True when the current user must use an ECO to modify this BoM.',
    )

    def _compute_bom_locked_for_editor(self):
        # Managers are never locked out; the flag is only True for controlled editors.
        is_manager = self.env.user.has_group('mrp.group_mrp_manager')
        for bom in self:
            bom.bom_locked_for_editor = not is_manager and bom._is_bom_locked()

    # ------------------------------------------------------------------
    # Lock logic
    # ------------------------------------------------------------------

    def _is_bom_locked(self):
        """Returns True when this BoM requires an ECO for structural modifications.

        A BoM is considered locked when it is active (production-ready) and
        has been referenced by at least one Manufacturing Order.  Revision BoMs
        (active=False) are never locked — they are the intended edit target.
        """
        self.ensure_one()
        return self.active and self.mo_count > 0

    # ------------------------------------------------------------------
    # Write protection for header and One2many fields
    # ------------------------------------------------------------------

    def write(self, vals):
        if not self.env.su and not self.env.user.has_group('mrp.group_mrp_manager'):
            changed = self._BOM_LOCKED_FIELDS & vals.keys()
            if changed:
                locked = self.filtered(lambda b: b._is_bom_locked())
                if locked:
                    raise UserError(_(
                        'The following fields can only be modified through an '
                        'Engineering Change Order (ECO):\n%(fields)s\n\n'
                        'Affected Bills of Materials:\n%(boms)s',
                        fields=', '.join(sorted(changed)),
                        boms='\n'.join('- %s' % n for n in locked.mapped('display_name')),
                    ))
        return super().write(vals)

    # ------------------------------------------------------------------
    # PLM apply override
    # ------------------------------------------------------------------

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
