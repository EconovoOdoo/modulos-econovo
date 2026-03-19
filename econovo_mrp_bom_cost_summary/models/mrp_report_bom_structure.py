from odoo import _, api, fields, models


class ReportBomStructure(models.AbstractModel):
    """Extend BOM structure report to include data needed by the cost summary.

    Adds:
    - secondary_currency (USD) conversion rate to ``_get_report_data``
    - product category id/name and ancestor chain to component and BOM data
    - workcenter id/name to each operation line
    """

    _inherit = 'report.mrp.report_bom_structure'

    @api.model
    def _get_categ_ancestors(self, categ):
        """Return list of ancestor dicts [{id, name}] from root to leaf."""
        path_ids = [
            int(x) for x in categ.parent_path.strip('/').split('/')
            if x
        ]
        ancestors = self.env['product.category'].browse(path_ids)
        return [{'id': c.id, 'name': c.name} for c in ancestors]

    @api.model
    def _get_report_data(self, bom_id, searchQty=0, searchVariant=False):
        """Extend report data with secondary currency (USD) information."""
        res = super()._get_report_data(
            bom_id, searchQty=searchQty, searchVariant=searchVariant,
        )
        company = (
            self.env['mrp.bom'].browse(bom_id).company_id or self.env.company
        )
        company_currency = company.currency_id
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        secondary_currency = False
        if usd and usd.active and usd.id != company_currency.id:
            rate = company_currency._get_conversion_rate(
                company_currency, usd, company,
                fields.Date.context_today(self),
            )
            secondary_currency = {
                'id': usd.id,
                'name': usd.name,
                'symbol': usd.symbol,
                'rate': rate,
            }
        res['secondary_currency'] = secondary_currency
        return res

    @api.model
    def _get_bom_data(
        self, bom, warehouse, product=False, line_qty=False,
        bom_line=False, level=0, parent_bom=False, parent_product=False,
        index=0, product_info=False, ignore_stock=False,
    ):
        """Add product category info to BOM node data for cost grouping."""
        res = super()._get_bom_data(
            bom, warehouse, product=product, line_qty=line_qty,
            bom_line=bom_line, level=level, parent_bom=parent_bom,
            parent_product=parent_product, index=index,
            product_info=product_info, ignore_stock=ignore_stock,
        )
        prod = (
            product
            or bom.product_id
            or bom.product_tmpl_id.product_variant_id
        )
        if prod:
            res['categ_id'] = prod.categ_id.id
            res['categ_name'] = prod.categ_id.name or _("Uncategorized")
            res['categ_ancestors'] = self._get_categ_ancestors(
                prod.categ_id,
            )
        return res

    @api.model
    def _get_component_data(
        self, parent_bom, parent_product, warehouse, bom_line,
        line_quantity, level, index, product_info, ignore_stock=False,
    ):
        """Add product category info to component data for cost grouping."""
        res = super()._get_component_data(
            parent_bom, parent_product, warehouse, bom_line,
            line_quantity, level, index, product_info,
            ignore_stock=ignore_stock,
        )
        res['categ_id'] = bom_line.product_id.categ_id.id
        res['categ_name'] = (
            bom_line.product_id.categ_id.name or _("Uncategorized")
        )
        res['categ_ancestors'] = self._get_categ_ancestors(
            bom_line.product_id.categ_id,
        )
        res['operation_id'] = (
            bom_line.operation_id.id if bom_line.operation_id else False
        )
        return res

    @api.model
    def _get_operation_line(self, product, bom, qty, level, index):
        """Add workcenter ID/name and clean operation name for grouping."""
        operations = super()._get_operation_line(
            product, bom, qty, level, index,
        )
        bom_operations = bom.operation_ids.filtered(
            lambda o: not product or not o._skip_operation_line(product)
        )
        for i, op in enumerate(operations):
            if i < len(bom_operations):
                op['workcenter_id'] = bom_operations[i].workcenter_id.id
                op['workcenter_name'] = bom_operations[i].workcenter_id.name
                op['operation_name'] = bom_operations[i].name
        return operations

    @api.model
    def _get_byproducts_lines(self, product, bom, bom_quantity, level, total, index):
        """Add product category info to byproduct lines for cost grouping."""
        byproducts, byproduct_cost_portion = super()._get_byproducts_lines(
            product, bom, bom_quantity, level, total, index,
        )
        for bp in byproducts:
            categ = (
                self.env['mrp.bom.byproduct'].browse(bp['id']).product_id.categ_id
            )
            bp['categ_id'] = categ.id
            bp['categ_name'] = categ.name or _("Uncategorized")
            bp['categ_ancestors'] = self._get_categ_ancestors(categ)
        return byproducts, byproduct_cost_portion
