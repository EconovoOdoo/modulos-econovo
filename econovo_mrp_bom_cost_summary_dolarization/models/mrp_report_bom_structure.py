# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ReportBomStructure(models.AbstractModel):
    """Extend BOM structure report to include direct USD costs.

    When both ``econovo_mrp_bom_cost_summary`` and ``gg_cost_dolarization``
    are installed, each component in the BOM tree gets two additional keys:

    - ``bom_cost_usd_direct``:  BOM Cost scaled to ``standard_price_usd``
      using the local-price ratio (``bom_cost × usd_price / ars_price``).
      For components without a local price, falls back to
      ``line_quantity × standard_price_usd``.

    - ``prod_cost_usd_direct``:  ``line_quantity × standard_price_usd``
      (direct catalogue cost in USD, independent of the exchange rate).

    These values are then picked up by the JS side
    (``bom_cost_dolarization.js``) to populate the new columns.
    """

    _inherit = 'report.mrp.report_bom_structure'

    @api.model
    def _get_component_data(
        self, parent_bom, parent_product, warehouse, bom_line,
        line_quantity, level, index, product_info, ignore_stock=False,
    ):
        res = super()._get_component_data(
            parent_bom, parent_product, warehouse, bom_line,
            line_quantity, level, index, product_info,
            ignore_stock=ignore_stock,
        )

        product = bom_line.product_id
        std_usd = getattr(product, 'standard_price_usd', 0.0) or 0.0
        std_ars = product.standard_price or 0.0

        # Product Cost USD direct: same formula as prod_cost but using
        # standard_price_usd instead of standard_price.
        prod_cost_usd_direct = line_quantity * std_usd

        # BOM Cost USD direct: scale the existing bom_cost by the
        # usd/ars price ratio so that nested sub-assembly costs are
        # also approximated in USD.  Falls back to the product cost
        # direct when no local price is set.
        bom_cost = res.get('bom_cost') or 0.0
        if std_ars > 0:
            bom_cost_usd_direct = bom_cost * (std_usd / std_ars)
        else:
            bom_cost_usd_direct = prod_cost_usd_direct

        res['prod_cost_usd_direct'] = prod_cost_usd_direct
        res['bom_cost_usd_direct'] = bom_cost_usd_direct
        return res

    @api.model
    def _get_byproducts_lines(self, product, bom, bom_quantity, level, total, index):
        """Add direct-USD cost fields to byproduct lines.

        Extends the base override from ``econovo_mrp_bom_cost_summary``
        (which adds category info) by computing:

        - ``prod_cost_usd_direct``: quantity × product.standard_price_usd
        - ``bom_cost_usd_direct``:  bom_cost × (usd_price / ars_price),
          falling back to prod_cost_usd_direct when no ARS price is set.
        """
        byproducts, byproduct_cost_portion = super()._get_byproducts_lines(
            product, bom, bom_quantity, level, total, index,
        )
        for bp in byproducts:
            byproduct_obj = self.env['mrp.bom.byproduct'].browse(bp['id'])
            prod = byproduct_obj.product_id
            std_usd = getattr(prod, 'standard_price_usd', 0.0) or 0.0
            std_ars = prod.standard_price or 0.0

            quantity = bp.get('quantity', 0.0) or 0.0
            prod_cost_usd_direct = quantity * std_usd

            bom_cost = bp.get('bom_cost', 0.0) or 0.0
            if std_ars > 0:
                bom_cost_usd_direct = bom_cost * (std_usd / std_ars)
            else:
                bom_cost_usd_direct = prod_cost_usd_direct

            bp['prod_cost_usd_direct'] = prod_cost_usd_direct
            bp['bom_cost_usd_direct'] = bom_cost_usd_direct
        return byproducts, byproduct_cost_portion

    @api.model
    def _get_operation_line(self, product, bom, qty, level, index):
        """Inject ``bom_cost_usd_direct`` into every operation line.

        Mirrors the full ARS formula from ``_get_operation_cost``
        (base + mrp_workorder enterprise override):

            bom_cost_usd_direct =
                (duration / 60) × costs_hour_usd
              + (duration / 60) × employee_costs_hour_usd × employee_ratio

        ``costs_hour_usd`` and ``employee_costs_hour_usd`` are the
        direct-USD fields added to ``mrp.workcenter`` by this bridge module.
        ``employee_ratio`` is defined by ``mrp_workorder`` (enterprise);
        getattr guards are used so the formula degrades gracefully when
        mrp_workorder is not installed.
        """
        operations = super()._get_operation_line(product, bom, qty, level, index)
        bom_ops = bom.operation_ids.filtered(
            lambda o: not product or not o._skip_operation_line(product)
        )
        for i, op_data in enumerate(operations):
            if i < len(bom_ops):
                op = bom_ops[i]
                wc = op.workcenter_id
                duration = op_data.get('quantity', 0.0) or 0.0  # minutes
                costs_hour_usd = getattr(wc, 'costs_hour_usd', 0.0) or 0.0
                employee_costs_hour_usd = (
                    getattr(wc, 'employee_costs_hour_usd', 0.0) or 0.0
                )
                employee_ratio = getattr(op, 'employee_ratio', 0.0) or 0.0
                hours = duration / 60.0
                op_data['bom_cost_usd_direct'] = (
                    hours * costs_hour_usd
                    + hours * employee_costs_hour_usd * employee_ratio
                )
            else:
                op_data['bom_cost_usd_direct'] = 0.0
        return operations

    @api.model
    def _get_subcontracting_line(self, bom, seller, level, bom_quantity):
        """Inject ``bom_cost_usd_direct`` / ``prod_cost_usd_direct`` into the
        subcontracting node.

        The direct USD cost is always derived from the vendor's actual price
        converted to USD using Odoo's standard currency conversion.  When the
        vendor already prices in USD the conversion is 1:1 (no rounding loss).
        When the vendor prices in ARS or any other currency the exchange rate
        is applied, which is the most honest representation of what the
        subcontracted item costs in USD.
        """
        res = super()._get_subcontracting_line(bom, seller, level, bom_quantity)
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        if not usd_currency:
            res['bom_cost_usd_direct'] = 0.0
            res['prod_cost_usd_direct'] = 0.0
            return res
        ratio_uom_seller = seller.product_uom.ratio / bom.product_uom_id.ratio
        price_in_seller_currency = seller.price / ratio_uom_seller * bom_quantity
        company = bom.company_id or self.env.company
        bom_cost_usd_direct = seller.currency_id._convert(
            price_in_seller_currency,
            usd_currency,
            company,
            fields.Date.today(),
        )
        res['bom_cost_usd_direct'] = bom_cost_usd_direct
        res['prod_cost_usd_direct'] = bom_cost_usd_direct
        return res

