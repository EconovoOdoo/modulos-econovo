# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MrpProductionSchedule(models.Model):
    _inherit = 'mrp.production.schedule'

    cascade_bom_explode = fields.Boolean(
        string="Include multi-level cascade products",
        default=False,
        help="When enabled, all BoM component levels (children, grandchildren, "
             "etc.) will be added to the MPS, not only the first level.",
    )

    def _collect_all_bom_components(self, product, company, visited=None):
        """Recursively collect all product IDs from all BoM levels.

        Traverses the BoM tree depth-first, collecting every component
        product that has a manufacturing BoM. Phantom/kit BoMs are
        traversed but their products are not added as MPS entries
        (their leaf components are added instead).

        :param product: product.product record to explore
        :param company: res.company record for BoM lookup
        :param visited: set of already visited product IDs (cycle detection)
        :return: set of product.product IDs found at all levels
        """
        if visited is None:
            visited = set()
        if product.id in visited:
            return set()
        visited.add(product.id)

        result = set()
        bom = self.env['mrp.bom']._bom_find(
            product, company_id=company.id,
        ).get(product, self.env['mrp.bom'])

        if not bom:
            return result

        for line in bom.bom_line_ids:
            if line._skip_bom_line(product):
                continue
            if line.product_id.type == 'consu':
                continue
            result.add(line.product_id.id)
            # Recurse into sub-components
            result |= self._collect_all_bom_components(
                line.product_id, company, visited,
            )
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Override to support multi-level BoM cascade when creating MPS entries.

        When cascade_bom_explode is True in any vals dict, the system
        collects ALL BoM component levels recursively before creating
        component MPS entries (instead of only the first level).
        """
        # Extract cascade flags before super() processes vals_list,
        # since the field is not stored and super's logic uses bom.explode()
        # which only handles phantom BoMs (first level for manufacturing).
        cascade_requests = {}
        for i, vals in enumerate(vals_list):
            if vals.pop('cascade_bom_explode', False):
                cascade_requests[i] = True

        if not cascade_requests:
            return super().create(vals_list)

        # For cascade requests, we need to handle component creation ourselves
        # instead of letting super() do it with bom.explode().
        # Strategy: let super() create the parent entries normally,
        # then replace its first-level component creation with our recursive one.

        # Temporarily remove bom_id from cascade entries so super() doesn't
        # create first-level components for them. We will handle it after.
        saved_bom_ids = {}
        saved_product_ids = {}
        saved_warehouse_ids = {}
        saved_company_ids = {}
        for i in cascade_requests:
            if i < len(vals_list) and vals_list[i].get('bom_id'):
                saved_bom_ids[i] = vals_list[i]['bom_id']
                saved_product_ids[i] = vals_list[i].get('product_id')
                saved_warehouse_ids[i] = vals_list[i].get(
                    'warehouse_id', self._default_warehouse_id().id,
                )
                saved_company_ids[i] = vals_list[i].get(
                    'company_id', self.env.company.id,
                )
                # Remove bom_id so super()'s create() won't do first-level explode
                del vals_list[i]['bom_id']

        # Call super() — creates parent MPS entries without component explosion
        mps = super().create(vals_list)

        # Now restore bom_id on the created records and do recursive explosion
        for i, bom_id in saved_bom_ids.items():
            if i < len(mps):
                record = mps[i]
                record.bom_id = bom_id

                bom = self.env['mrp.bom'].browse(bom_id)
                product = record.product_id
                company = record.company_id
                warehouse_id = record.warehouse_id.id

                # Collect ALL levels recursively
                all_component_ids = self._collect_all_bom_components(
                    product, company,
                )

                # Create MPS entries for components that don't already exist
                components_vals = []
                for comp_product_id in all_component_ids:
                    existing = self.search([
                        ('product_id', '=', comp_product_id),
                        ('warehouse_id', '=', warehouse_id),
                        ('company_id', '=', company.id),
                    ], limit=1)
                    if existing:
                        continue
                    components_vals.append({
                        'product_id': comp_product_id,
                        'warehouse_id': warehouse_id,
                        'company_id': company.id,
                    })

                if components_vals:
                    self.env['mrp.production.schedule'].create(components_vals)

        return mps
