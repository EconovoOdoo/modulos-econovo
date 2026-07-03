# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################
import io
import zipfile
import base64
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BatchPdfGenerationWizard(models.TransientModel):
    """Wizard to generate PDF attendance sheets in batches.
    
    This solves memory issues when generating PDFs for large numbers of employees
    by splitting them into smaller batches (default: 25 employees per PDF).
    """
    _name = 'batch.pdf.generation.wizard'
    _description = 'Batch PDF Generation Wizard'

    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Month', default=lambda self: str(datetime.now().month), required=True)

    year = fields.Integer(string='Year', default=lambda self: datetime.now().year, required=True)

    employee_ids = fields.Many2many(
        'hr.employee', string='Employees',
        help='Leave empty to include all employees'
    )

    batch_size = fields.Integer(
        string='Employees per Batch',
        default=25,
        help='Number of employees per PDF file. Smaller = less memory usage.'
    )

    sheet_type = fields.Selection([
        ('combined', 'Combined Sheet'),
        ('individual', 'Individual Sheets'),
    ], string='Sheet Type', default='combined', required=True)

    # Progress tracking
    state = fields.Selection([
        ('draft', 'Ready'),
        ('generating', 'Generating...'),
        ('done', 'Completed'),
        ('error', 'Failed'),
    ], string='State', default='draft')

    progress_percent = fields.Float(string='Progress (%)', default=0.0)
    current_batch = fields.Integer(string='Current Batch', default=0)
    total_batches = fields.Integer(string='Total Batches', default=0)
    log_messages = fields.Text(string='Generation Log', readonly=True)

    # Output files
    zip_file = fields.Binary(string='ZIP File', readonly=True)
    zip_filename = fields.Char(string='ZIP Filename', readonly=True)
    file_count = fields.Integer(string='Files Generated', readonly=True)

    def action_start_generation(self):
        """Start batch PDF generation."""
        self.ensure_one()
        
        # Get employees
        employees = self.employee_ids or self.env['hr.employee'].search([])
        if not employees:
            raise UserError(_('No employees found. Please select employees or ensure employees exist.'))
        
        # Calculate batches
        batch_size = max(1, min(self.batch_size, 50))  # Limit to 1-50
        total_batches = (len(employees) + batch_size - 1) // batch_size
        
        self.write({
            'state': 'generating',
            'total_batches': total_batches,
            'current_batch': 0,
            'progress_percent': 0,
            'log_messages': f'Starting batch PDF generation...\n'
                          f'Total employees: {len(employees)}\n'
                          f'Batch size: {batch_size}\n'
                          f'Total batches: {total_batches}\n\n',
        })
        
        try:
            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            files_generated = 0
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Process employees in batches
                for batch_num in range(total_batches):
                    start_idx = batch_num * batch_size
                    end_idx = min(start_idx + batch_size, len(employees))
                    batch_employees = employees[start_idx:end_idx]
                    
                    self._log(f'Batch {batch_num + 1}/{total_batches}: Processing {len(batch_employees)} employees...')
                    self.write({
                        'current_batch': batch_num + 1,
                        'progress_percent': ((batch_num + 1) / total_batches) * 90,  # 90% for generation
                    })
                    
                    # Create a temporary wizard for this batch
                    batch_wizard = self.env['employee.attendance.sheet.wizard'].create({
                        'month': self.month,
                        'year': self.year,
                        'employee_ids': [(6, 0, batch_employees.ids)],
                        'report_format': 'pdf',
                        'sheet_type': self.sheet_type,
                    })
                    
                    # Generate PDF for this batch
                    try:
                        pdf_data = batch_wizard._generate_pdf_report()
                        
                        # Add to ZIP
                        filename = f'attendance_sheet_batch_{batch_num + 1:03d}.pdf'
                        zip_file.writestr(filename, pdf_data)
                        files_generated += 1
                        
                        self._log(f'✓ Generated: {filename}')
                        
                    except Exception as e:
                        self._log(f'✗ Error in batch {batch_num + 1}: {str(e)}')
                        # Continue with next batch instead of failing completely
            
            # Save ZIP file
            zip_buffer.seek(0)
            zip_data = zip_buffer.getvalue()
            
            month_name = dict(self._fields['month'].selection).get(self.month, self.month)
            filename = f'attendance_sheets_{month_name}_{self.year}_batches.zip'
            
            self.write({
                'state': 'done',
                'progress_percent': 100,
                'zip_file': base64.b64encode(zip_data),
                'zip_filename': filename,
                'file_count': files_generated,
            })
            
            self._log(f'\n{"="*50}')
            self._log(f'Generation Complete!')
            self._log(f'Files generated: {files_generated}')
            self._log(f'ZIP file: {filename}')
            self._log(f'{"="*50}')
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'batch.pdf.generation.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': self.env.context,
            }
            
        except Exception as e:
            self._log(f'\n✗ ERROR: {str(e)}')
            self.write({
                'state': 'error',
                'progress_percent': 0,
            })
            raise UserError(_('Error during PDF generation: %s') % str(e))

    def _log(self, message):
        """Append message to log."""
        self.ensure_one()
        current_logs = self.log_messages or ''
        new_log = current_logs + message + '\n'
        self.write({'log_messages': new_log})

    def action_close(self):
        """Close wizard."""
        return {'type': 'ir.actions.act_window_close'}
