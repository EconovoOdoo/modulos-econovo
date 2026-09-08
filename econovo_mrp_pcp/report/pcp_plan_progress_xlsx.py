# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PcpPlanProgressXlsx(models.AbstractModel):
    _name = 'report.econovo_mrp_pcp.report_plan_progress'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'PCP Plan Progress XLSX Report'

    def generate_xlsx_report(self, workbook, data, plans):
        sheet = workbook.add_worksheet('Production Progress')
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#1E293B', 'font_color': 'white', 'border': 1,
        })
        columns = [
            ('Priority', 16), ('Plan', 40), ('Process', 22), ('Product', 35),
            ('Qty Produced', 14), ('Qty Planned', 14), ('% Progress', 12), ('State', 15),
        ]
        for col_index, (label, width) in enumerate(columns):
            sheet.write(0, col_index, label, header_format)
            sheet.set_column(col_index, col_index, width)

        row_index = 1
        for plan in plans:
            workorders = plan.manufacture_order_ids.workorder_ids
            for workorder in workorders:
                progress = 0.0
                if workorder.qty_production:
                    progress = round(workorder.qty_produced / workorder.qty_production * 100, 1)
                sheet.write(row_index, 0, plan.priority_id.name or '')
                sheet.write(row_index, 1, plan.name)
                sheet.write(row_index, 2, workorder.name)
                sheet.write(row_index, 3, workorder.product_id.display_name)
                sheet.write(row_index, 4, workorder.qty_produced)
                sheet.write(row_index, 5, workorder.qty_production)
                sheet.write(row_index, 6, progress)
                sheet.write(row_index, 7, workorder.state)
                row_index += 1
