# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def batch_production_assignment(self):
        """
        Apply batch material assignment to multiple selected production orders.
        
        This method implements the same functionality as the "Assignments" (smart button)
        but applied massively to multiple production orders.
        
        Returns:
            dict: Result of assignment action with success/error information
        """
        if not self:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Error'),
                'message': _('No production orders have been selected.'),
                'type': 'warning'
            }}
        
        # Categorize and process results with improved messaging
        results = {
            'fully_assigned': [],
            'partially_assigned': [],
            'already_assigned': [],
            'no_materials': [],
            'invalid_state': [],
            'errors': []
        }
        
        # Filter only the OPs that can be assigned
        assignable_productions = self.filtered(lambda p: p.state in ['confirmed', 'progress'])
        
        if not assignable_productions:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Warning'),
                'message': _('No production orders in valid state for material assignment (must be Confirmed or In Progress).'),
                'type': 'warning'
            }}
        
        for production in assignable_productions:
            try:
                # Check current state before assignment
                pre_assignment_category = self._categorize_production_detailed(production)
                
                if pre_assignment_category in ['already_assigned', 'no_materials', 'invalid_state']:
                    results[pre_assignment_category].append({
                        'production': production,
                        'message': self._get_category_message(pre_assignment_category, production)
                    })
                    continue
                
                # Attempt assignment
                result = production._execute_batch_assignment()
                if result['success']:
                    # Check post-assignment status to determine if fully or partially assigned
                    post_assignment_category = self._categorize_production_detailed(production)
                    
                    if post_assignment_category == 'already_assigned':
                        results['fully_assigned'].append({
                            'production': production,
                            'message': result['message']
                        })
                    else:
                        results['partially_assigned'].append({
                            'production': production,
                            'message': result['message']
                        })
                else:
                    results['errors'].append({
                        'production': production,
                        'message': result['message']
                    })
                    
            except Exception as e:
                results['errors'].append({
                    'production': production,
                    'message': str(e)
                })
        
        # Generate comprehensive result message
        return self._generate_result_notification(results)
    
    def _categorize_production_detailed(self, production):
        """
        Categorize a production order with detailed analysis.
        
        Returns:
            str: Category ('fully_assignable', 'partially_assignable', 'already_assigned', 
                          'no_materials', 'invalid_state')
        """
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
                return 'no_materials'
            
            # Analyze assignability
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
            _logger.warning(f"Error categorizing production {production.name}: {str(e)}")
            return 'no_materials'
    
    def _get_category_message(self, category, production):
        """Get descriptive message for each category."""
        messages = {
            'already_assigned': _('All materials already assigned'),
            'no_materials': _('No materials available for assignment'),
            'invalid_state': _('Invalid state for assignment (must be Confirmed or In Progress)'),
            'fully_assignable': _('All materials available and ready'),
            'partially_assignable': _('Some materials available')
        }
        return messages.get(category, _('Unknown status'))
    
    def _generate_result_notification(self, results):
        """Generate comprehensive result notification."""
        message_parts = []
        notification_type = 'success'
        
        # Count totals
        total_success = len(results['fully_assigned']) + len(results['partially_assigned'])
        total_processed = sum(len(category) for category in results.values())
          # Success messages
        if results['fully_assigned']:
            message_parts.append(f"[SUCCESS] {len(results['fully_assigned'])} order(s) completely assigned")
            
        if results['partially_assigned']:
            message_parts.append(f"[WARNING] {len(results['partially_assigned'])} order(s) partially assigned")
            notification_type = 'warning'
            
        # Skip messages
        if results['already_assigned']:
            message_parts.append(f"[INFO] {len(results['already_assigned'])} order(s) already had materials assigned")
            
        if results['no_materials']:
            message_parts.append(f"[ERROR] {len(results['no_materials'])} order(s) without available materials")
            if total_success == 0:
                notification_type = 'danger'
                
        if results['invalid_state']:
            message_parts.append(f"[BLOCKED] {len(results['invalid_state'])} order(s) in invalid state")
            
        if results['errors']:
            message_parts.append(f"[ERROR] {len(results['errors'])} order(s) with processing errors")
            if total_success == 0:
                notification_type = 'danger'
        
        # Add sample error details
        if results['errors']:
            message_parts.append("\nError details:")
            for item in results['errors'][:3]:  # Show first 3 errors
                message_parts.append(f"• {item['production'].name}: {item['message']}")
            if len(results['errors']) > 3:
                message_parts.append(f"• ... and {len(results['errors']) - 3} more errors")
          # Summary
        if total_success > 0:
            message_parts.insert(0, f"[SUMMARY] {total_success}/{total_processed} orders processed successfully")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Material Assignment Result'),
                'message': '\n'.join(message_parts),
                'type': notification_type,
                'sticky': True  # Keep notification visible
            }
        }

    def _execute_batch_assignment(self):
        """
        Execute assignment logic for an individual OP replicating
        exactly what the native "Assignments" button does.
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        self.ensure_one()
        
        try:
            # Debugging: Log the type and contents of move_finished_ids
            _logger.debug(f"move_finished_ids type: {type(self.move_finished_ids)}")
            _logger.debug(f"move_finished_ids contents: {self.move_finished_ids}")

            # Verify that there are valid finished product movements
            finished_moves = self.move_finished_ids.filtered(
                lambda m: m.product_id.type == 'product' and m.state != 'cancel'
            )
            
            if not finished_moves:
                return {'success': False, 'message': 'No finished products to assign'}
            
            # Use the same context as the native button
            context = dict(self.env.context, default_production_ids=self.ids)
            
            # Get the reception report with the correct context
            reception_report = self.env['report.stock.report_reception'].with_context(context)
            
            # Get the documents as the native report does (the context already contains the IDs)
            docs = reception_report._get_docs(self.ids)
            
            if not docs:
                return {'success': False, 'message': 'No valid documents found'}
            
            # Get report data same as native button
            report_values = reception_report._get_report_values(self.ids)
            
            if not report_values:
                return {'success': False, 'message': 'Could not get report data'}
            
            if report_values.get('pickings') is False:
                return {'success': False, 'message': report_values.get('reason', 'No report data available')}
            
            # Check if there are lines to assign
            sources_to_lines = report_values.get('sources_to_lines', {})
            
            if not sources_to_lines:
                return {'success': False, 'message': 'No lines available for assignment'}
            
            # Collect all assignments that can be made
            move_ids = []
            qtys = []
            in_ids = []
            
            # Process each source and its lines to make automatic assignments
            for source, lines in sources_to_lines.items():
                for line in lines:
                    # Only process lines that can be assigned and are not already assigned
                    if (line.get('is_qty_assignable', False) and 
                        not line.get('is_assigned', False) and 
                        line.get('move_ins') and 
                        line.get('move_out') and
                        line.get('quantity', 0) > 0):
                        
                        move_out = line.get('move_out')
                        quantity = line.get('quantity')
                        move_ins = line.get('move_ins')
                        
                        move_ids.append(move_out.id)
                        qtys.append(quantity)
                        in_ids.append(move_ins)
            
            if move_ids:
                try:
                    # Call the report's assignment method with all assignments
                    reception_report.action_assign(move_ids, qtys, in_ids)
                    return {'success': True, 'message': f'{len(move_ids)} assignment(s) completed'}
                except Exception as assign_error:
                    _logger.error(f"Error in action_assign: {str(assign_error)}")
                    return {'success': False, 'message': f'Assignment error: {str(assign_error)}'}
            else:
                return {'success': False, 'message': 'No materials found to assign'}
                
        except Exception as e:
            _logger.error(f"Error in production assignment {self.name}: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    @api.model
    def batch_assign_selected_productions(self, production_ids):
        """
        Server action method to be called from list view.
        
        Args:
            production_ids (list): List of production order IDs to assign
            
        Returns:
            dict: Action result with notification message
        """
        if not production_ids:
            raise UserError(_("No production orders have been selected for batch assignment."))
        
        productions = self.browse(production_ids)
        return productions.batch_production_assignment()

    @api.model
    def batch_unassign_selected_productions(self, production_ids):
        """
        Server action method to be called from list view for unassignment.
        
        Args:
            production_ids (list): List of production order IDs to unassign
            
        Returns:
            dict: Action result to open the wizard
        """
        if not production_ids:
            raise UserError(_("No production orders have been selected for batch unassignment."))
        
        # Open the unified wizard in unassignment mode
        return {
            'type': 'ir.actions.act_window',
            'name': _('Batch Material Unassignment'),
            'res_model': 'mrp.production.batch.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': production_ids,
                'active_model': 'mrp.production',
                'default_operation_mode': 'unassign'
            }
        }

    def batch_production_unassignment(self):
        """
        Apply batch material unassignment to multiple selected production orders.
        
        This method implements the opposite functionality to batch assignment,
        using the native do_unreserve() method to release reserved materials.
        
        Returns:
            dict: Result of unassignment action with success/error information
        """
        if not self:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Error'),
                'message': _('No production orders have been selected.'),
                'type': 'warning'
            }}
        
        # Categorize and process results for unassignment
        results = {
            'fully_unassigned': [],
            'partially_unassigned': [],
            'already_unassigned': [],
            'no_reservations': [],
            'invalid_state': [],
            'errors': []
        }
        
        # Filter only the OPs that can be unassigned
        unassignable_productions = self.filtered(lambda p: p.state in ['confirmed', 'progress'])
        
        if not unassignable_productions:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
                'title': _('Warning'),
                'message': _('No production orders in valid state for material unassignment (must be Confirmed or In Progress).'),
                'type': 'warning'
            }}

        for production in unassignable_productions:
            try:
                # Attempt unassignment directly - let action_unassign handle its own validation
                result = production._execute_batch_unassignment()
                if result['success']:
                    results['fully_unassigned'].append({
                        'production': production,
                        'message': result['message']
                    })
                else:
                    results['errors'].append({
                        'production': production,
                        'message': result['message']
                    })
                    
            except Exception as e:
                _logger.error(f"Error processing production {production.name}: {str(e)}")
                results['errors'].append({
                    'production': production,
                    'message': f'Unexpected error: {str(e)}'
                })
        
        return self._generate_unassignment_result_notification(results)

    def _categorize_production_for_unassignment(self, production):
        """
        Categorize a production order based on its unassignment status using 
        reception report data for consistency with the native reception report logic.
        This uses the same criteria as action_view_reception_report to determine
        what materials can be unassigned.
        """
        
        # Check if production is in valid state
        if production.state not in ['confirmed', 'progress']:
            return 'invalid_state'
        
        try:
            # Use reception report for detailed analysis (same as action_view_reception_report)
            context = dict(self.env.context, default_production_ids=production.ids)
            reception_report = self.env['report.stock.report_reception'].with_context(context)
            
            # Get report values using the same method as the reception report
            report_values = reception_report._get_report_values(production.ids)
            
            if not report_values or report_values.get('pickings') is False:
                # If report can't be generated, fallback to direct move analysis
                reserved_moves = production.move_raw_ids.filtered(
                    lambda m: m.state in ['assigned', 'partially_available'] and m.reserved_availability > 0
                )
                return 'no_reservations' if not reserved_moves else 'partially_unassignable'

            sources_to_lines = report_values.get('sources_to_lines', {})

            if not sources_to_lines:
                # No lines available, check moves directly as fallback
                reserved_moves = production.move_raw_ids.filtered(
                    lambda m: m.state in ['assigned', 'partially_available'] and m.reserved_availability > 0
                )
                return 'no_reservations' if not reserved_moves else 'partially_unassignable'

            # Analyze assignment status from reception report lines
            total_lines = 0
            assigned_lines = 0
            assignable_lines = 0

            for source, lines in sources_to_lines.items():
                for line in lines:
                    total_lines += 1

                    # Key logic: Use same criteria as reception report
                    if line.get('is_assigned', False):
                        assigned_lines += 1
                    elif line.get('is_qty_assignable', True):
                        assignable_lines += 1

            if total_lines == 0:
                reserved_moves = production.move_raw_ids.filtered(
                    lambda m: m.state in ['assigned', 'partially_available'] and m.reserved_availability > 0
                )
                return 'no_reservations' if not reserved_moves else 'partially_unassignable'
            elif assigned_lines == 0:
                return 'no_reservations'
            elif assigned_lines == total_lines:
                return 'fully_unassignable'
            else:
                return 'partially_unassignable'
                
        except Exception as e:
            _logger.warning("Error categorizing production for unassignment %s: %s" % (production.name, str(e)))
            # Fallback to direct move analysis in case of error
            try:
                reserved_moves = production.move_raw_ids.filtered(
                    lambda m: m.state in ['assigned', 'partially_available'] and m.reserved_availability > 0
                )
                return 'no_reservations' if not reserved_moves else 'fully_unassignable'
            except:
                return 'no_reservations'
    
    def _get_unassignment_category_message(self, category, production):
        """Get descriptive message for each unassignment category."""
        messages = {
            'no_reservations': _('No materials reserved for unassignment'),
            'invalid_state': _('Invalid state for unassignment (must be Confirmed or In Progress)'),
            'fully_unassignable': _('All materials reserved and ready to unreserve'),
            'partially_unassignable': _('Some materials reserved')
        }
        return messages.get(category, _('Unknown status'))
    
    def _validate_unassignment_conditions(self):
        """
        Validate conditions for unassignment operation.
        
        Returns:
            tuple: (is_valid: bool, error_message: str)
        """
        self.ensure_one()
        
        # Check if production is in valid state
        if self.state not in ['confirmed', 'progress']:
            return False, _('Production order must be in Confirmed or In Progress state for unassignment')
          # Check if there are moves to unreserve
        if not self.move_raw_ids:
            return False, _('No raw material moves found for unassignment')
        
        return True, ''

    def _execute_batch_unassignment(self):
        """
        Execute unassignment using the reception report's action_unassign method.
        This method bypasses all validations to force unassignment.

        Returns:
            dict: {'success': bool, 'message': str}
        """
        self.ensure_one()

        try:
            # Use the same context approach as assignment
            context = dict(self.env.context, default_production_ids=self.ids)
            reception_report = self.env['report.stock.report_reception'].with_context(context)

            # Get report values to retrieve assignment data
            report_values = reception_report._get_report_values(self.ids)

            # Process unassignment using action_unassign
            unassignments_made = 0

            for source, lines in report_values.get('sources_to_lines', {}).items():
                for line in lines:
                    move_out = line.get('move_out')
                    quantity = line.get('quantity', 0)
                    move_ins = line.get('move_ins', [])

                    if move_out and quantity > 0 and move_ins:
                        try:
                            reception_report.action_unassign(move_out.id, quantity, move_ins)
                            unassignments_made += 1
                        except Exception as line_error:
                            _logger.warning(f"Failed to unassign line: {str(line_error)}")
                            continue

            return {'success': True, 'message': f'{unassignments_made} material(s) unassigned successfully'}

        except Exception as e:
            _logger.error(f"Error in production unassignment {self.name}: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    def _generate_unassignment_result_notification(self, results):
        """Generate comprehensive result notification for unassignment operations."""
        message_parts = []
        notification_type = 'success'
        
        # Count totals
        total_success = len(results['fully_unassigned']) + len(results['partially_unassigned'])
        total_processed = sum(len(category) for category in results.values())
          # Success messages
        if results['fully_unassigned']:
            message_parts.append(f"[SUCCESS] {len(results['fully_unassigned'])} order(s) completely unassigned")
            
        if results['partially_unassigned']:
            message_parts.append(f"[WARNING] {len(results['partially_unassigned'])} order(s) partially unassigned")
            notification_type = 'warning'
            
        # Skip messages
        if results['no_reservations']:
            message_parts.append(f"[INFO] {len(results['no_reservations'])} order(s) had no materials to unassign")
            
        if results['invalid_state']:
            message_parts.append(f"[BLOCKED] {len(results['invalid_state'])} order(s) in invalid state")
            
        if results['errors']:
            message_parts.append(f"[ERROR] {len(results['errors'])} order(s) with processing errors")
            if total_success == 0:
                notification_type = 'danger'
        
        # Add sample error details
        if results['errors']:
            message_parts.append("\nError details:")
            for error in results['errors'][:3]:  # Show max 3 error examples
                message_parts.append(f"• {error['production'].name}: {error['message']}")
            if len(results['errors']) > 3:
                message_parts.append(f"... and {len(results['errors']) - 3} more errors")
        
        # Generate title
        if total_success > 0:
            if notification_type == 'warning':
                title = _('Batch Material Unassignment - Partial Success')
            else:
                title = _('Batch Material Unassignment - Success')
        else:
            title = _('Batch Material Unassignment - No Changes')
            notification_type = 'warning'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': '\n'.join(message_parts),
                'type': notification_type,
                'sticky': True if total_processed > 5 else False
            }
        }

