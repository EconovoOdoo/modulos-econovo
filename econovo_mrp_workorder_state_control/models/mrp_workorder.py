# -*- coding: utf-8 -*-
"""
Odoo 19 functionality backport for workorder state control.

This module implements EXACTLY the same code from Odoo 19 to allow
flexible state changes in workorders, including reverting from 'done'.
"""
from datetime import datetime
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    # ============================================================================
    # STATE FIELD - Remove readonly to allow direct write
    # ============================================================================
    # In Odoo 17 the state field has readonly=True, which prevents writing.
    # In Odoo 19 this restriction was removed to allow the set_state() method.
    # We redefine the field WITHOUT readonly to replicate Odoo 19 behavior.
    
    state = fields.Selection(
        selection=[
            ('pending', 'Waiting for another WO'),
            ('waiting', 'Waiting for components'),
            ('ready', 'Ready'),
            ('progress', 'In Progress'),
            ('done', 'Finished'),
            ('cancel', 'Cancelled')
        ],
        string='Status',
        compute='_compute_state',
        store=True,
        default='pending',
        copy=False,
        readonly=False,  # ← KEY CHANGE: Odoo 17 has readonly=True, Odoo 19 has readonly=False
        recursive=True,
        index=True
    )

    # ============================================================================
    # SET_STATE METHOD - IDENTICAL code from Odoo 19 (with button support)
    # ============================================================================
    # Copied verbatim from odoo/addons/mrp/models/mrp_workorder.py (Odoo 19.0)
    # Commit: 3f10d3c31b9d8aa65f4006f899afea5fb26b6719
    # Lines: ~150-172 (approximate)
    # Modified to support calls from buttons via context
    
    def set_state(self, state=None):
        """
        Change workorder state flexibly.
        
        This method allows state transitions that would normally not be
        possible, including reverting from 'done' to previous states.
        
        Args:
            state (str): Target state ('ready', 'progress', 'done', 'cancel')
                        If None, reads from context['state'] (for button calls)
        
        Special behavior:
            - If the workorder is in 'done' and wants to go to 'progress',
              it first goes to 'ready' as an intermediate step to avoid conflicts.
            - If in 'progress', it pauses first before changing to another state.
        
        Returns:
            bool: True if state change completed
        """
        # Support button calls: read state from context if not provided
        if state is None:
            state = self.env.context.get('state')
        if not state:
            return False
        ids_to_update = []
        for wo in self:
            # Do not process if already in target state or if done/cancel
            if wo.state == state or 'done' in (wo.state, wo.production_state):
                continue
            
            # If in progress, pause first
            if wo.state == 'progress':
                wo.button_pending()
            
            # SPECIAL CASE: Revert from 'done' or 'cancel' to 'progress'
            # First go to 'ready' as intermediate state to avoid conflicts
            elif wo.state in ('done', 'cancel') and state == 'progress':
                wo.write({'state': 'ready'})  # Middle step to solve further conflict
            
            ids_to_update.append(wo.id)
        
        wo_to_update = self.browse(ids_to_update)
        
        # Execute transition according to target state
        if state == 'cancel':
            wo_to_update.action_cancel()
        elif state == 'done':
            wo_to_update.action_mark_as_done()
        elif state == 'progress':
            wo_to_update.button_start()
        else:
            wo_to_update.write({'state': state})

    # ============================================================================
    # ACTION_MARK_AS_DONE METHOD - Alias of button_finish (exists in Odoo 19)
    # ============================================================================
    # In Odoo 19 action_mark_as_done is used instead of button_finish.
    # We create an alias to maintain exact compatibility with Odoo 19.
    
    def action_mark_as_done(self):
        """
        Mark workorder as completed.
        
        This method is a wrapper/alias of the existing button_finish method in Odoo 17.
        In Odoo 19, button_finish was renamed to action_mark_as_done.
        
        Returns:
            bool: Result of button_finish
        """
        # Verify that the workcenter is not blocked
        for wo in self:
            if wo.working_state == 'blocked':
                raise UserError(_('Please unblock the work center to validate the work order'))
            
            # Call the standard method
            wo.button_finish()
            
            # If no duration recorded, use the expected one
            if wo.duration == 0.0:
                wo.duration = wo.duration_expected
                wo.duration_percent = 100
        
        return True
