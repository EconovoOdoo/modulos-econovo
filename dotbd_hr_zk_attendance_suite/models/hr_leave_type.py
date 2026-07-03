# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited
#    Author: Rafiur Rahman Rafit
#
################################################################################

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrLeaveType(models.Model):
    """Extension of hr.leave.type to add short code for attendance reports"""
    _inherit = 'hr.leave.type'

    leave_short_code = fields.Char(
        string='Leave Code',
        size=5,
        help='Short code to display in attendance reports (e.g., SL, PL, CL). '
             'Maximum 5 characters. Will be shown in attendance sheets to distinguish different leave types.',
    )

    leave_attendance_category = fields.Selection([
        ('absence', 'Absence (Counts as Absence)'),
        ('worked', 'Worked (Counts as Worked Time)'),
    ], string='Attendance Category', default='absence',
        help='Determines how this leave type is counted in attendance reports:\n'
             '- Absence: Counts as absence (e.g., Sick Leave)\n'
             '- Worked: Counts as worked time (e.g., Training Leave)',
    )

    is_mandatory = fields.Boolean(
        string='Is Mandatory Day',
        default=False,
        help='If checked, this leave type is treated as a mandatory day (like public holiday). '
             'Shows as "M" in attendance reports and does not count as absent.'
    )

    @api.constrains('leave_short_code')
    def _check_leave_short_code(self):
        """Validate short code format and uniqueness"""
        for record in self:
            if record.leave_short_code:
                code = record.leave_short_code

                # Check length
                if len(code) > 5:
                    raise ValidationError('Leave code must be maximum 5 characters.')

                # Check for special characters (only alphanumeric allowed)
                if not code.isalnum():
                    raise ValidationError('Leave code must contain only letters and numbers (no spaces or special characters).')

                # Check for duplicates
                duplicate = self.search([
                    ('leave_short_code', '=', code),
                    ('id', '!=', record.id)
                ], limit=1)

                if duplicate:
                    raise ValidationError(
                        f'Leave code "{code}" is already used by "{duplicate.name}". '
                        'Please choose a different code.'
                    )

    def _clean_short_code(self, code):
        """Clean and format short code"""
        if code:
            return code.strip().upper()
        return code

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate short code if not provided, clean if provided"""
        for vals in vals_list:
            # Clean the code if provided
            if vals.get('leave_short_code'):
                vals['leave_short_code'] = self._clean_short_code(vals['leave_short_code'])
            # Auto-generate if not provided
            elif vals.get('name'):
                vals['leave_short_code'] = self._generate_short_code(vals['name'])
        return super(HrLeaveType, self).create(vals_list)

    def write(self, vals):
        """Clean short code before writing"""
        if 'leave_short_code' in vals:
            vals['leave_short_code'] = self._clean_short_code(vals['leave_short_code'])
        return super(HrLeaveType, self).write(vals)

    def _generate_short_code(self, name):
        """Generate a short code from leave type name"""
        if not name:
            return ''

        # Common mappings
        name_lower = name.lower()
        if 'sick' in name_lower:
            base_code = 'SL'
        elif 'paid' in name_lower or 'annual' in name_lower or 'vacation' in name_lower:
            base_code = 'PL'
        elif 'casual' in name_lower:
            base_code = 'CL'
        elif 'unpaid' in name_lower:
            base_code = 'UL'
        elif 'comp' in name_lower or 'compensatory' in name_lower:
            base_code = 'CO'
        elif 'maternity' in name_lower:
            base_code = 'ML'
        elif 'paternity' in name_lower:
            base_code = 'PAL'
        elif 'marriage' in name_lower or 'wedding' in name_lower:
            base_code = 'MAR'
        elif 'bereavement' in name_lower or 'mourning' in name_lower:
            base_code = 'BL'
        elif 'study' in name_lower or 'education' in name_lower:
            base_code = 'EDU'
        elif 'medical' in name_lower:
            base_code = 'ML'
        else:
            # Take first letter of each word (up to 3 letters)
            words = name.strip().split()
            if len(words) == 1:
                base_code = words[0][:3].upper()
            else:
                base_code = ''.join([w[0].upper() for w in words[:3]])

        # Ensure unique code
        code = base_code
        counter = 1
        while self.search([('leave_short_code', '=', code)], limit=1):
            code = f'{base_code}{counter}'
            counter += 1
            if counter > 99:  # Safety limit
                code = base_code
                break

        return code[:5]  # Ensure max 5 characters

    @api.model
    def _set_default_leave_codes(self):
        """
        Initialize default short codes for existing leave types.
        This is called during module installation/upgrade via XML data file.
        Only updates leave types that don't already have a short code.
        """
        default_codes = [
            (['sick'], 'SL'),
            (['paid', 'annual'], 'PL'),
            (['casual'], 'CL'),
            (['unpaid'], 'UL'),
            (['comp', 'compensatory'], 'CO'),
            (['maternity'], 'ML'),
            (['paternity'], 'PAL'),
            (['marriage', 'wedding'], 'MAR'),
            (['bereavement', 'mourning'], 'BL'),
            (['study', 'education'], 'EDU'),
            (['medical'], 'MED'),
        ]

        for keywords, code in default_codes:
            # Build domain to search for leave types matching any keyword
            domain = ['|'] * (len(keywords) - 1) if len(keywords) > 1 else []
            domain.extend([('name', 'ilike', keyword) for keyword in keywords])
            # Only update if no short code is set
            domain.append(('leave_short_code', '=', False))

            leave_types = self.search(domain)
            if leave_types:
                # Update only if the code is not already used
                if not self.search([('leave_short_code', '=', code)], limit=1):
                    # Update the first matching leave type
                    leave_types[0].write({'leave_short_code': code})

        return True
