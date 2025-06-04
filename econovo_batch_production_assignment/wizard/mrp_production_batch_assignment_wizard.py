# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MrpProductionBatchAssignmentWizard(models.TransientModel):
    _name = 'mrp.production.batch.assignment.wizard'
    _description = 'Manufacturing Order Batch Assignment Wizard'

    # Mode toggle
    operation_mode = fields.Selection([
        ('assign', 'Assignment'),
        ('unassign', 'Unassignment')
    ], string='Operation Mode', default='assign', required=True)

    # Fields for the summary
    production_ids = fields.Many2many('mrp.production', string='Manufacturing Orders')

    # Summary counters
    fully_assignable_count = fields.Integer(string='Fully Assignable', readonly=True)
    partially_assignable_count = fields.Integer(string='Partially Assignable', readonly=True)
    already_assigned_count = fields.Integer(string='Already Assigned', readonly=True)
    no_materials_count = fields.Integer(string='No Materials to Assign', readonly=True)
    invalid_state_count = fields.Integer(string='Invalid State', readonly=True)

    # Detail information
    summary_text = fields.Html(string='Assignment Summary', readonly=True)

    @api.model
    def default_get(self, fields_list):
        """Override to populate wizard with selected production orders."""
        res = super().default_get(fields_list)

        # Get production IDs from context
        production_ids = self.env.context.get('active_ids', [])

        if not production_ids:
            raise UserError("No manufacturing orders selected.")

        res['production_ids'] = [(6, 0, production_ids)]

        # Analyze and categorize the selected productions based on default operation mode
        self = self.with_context(lang='en_US')
        self._analyze_productions(res, production_ids, res.get('operation_mode', 'assign'))

        return res

    @api.onchange('operation_mode')
    def _onchange_operation_mode(self):
        """Re-analyze productions when operation mode changes."""
        if self.production_ids:
            production_ids = self.production_ids.ids
            self._reanalyze_productions(production_ids)

    def _reanalyze_productions(self, production_ids):
        """Re-analyze productions for the current operation mode."""
        # Create a temporary dict to hold results
        res = {}
        self._analyze_productions(res, production_ids, self.operation_mode)        # Update current record with new values
        self.fully_assignable_count = res.get('fully_assignable_count', 0)
        self.partially_assignable_count = res.get('partially_assignable_count', 0)
        self.already_assigned_count = res.get('already_assigned_count', 0)
        self.no_materials_count = res.get('no_materials_count', 0)
        self.invalid_state_count = res.get('invalid_state_count', 0)
        self.summary_text = res.get('summary_text', '')

    def _analyze_productions(self, res, production_ids, operation_mode='assign'):
        """Analyze selected productions and categorize them based on operation mode."""
        productions = self.env['mrp.production'].browse(production_ids)

        # Initialize counters
        fully_assignable = []
        partially_assignable = []
        already_assigned = []
        no_materials = []
        invalid_state = []

        for production in productions:
            if operation_mode == 'assign':
                category = self._categorize_production_for_assignment(production)
            else:  # unassign
                category = self._categorize_production_for_unassignment(production)
                # Map unassignment categories to display categories
                if category == 'fully_unassignable':
                    category = 'fully_assignable'  # Use same display field
                elif category == 'partially_unassignable':
                    category = 'partially_assignable'  # Use same display field
                elif category == 'no_reservations':
                    category = 'no_materials'  # Use same display field

            if category == 'fully_assignable':
                fully_assignable.append(production)
            elif category == 'partially_assignable':
                partially_assignable.append(production)
            elif category == 'already_assigned':
                already_assigned.append(production)
            elif category == 'no_materials':
                no_materials.append(production)
            else:  # invalid_state
                invalid_state.append(production)

        # Update counters
        res['fully_assignable_count'] = len(fully_assignable)
        res['partially_assignable_count'] = len(partially_assignable)
        res['already_assigned_count'] = len(already_assigned)
        res['no_materials_count'] = len(no_materials)
        res['invalid_state_count'] = len(invalid_state)

        # Generate summary HTML
        res['summary_text'] = self._generate_summary_html(
            fully_assignable, partially_assignable, already_assigned,
            no_materials, invalid_state, operation_mode
        )

    def _categorize_production_for_assignment(self, production):
        """Categorize a production order based on its assignment status."""

        # Check if production is in valid state
        if production.state not in ['confirmed', 'progress']:
            return 'invalid_state'

        # Check if show_allocation is available
        if not production.show_allocation:
            return 'already_assigned'

        try:
            # Get detailed assignment information using reception report
            context = dict(self.env.context, default_production_ids=production.ids)
            reception_report = self.env['report.stock.report_reception'].with_context(context)

            # Get report values
            report_values = reception_report._get_report_values(production.ids)

            if not report_values or report_values.get('pickings') is False:
                return 'no_materials'

            sources_to_lines = report_values.get('sources_to_lines', {})

            if not sources_to_lines:
                return 'no_materials'            # Analyze assignability
            total_lines = 0
            assignable_lines = 0
            assigned_lines = 0

            for source, lines in sources_to_lines.items():
                for line in lines:
                    total_lines += 1

                    if line.get('is_assigned', False):
                        assigned_lines += 1
                    elif line.get('is_qty_assignable', False):
                        assignable_lines += 1

            if total_lines == 0:
                return 'no_materials'
            elif assigned_lines == total_lines:
                return 'already_assigned'
            elif assignable_lines == total_lines:
                return 'fully_assignable'
            elif assignable_lines > 0:
                return 'partially_assignable'
            else:
                return 'no_materials'
                
        except Exception as e:
            _logger.warning(_("Error categorizing production %s: %s") % (production.name, str(e)))
            return 'no_materials'

    def _categorize_production_for_unassignment(self, production):
        """Categorize a production order for unassignment using proper logic."""
          # Use the model's robust categorization method that uses reception report logic
        return production._categorize_production_for_unassignment(production)

    def _generate_summary_html(self, fully_assignable, partially_assignable,
                              already_assigned, no_materials, invalid_state, operation_mode='assign'):
        """Generate HTML summary of the assignment analysis using native Bootstrap alert classes."""
        html_parts = ['<div class="container-fluid">']

        if operation_mode == 'assign':
            # Assignment mode messages with Bootstrap alert classes
            if fully_assignable:
                html_parts.append(
                    '<div class="alert alert-success" role="alert">'
                    '<h5 class="alert-heading">'
                    '<i class="fa fa-check-circle"></i> %s (%s)'
                    '</h5>'
                    '<p class="mb-1">%s</p>'
                    '<ul class="mb-0">%s</ul>'
                    '%s'
                    '</div>' % (
                        _("Fully Assignable"), len(fully_assignable),
                        _("These orders have all materials available and ready to assign."),
                        self._format_production_list(fully_assignable[:5]),
                        self._show_more_indicator(fully_assignable, 5)
                    )
                )

            if partially_assignable:
                html_parts.append(
                    '<div class="alert alert-warning" role="alert">'
                    '<h5 class="alert-heading">'
                    '<i class="fa fa-exclamation-triangle"></i> %s (%s)'
                    '</h5>'
                    '<p class="mb-1">%s</p>'
                    '<ul class="mb-0">%s</ul>'
                    '%s'
                    '</div>' % (
                        _("Partially Assignable"), len(partially_assignable),
                        _("These orders have some materials available but not all."),
                        self._format_production_list(partially_assignable[:5]),
                        self._show_more_indicator(partially_assignable, 5)                    )
                )

            if already_assigned:
                html_parts.append(
                    '<div class="alert alert-info" role="alert">'
                    '<h5 class="alert-heading">'
                    '<i class="fa fa-info-circle"></i> %s (%s)'
                    '</h5>'
                    '<p class="mb-1">%s</p>'
                    '<ul class="mb-0">%s</ul>'
                    '%s'
                    '</div>' % (
                        _("Already Assigned"), len(already_assigned),
                        _("These orders already have materials assigned."),
                        self._format_production_list(already_assigned[:5]),
                        self._show_more_indicator(already_assigned, 5)
                    )
                )

            if no_materials:
                html_parts.append(
                    '<div class="alert alert-danger" role="alert">'
                    '<h5 class="alert-heading">'
                    '<i class="fa fa-times-circle"></i> %s (%s)'
                    '</h5>'
                    '<p class="mb-1">%s</p>'
                    '<ul class="mb-0">%s</ul>'
                    '%s'
                    '</div>' % (
                        _("No Materials to Assign"), len(no_materials),
                        _("These orders have no materials available for assignment."),
                        self._format_production_list(no_materials[:5]),
                        self._show_more_indicator(no_materials, 5)                    )
                )
        else:
            # Unassignment mode messages with Bootstrap alert classes
            if fully_assignable:
                html_parts.append(
                    '<div class="alert alert-success" role="alert">'
                    '<h5 class="alert-heading">'
                    '<i class="fa fa-check-circle"></i> %s (%s)'
                    '</h5>'
                    '<p class="mb-1">%s</p>'
                    '<ul class="mb-0">%s</ul>'
                    '%s'
                    '</div>' % (
                        _("Fully Unreservable"), len(fully_assignable),
                        _("These orders have all materials reserved and ready to unreserve."),
                        self._format_production_list(fully_assignable[:5]),
                        self._show_more_indicator(fully_assignable, 5)
                    )
                )

            if partially_assignable:
                html_parts.append(
                    '<div class="alert alert-warning" role="alert">'
                    '<h5 class="alert-heading">'
                    '<i class="fa fa-exclamation-triangle"></i> %s (%s)'
                    '</h5>'
                    '<p class="mb-1">%s</p>'
                    '<ul class="mb-0">%s</ul>'
                    '%s'
                    '</div>' % (
                        _("Partially Unreservable"), len(partially_assignable),
                        _("These orders have some materials reserved but not all."),
                        self._format_production_list(partially_assignable[:5]),
                        self._show_more_indicator(partially_assignable, 5)                    )
                )

            if no_materials:
                html_parts.append(
                    '<div class="alert alert-danger" role="alert">'
                    '<h5 class="alert-heading">'
                    '<i class="fa fa-times-circle"></i> %s (%s)'
                    '</h5>'
                    '<p class="mb-1">%s</p>'
                    '<ul class="mb-0">%s</ul>'
                    '%s'
                    '</div>' % (
                        _("No Materials to Unreserve"), len(no_materials),
                        _("These orders have no materials reserved for unreservation."),
                        self._format_production_list(no_materials[:5]),
                        self._show_more_indicator(no_materials, 5)                    )
                )

        if invalid_state:
            html_parts.append(
                '<div class="alert alert-secondary" role="alert">'
                '<h5 class="alert-heading">'
                '<i class="fa fa-ban"></i> %s (%s)'
                '</h5>'
                '<p class="mb-1">%s</p>'
                '<ul class="mb-0">%s</ul>'
                '%s'
                '</div>' % (
                    _("Invalid State"), len(invalid_state),
                    _("These orders are not in a valid state for processing (must be Confirmed or In Progress)."),
                    self._format_production_list(invalid_state[:5]),
                    self._show_more_indicator(invalid_state, 5)
                )
            )

        html_parts.append('</div>')

        return ''.join(html_parts)

    def _format_production_list(self, productions):
        """Format a list of productions as HTML list items."""
        items = []
        for prod in productions:
            items.append('<li><strong>%s</strong> - %s</li>' % (prod.name, prod.product_id.name))
        return ''.join(items)

    def _show_more_indicator(self, production_list, limit):
        """Show 'and X more' indicator if list is longer than limit."""
        if len(production_list) > limit:
            return '<p style="margin: 5px 0; color: #666; font-style: italic;">%s</p>' % (
                _("... and %s more") % (len(production_list) - limit)
            )
        return ''

    def action_confirm_assignment(self):
        """Execute the batch assignment or unassignment after confirmation."""
        if not self.production_ids:
            raise UserError(_("No manufacturing orders to process."))

        if self.operation_mode == 'assign':
            return self._execute_batch_assignment()
        else:
            return self._execute_batch_unassignment()

    def _execute_batch_assignment(self):
        """Execute batch assignment."""
        # Filter only orders that can be processed for assignment
        processable_productions = self.production_ids.filtered(
            lambda p: p.state in ['confirmed', 'progress'] and p.show_allocation
        )

        if not processable_productions:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Orders to Process'),
                    'message': _('No manufacturing orders can be processed for assignment.'),
                    'type': 'warning'                }
            }

        # Execute the batch assignment
        result = processable_productions.batch_production_assignment()

        # Close the wizard and show the result
        return result

    def _execute_batch_unassignment(self):
        """Execute batch unassignment."""
        # Filter orders using proper categorization logic instead of just checking move_line_ids
        processable_productions = []
        
        for production in self.production_ids:
            if production.state in ['confirmed', 'progress']:
                category = production._categorize_production_for_unassignment(production)
                if category in ['fully_unassignable', 'partially_unassignable']:
                    processable_productions.append(production)
        
        processable_productions = self.env['mrp.production'].browse([p.id for p in processable_productions])

        if not processable_productions:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Orders to Process'),
                    'message': _('No manufacturing orders have material reservations that can be unassigned.'),
                    'type': 'warning'
                }
            }

        # Execute the batch unassignment using the model method for better tracking
        results = {
            'success': [],
            'failed': [],
            'no_reservations': []
        }

        for production in processable_productions:
            try:
                # Use the model method that provides detailed feedback
                result = production._execute_batch_unassignment()
                if result.get('success', False):
                    results['success'].append({
                        'production': production,
                        'message': result.get('message', '')
                    })
                else:
                    message = result.get('message', '').lower()
                    if 'no reserved materials' in message or 'no material reservations' in message:
                        results['no_reservations'].append(production)
                    else:
                        results['failed'].append({
                            'production': production,
                            'message': result.get('message', '')
                        })
            except Exception as e:
                _logger.error("Error in batch unassignment for %s: %s" % (production.name, str(e)))
                results['failed'].append({
                    'production': production,
                    'message': str(e)
                })

        # Generate comprehensive notification
        return self._generate_unassignment_notification(results)

    def _generate_unassignment_notification(self, results):
        """Generate comprehensive notification for unassignment results."""
        message_parts = []
        notification_type = 'success'

        # Success messages
        if results['success']:
            total_materials = sum(int(item['message'].split()[0]) if item['message'].split()[0].isdigit() else 1
                                for item in results['success'])
            message_parts.append("[SUCCESS] Successfully unassigned materials from %d order(s) (%d material(s) total)" %
                               (len(results['success']), total_materials))

        # Warnings
        if results['no_reservations']:
            message_parts.append("[INFO] %d order(s) had no material reservations to unassign" % len(results['no_reservations']))
            if not results['success']:
                notification_type = 'warning'

        # Errors
        if results['failed']:
            message_parts.append("[WARNING] %d order(s) failed to unassign: %s" %
                               (len(results['failed']),
                                ', '.join([item['production'].name + ' (' + item['message'] + ')'
                                         for item in results['failed'][:3]])))
            if len(results['failed']) > 3:
                message_parts.append("... and %d more" % (len(results['failed']) - 3))

            if not results['success']:
                notification_type = 'danger'

        # Default message if nothing processed
        if not any([results['success'], results['failed'], results['no_reservations']]):
            message_parts.append("No orders were processed")
            notification_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Unassignment Results'),
                'message': '<br/>'.join(message_parts),
                'type': notification_type,
                'sticky': len(message_parts) > 1
            }
        }

    def action_cancel(self):
        """Cancel the wizard without performing assignment."""
        return {'type': 'ir.actions.act_window_close'}
