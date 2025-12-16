
import logging

from odoo import _, models, api
from odoo.exceptions import CacheMiss
_logger = logging.getLogger(__name__)

class BomStructureXlsx(models.AbstractModel):
    _inherit = 'report.mrp_bom_structure_xlsx.bom_structure_xlsx'

    def print_bom_children(self, ch, sheet, row, level):
        i, j = row, level
        j += 1
        sheet.write(i, 1, "> " * j)
        sheet.write(i, 2, ch.product_id.default_code or "")
        sheet.write(i, 3, ch.product_id.display_name or "")
        sheet.write(
            i,
            4,
            ch.product_uom_id._compute_quantity(ch.product_qty, ch.product_id.uom_id)
            or "",
        )
        sheet.write(i, 5, ch.product_id.uom_id.name or "")
        sheet.write(i, 6, ch.bom_id.code or "")
        sheet.write(i, 7, ch.product_id.standard_price_usd or "")
        sheet.write(i, 8, ch.product_id.standard_price or "")
        i += 1
        # self.env.cache.invalidate()
        try:
            for child in ch.child_line_ids:
                i = self.print_bom_children(child, sheet, i, j)
        except CacheMiss as e:
            # The Bom has no childs, thus it is the last level.
            # When a BoM has no childs, chlid_line_ids is None, this creates a
            # CacheMiss Error. However, this is expected because there really
            # cannot be child_line_ids.
            _logger.warning(e)

        j -= 1
        return i

    def generate_xlsx_report(self, workbook, data, objects):
        workbook.set_properties(
            {"comments": "Created with Python and XlsxWriter from Odoo 11.0"}
        )
        sheet = workbook.add_worksheet(_("BOM Structure"))
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.set_zoom(80)
        sheet.set_column(0, 0, 40)
        sheet.set_column(1, 2, 20)
        sheet.set_column(3, 3, 40)
        sheet.set_column(4, 8, 20)
        bold = workbook.add_format({"bold": True})
        title_style = workbook.add_format(
            {"bold": True, "bg_color": "#FFFFCC", "bottom": 1}
        )
        sheet_title = [
            _("BOM Name"),
            _("Level"),
            _("Product Reference"),
            _("Product Name"),
            _("Quantity"),
            _("Unit of Measure"),
            _("Reference"),
            _("Precio Unitario en USD"),
            _("Precio Unitario")
        ]
        sheet.set_row(0, None, None, {"collapsed": 1})
        sheet.write_row(1, 0, sheet_title, title_style)
        sheet.freeze_panes(2, 0)
        i = 2
        for o in objects:
            sheet.write(i, 0, o.product_tmpl_id.name or "", bold)
            sheet.write(i, 1, "", bold)
            sheet.write(i, 2, o.product_id.default_code or "", bold)
            sheet.write(i, 3, o.product_id.name or "", bold)
            sheet.write(i, 4, o.product_qty, bold)
            sheet.write(i, 5, o.product_uom_id.name or "", bold)
            sheet.write(i, 6, o.code or "", bold)
            sheet.write(i, 7, o.product_id.standard_price_usd or "", bold)
            sheet.write(i, 8, o.product_id.standard_price or "", bold)
            i += 1
            j = 0
            for ch in o.bom_line_ids:
                i = self.print_bom_children(ch, sheet, i, j)


class ReportBomStructure(models.AbstractModel):
    _inherit = 'report.mrp.report_bom_structure'

    @api.model
    def _get_component_data(self, parent_bom, parent_product, warehouse, bom_line, line_quantity, level, index,
                            product_info, ignore_stock=False):
        ret = super()._get_component_data(parent_bom, parent_product, warehouse, bom_line, line_quantity, level, index,
                                        product_info, ignore_stock=ignore_stock)
        ret['standard_price_usd'] = bom_line.product_id.standard_price_usd
        return ret

    @api.model
    def _get_byproducts_lines(self, product, bom, bom_quantity, level, total, index):
        byproducts, byproduct_cost_portion = super()._get_byproducts_lines(product, bom, bom_quantity, level, total, index)
        for i in range(len(byproducts)):
            byproducts[i]['standard_price_usd'] = byproducts[i]['product_id'].standard_price_usd
        return byproducts, byproduct_cost_portion

    @api.model
    def _get_bom_data(self, bom, warehouse, product=False, line_qty=False, bom_line=False, level=0, parent_bom=False, parent_product=False, index=0, product_info=False, ignore_stock=False):
        ret = super()._get_bom_data(bom, warehouse, product=product, line_qty=line_qty, bom_line=bom_line, level=level, parent_bom=parent_bom, parent_product=parent_product, index=index, product_info=product_info, ignore_stock=ignore_stock)
        ret['standard_price_usd'] = bom.product_id.standard_price_usd or bom.product_tmpl_id.standard_price_usd
        return ret