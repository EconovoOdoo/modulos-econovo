# -*- coding: utf-8 -*-
# Author: Rafiur Rahman Rafit
# Company: Dot BD Solutions Limited
# Created: 2026-03-27
# Description: Festive Bonus model — defines bonus rules that auto-apply
#              as earning lines on payslips when activated.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DotbdFestiveBonus(models.Model):
    """Configurable festive bonus rules.

    When ``active=True``, the bonus is automatically applied as an earning
    line on every payslip whose employee (or salary template) matches the
    rule's scope.
    """
    _name = 'dotbd.festive.bonus'
    _description = 'Festive Bonus'
    _order = 'name'

    # ── Identity ────────────────────────────────────────────────────────────
    name = fields.Char(string='Name', required=True)
    country_id = fields.Many2one(
        'res.country', string='Country',
        default=lambda self: self.env.ref('base.bd', raise_if_not_found=False))
    religion = fields.Selection([
        ('islam', 'Islam'),
        ('hindu', 'Hinduism'),
        ('christian', 'Christianity'),
        ('buddhist', 'Buddhism'),
        ('jewish', 'Judaism'),
        ('sikh', 'Sikhism'),
        ('jain', 'Jainism'),
        ('shinto', 'Shinto'),
        ('cultural', 'Cultural / Regional'),
        ('universal', 'Universal (All)'),
    ], string='Religion / Category')

    # ── Bonus calculation ───────────────────────────────────────────────────
    bonus_type = fields.Selection([
        ('percentage_gross', '% of Gross Salary'),
        ('percentage_wages', '% of Basic Wages'),
        ('percentage_net', '% of Net (Gross - Deductions)'),
        ('fixed', 'Fixed Amount'),
    ], string='Bonus Type', required=True, default='percentage_wages')
    percentage = fields.Float(
        string='Percentage (%)', digits=(5, 2))
    fixed_amount = fields.Float(string='Fixed Amount')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)

    # ── Scope: who receives the bonus ───────────────────────────────────────
    apply_to = fields.Selection([
        ('template', 'Salary Template'),
        ('employee', 'Specific Employees'),
    ], string='Apply To', required=True, default='template')
    salary_template_ids = fields.Many2many(
        'dotbd.salary.template',
        'dotbd_festive_bonus_template_rel',
        'bonus_id', 'template_id',
        string='Salary Templates')
    employee_ids = fields.Many2many(
        'hr.employee',
        'dotbd_festive_bonus_employee_rel',
        'bonus_id', 'employee_id',
        string='Employees')

    # ── Status ──────────────────────────────────────────────────────────────
    active = fields.Boolean(
        string='Active', default=False,
        help='When active, this bonus is automatically applied on the next '
             'payslip generation for matching employees.')
    note = fields.Text(string='Description')

    # ── Constraints ─────────────────────────────────────────────────────────
    @api.constrains('bonus_type', 'percentage', 'fixed_amount')
    def _check_amounts(self):
        for rec in self:
            if rec.bonus_type in (
                    'percentage_gross', 'percentage_wages', 'percentage_net'):
                if rec.percentage <= 0:
                    raise ValidationError(
                        _('Percentage must be greater than 0 for '
                          'percentage-based bonus types.'))
            elif rec.bonus_type == 'fixed':
                if rec.fixed_amount <= 0:
                    raise ValidationError(
                        _('Fixed amount must be greater than 0 for '
                          'fixed bonus type.'))
