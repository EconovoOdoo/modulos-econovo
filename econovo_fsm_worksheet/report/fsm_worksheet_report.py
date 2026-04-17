# -*- coding: utf-8 -*-
from odoo import api, models


class FsmWorksheetSvt04Report(models.AbstractModel):
    """Report model for the REG-SVT-04 Orden de Trabajo PDF.

    Provides the worksheet record for each task so the QWeb template can render
    all x_* fields alongside the native task and timesheet data.
    """

    _name = 'report.econovo_fsm_worksheet.report_svt04'
    _description = 'FSM Worksheet SVT-04 Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        tasks = self.env['project.task'].browse(docids).sudo()
        worksheet_map = {}
        for task in tasks:
            if not (task.worksheet_template_id and task.worksheet_template_id.model_id):
                continue
            x_model = task.worksheet_template_id.model_id.model
            if x_model not in self.env:
                continue
            worksheet = self.env[x_model].search(
                [('x_project_task_id', '=', task.id)],
                limit=1,
                order='create_date DESC',
            )
            worksheet_map[task.id] = worksheet
        return {
            'doc_ids': docids,
            'doc_model': 'project.task',
            'docs': tasks,
            'worksheet_map': worksheet_map,
        }
