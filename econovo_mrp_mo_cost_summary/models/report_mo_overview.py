# -*- coding: utf-8 -*-

from odoo import _, api, models


class ReportMoOverview(models.AbstractModel):
    _inherit = 'report.mrp.report_mo_overview'

    @api.model
    def _get_categ_ancestors(self, categ):
        """Return list of ancestor dicts [{id, name}] from root to leaf.

        Identical to the helper in econovo_mrp_bom_cost_summary so the
        frontend can reconstruct the same category tree shape.
        """
        path_ids = [int(x) for x in categ.parent_path.strip('/').split('/') if x]
        ancestors = self.env['product.category'].browse(path_ids)
        return [{'id': c.id, 'name': c.name} for c in ancestors]

    def _get_components_data(self, production, replenish_data=False, level=0, current_index=False):
        """Inject categ_id, categ_name and categ_ancestors at the wrapper level.

        We add these fields on the wrapper dict (alongside 'summary' and
        'replenishments') rather than inside 'summary', because MoOverviewLine
        performs strict prop-shape validation on 'summary' and would reject
        unknown keys.
        """
        components = super()._get_components_data(
            production, replenish_data=replenish_data, level=level,
            current_index=current_index,
        )
        # Pre-build product_id → categ lookup from all raw moves.
        # Multiple lines with the same product always share the same categ,
        # so a dict is safe and avoids repeated record-set traversal.
        categ_by_product = {
            move.product_id.id: move.product_id.categ_id
            for move in production.move_raw_ids
        }
        for comp_wrapper in components:
            prod_id = comp_wrapper.get('summary', {}).get('product_id')
            categ = categ_by_product.get(prod_id)
            if not categ:
                comp_wrapper['categ_id'] = 0
                comp_wrapper['categ_name'] = _("Uncategorized")
                comp_wrapper['categ_ancestors'] = []
                continue
            comp_wrapper['categ_id'] = categ.id
            comp_wrapper['categ_name'] = categ.name or _("Uncategorized")
            comp_wrapper['categ_ancestors'] = self._get_categ_ancestors(categ)
        return components

    def _get_byproducts_data(self, production, current_mo_cost, current_real_cost,
                             level=0, current_index=False):
        """Inject a categ_map sibling on the byproducts dict.

        Category info is stored in byproducts['categ_map'] keyed by product_id
        instead of directly on each detail dict.  The detail dicts are passed
        as-is to MoOverviewLine which has a strict OWL prop shape; any unknown
        key there raises an OwlError.
        """
        remaining, byproducts = super()._get_byproducts_data(
            production, current_mo_cost, current_real_cost,
            level=level, current_index=current_index,
        )
        categ_by_product = {
            move.product_id.id: move.product_id.categ_id
            for move in production.move_byproduct_ids
        }
        categ_map = {}
        for product_id, categ in categ_by_product.items():
            if not categ:
                categ_map[product_id] = {
                    'categ_id': 0,
                    'categ_name': _("Uncategorized"),
                    'categ_ancestors': [],
                }
            else:
                categ_map[product_id] = {
                    'categ_id': categ.id,
                    'categ_name': categ.name or _("Uncategorized"),
                    'categ_ancestors': self._get_categ_ancestors(categ),
                }
        byproducts['categ_map'] = categ_map
        return remaining, byproducts

    def _get_operations_data(self, production, level=0, current_index=False):
        result = super()._get_operations_data(
            production, level=level, current_index=current_index
        )
        # Build a workcenter lookup keyed by workorder ID and store it as a
        # sibling of 'details' on the result dict.  This lets our JS utility
        # group sub-MO operations by work center without injecting extra keys
        # into each detail item — which would break MoOverviewLine's strict
        # OWL prop-shape validation.
        result['workcenter_map'] = {
            wo.id: {
                'workcenter_id': wo.workcenter_id.id,
                'workcenter_name': wo.workcenter_id.display_name,
            }
            for wo in production.workorder_ids
        }
        return result

    def _get_replenishment_lines(self, production, move_raw, replenish_data, level, current_index):
        """Move workcenter_map out of rep['operations'] into rep['operations_workcenter_map'].

        _get_operations_data adds 'workcenter_map' to the operations result so our
        JS can group sub-MO operations by work center.  However, the native
        MoOverviewComponentsBlock receives rep['operations'] as an OWL prop and
        rejects any key that is not in its declared shape.  We therefore pop
        'workcenter_map' here and re-attach it as a sibling key on the
        replenishment dict itself, where OWL never looks.

        Additionally, for sub-MO replenishments we inject subcontractor_id and
        subcontractor_name so the JS layer can build the Subcontracting section
        without an extra round-trip to the server.
        """
        replenishments = super()._get_replenishment_lines(
            production, move_raw, replenish_data, level, current_index
        )
        # Collect all sub-MO IDs in one pass so we can batch-browse them.
        sub_mo_ids = [
            rep['summary']['id']
            for rep in replenishments
            if rep.get('summary', {}).get('model') == 'mrp.production'
            and rep.get('summary', {}).get('id')
        ]
        sub_mo_by_id = {}
        if sub_mo_ids:
            for mo in self.env['mrp.production'].browse(sub_mo_ids):
                sub_mo_by_id[mo.id] = mo

        for rep in replenishments:
            # Move workcenter_map to a sibling key (existing behaviour).
            ops = rep.get('operations')
            if ops and 'workcenter_map' in ops:
                rep['operations_workcenter_map'] = ops.pop('workcenter_map')

            # Inject subcontractor info for sub-MOs.
            summary = rep.get('summary', {})
            if summary.get('model') == 'mrp.production' and summary.get('id'):
                mo = sub_mo_by_id.get(summary['id'])
                if mo and mo.subcontractor_id:
                    summary['subcontractor_id'] = mo.subcontractor_id.id
                    summary['subcontractor_name'] = mo.subcontractor_id.display_name
        return replenishments

    def _get_report_data(self, production_id):
        """Inject 'operations_workcenter_info' as a top-level sibling of 'operations'.

        MoOverviewComponentsBlock validates the 'operations' prop with a strict
        shape {summary, details} — any extra key inside it triggers an OwlError.
        'workcenter_map' added by _get_operations_data must be removed from the
        top-level operations dict here; for sub-MO replenishments it is already
        moved to 'operations_workcenter_map' by _get_replenishment_lines above.
        The top-level workcenter info is instead provided via the separate
        'operations_workcenter_info' list (used by our JS utility by index).
        """
        result = super()._get_report_data(production_id)
        # Remove workcenter_map injected by _get_operations_data so it does not
        # reach MoOverviewComponentsBlock as an invalid prop key.
        result.get('operations', {}).pop('workcenter_map', None)
        # Remove categ_map injected by _get_byproducts_data — same reason.
        # Promote it to a top-level sibling 'byproducts_categ_map' so that
        # the byproducts dict keeps shape {summary, details} only.
        bp_categ_map = (result.get('byproducts') or {}).pop('categ_map', {})
        result['byproducts_categ_map'] = bp_categ_map
        production = self.env['mrp.production'].browse(production_id)
        result['operations_workcenter_info'] = [
            {
                'workcenter_id': wo.workcenter_id.id,
                'workcenter_name': wo.workcenter_id.display_name,
            }
            for wo in production.workorder_ids
        ]
        return result
