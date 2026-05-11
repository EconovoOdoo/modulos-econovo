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

    def _get_report_data(self, production_id):
        """Inject 'operations_workcenter_info' as a top-level sibling of 'operations'.

        MoOverviewComponentsBlock validates the 'operations' prop with a strict
        shape {summary, details} — any extra key inside it triggers an OwlError.
        Adding workcenter info here, at the root level of the report data dict,
        keeps the 'operations' structure untouched while still making the data
        available to our JS utility via state.data.operations_workcenter_info.
        """
        result = super()._get_report_data(production_id)
        production = self.env['mrp.production'].browse(production_id)
        result['operations_workcenter_info'] = [
            {
                'workcenter_id': wo.workcenter_id.id,
                'workcenter_name': wo.workcenter_id.display_name,
            }
            for wo in production.workorder_ids
        ]
        return result
