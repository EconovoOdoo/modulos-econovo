# -*- coding: utf-8 -*-

from odoo import fields, models, api


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    location_dest_id = fields.Many2one(
        'stock.location', 
        string='Destination Location',
        domain="[('usage', '=', 'internal'), ('company_id', 'in', [company_id, False])]",
        check_company=True,
        help="Location where finished products from this work center should be stored. "
             "If not set, the default location from the operation type will be used."
    )

    @api.depends('location_dest_id')
    def _compute_has_custom_destination(self):
        """Compute if workcenter has a custom destination location"""
        for workcenter in self:
            workcenter.has_custom_destination = bool(workcenter.location_dest_id)

    has_custom_destination = fields.Boolean(
        string='Has Custom Destination',
        compute='_compute_has_custom_destination',
        store=True,
        help="Technical field indicating if this workcenter has a custom destination location"
    )

    @api.depends('order_ids.duration_expected', 'order_ids.workcenter_id', 'order_ids.state', 'order_ids.date_start')
    def _compute_workorder_count(self):
        """
        Override native _compute_workorder_count to fix KeyError with NewId records.
        
        ROOT CAUSE:
        Native Odoo method at addons/mrp/models/mrp_workcenter.py line 86-108 has a bug:
        - Line 88: result = {wid: {} for wid in self._ids}
        - During form view onchange, self._ids contains NewId objects (e.g., NewId origin='virtual_123')
        - Line 95-100: _read_group() queries database and returns REAL database IDs (e.g., 107)
        - Line 100: result[workcenter.id][state] = count
        - KeyError occurs because workcenter.id (107) is not in result dict (only NewId keys exist)
        
        SOLUTION:
        Filter out NewId records before processing. Only query database for records with real IDs.
        Handle NewId records separately by setting default zero values.
        
        This is the most robust solution as it:
        - Fixes the root cause directly
        - Handles all edge cases (new records, form edits, list edits)
        - Maintains full compatibility with Odoo's workorder count logic
        - Works regardless of how the method is triggered (onchange, compute, etc.)
        """
        from datetime import datetime
        
        # Filter out NewId records (records not yet saved to database)
        real_workcenters = self.filtered(lambda w: not isinstance(w.id, models.NewId))
        
        if not real_workcenters:
            # All records are NewIds (not saved yet), set default values
            for workcenter in self:
                workcenter.workorder_count = 0
                workcenter.workorder_pending_count = 0
                workcenter.workcenter_load = 0
                workcenter.workorder_ready_count = 0
                workcenter.workorder_progress_count = 0
                workcenter.workorder_late_count = 0
            return
        
        # Use real IDs only (not self._ids which can include NewIds)
        MrpWorkorder = self.env['mrp.workorder']
        result = {wid: {} for wid in real_workcenters.ids}  # FIX: Use real_workcenters.ids instead of self._ids
        result_duration_expected = {wid: 0 for wid in real_workcenters.ids}
        
        # Count Late Workorder
        data = MrpWorkorder._read_group(
            [('workcenter_id', 'in', real_workcenters.ids), ('state', 'in', ('pending', 'waiting', 'ready')), ('date_start', '<', datetime.now().strftime('%Y-%m-%d'))],
            ['workcenter_id'], ['__count'])
        count_data = {workcenter.id: count for workcenter, count in data}
        
        # Count All, Pending, Ready, Progress Workorder
        res = MrpWorkorder._read_group(
            [('workcenter_id', 'in', real_workcenters.ids)],
            ['workcenter_id', 'state'], ['duration_expected:sum', '__count'])
        for workcenter, state, duration_sum, count in res:
            result[workcenter.id][state] = count
            if state in ('pending', 'waiting', 'ready', 'progress'):
                result_duration_expected[workcenter.id] += duration_sum
        
        # Set computed values for real workcenters
        for workcenter in real_workcenters:
            workcenter.workorder_count = sum(count for state, count in result[workcenter.id].items() if state not in ('done', 'cancel'))
            workcenter.workorder_pending_count = result[workcenter.id].get('pending', 0)
            workcenter.workcenter_load = result_duration_expected[workcenter.id]
            workcenter.workorder_ready_count = result[workcenter.id].get('ready', 0)
            workcenter.workorder_progress_count = result[workcenter.id].get('progress', 0)
            workcenter.workorder_late_count = count_data.get(workcenter.id, 0)
        
        # Set default values for NewId records (if any remain in self)
        new_workcenters = self - real_workcenters
        for workcenter in new_workcenters:
            workcenter.workorder_count = 0
            workcenter.workorder_pending_count = 0
            workcenter.workcenter_load = 0
            workcenter.workorder_ready_count = 0
            workcenter.workorder_progress_count = 0
            workcenter.workorder_late_count = 0
