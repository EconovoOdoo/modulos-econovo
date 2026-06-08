import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# XML IDs of every activity type owned by this module.
# Used when reassigning existing activities to the substitute.
_APPROVAL_ACTIVITY_XML_IDS = [
    'econovo_payment_approval.mail_activity_type_revisar_pago',
    'econovo_payment_approval.mail_activity_type_pago_rechazado',
    'econovo_payment_approval.mail_activity_type_aprobar_asiento',
    'econovo_payment_approval.mail_activity_type_asiento_rechazado',
]


class EconovoApprovalSubstitution(models.Model):
    _name = 'econovo.approval.substitution'
    _description = 'Approval User Substitution'
    _order = 'date_start desc, id desc'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    original_user_id = fields.Many2one(
        'res.users',
        string='Usuario ausente',
        required=True,
        index=True,
        help='The approver who is absent and whose activities should be redirected.',
    )
    substitute_user_id = fields.Many2one(
        'res.users',
        string='Sustituto',
        required=True,
        help='The user who will cover approvals during the absence.',
    )
    trigger_mode = fields.Selection(
        [
            ('manual', 'Manual (por fechas)'),
            ('hr_leave', 'Automático (licencias HR)'),
            ('both', 'Ambos'),
        ],
        string='Modo de activación',
        default='both',
        required=True,
        help=(
            'Manual: active within the configured date range only.\n'
            'HR Auto: active whenever the absent user has an approved HR leave today.'
            ' Requires the hr module to be installed.\n'
            'Both: the substitution activates if EITHER condition holds.'
        ),
    )
    date_start = fields.Date(
        string='Desde',
        help='Required for Manual and Both modes. First day the substitution is active.',
    )
    date_end = fields.Date(
        string='Hasta',
        help='Last day the substitution is active. Leave empty for open-ended.',
    )
    notes = fields.Text(string='Notas')
    active = fields.Boolean(default=True)

    is_currently_active = fields.Boolean(
        compute='_compute_is_currently_active',
        string='Activa ahora',
        store=False,
        help=(
            'For Manual/Both modes: True when today falls within the date range.\n'
            'For HR Auto mode: always shown as True (actual activation is evaluated '
            'at routing time when an HR leave is detected).'
        ),
    )

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------

    @api.depends('trigger_mode', 'date_start', 'date_end', 'active')
    def _compute_is_currently_active(self):
        today = fields.Date.today()
        for rec in self:
            if not rec.active:
                rec.is_currently_active = False
            elif rec.trigger_mode == 'hr_leave':
                # Activation depends on a live HR leave check; show as "configured".
                # The real evaluation happens in _get_effective_approver at routing time.
                rec.is_currently_active = True
            else:
                # manual or both: evaluate the date range
                rec.is_currently_active = bool(
                    rec.date_start
                    and rec.date_start <= today
                    and (not rec.date_end or rec.date_end >= today)
                )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('original_user_id', 'substitute_user_id')
    def _check_different_users(self):
        for rec in self:
            if rec.original_user_id == rec.substitute_user_id:
                raise ValidationError(
                    _('The substitute cannot be the same as the original user.')
                )

    @api.constrains('trigger_mode', 'date_start')
    def _check_date_required_for_manual(self):
        for rec in self:
            if rec.trigger_mode in ('manual', 'both') and not rec.date_start:
                raise ValidationError(
                    _('Start date is required when the trigger mode is Manual or Both.')
                )

    @api.constrains('date_start', 'date_end')
    def _check_date_order(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError(_('End date cannot be earlier than start date.'))

    @api.constrains(
        'original_user_id', 'date_start', 'date_end', 'trigger_mode', 'active'
    )
    def _check_no_overlap(self):
        """Prevent overlapping manual substitutions for the same original user.

        Two records overlap when their date ranges intersect.
        [A, B] overlaps [C, D]  iff  A <= D  and  C <= B
        (using 9999-12-31 as a proxy for "no end date").
        """
        infinity = fields.Date.from_string('9999-12-31')
        for rec in self.filtered(
            lambda r: r.active and r.trigger_mode in ('manual', 'both') and r.date_start
        ):
            candidates = self.search([
                ('original_user_id', '=', rec.original_user_id.id),
                ('trigger_mode', 'in', ('manual', 'both')),
                ('active', '=', True),
                ('id', '!=', rec.id),
                ('date_start', '!=', False),
            ])
            rec_end = rec.date_end or infinity
            for other in candidates:
                other_end = other.date_end or infinity
                if rec.date_start <= other_end and other.date_start <= rec_end:
                    raise ValidationError(_(
                        'There is already an active manual substitution for %(user)s '
                        'that overlaps this period (%(existing)s).',
                        user=rec.original_user_id.name,
                        existing=other.display_name,
                    ))

    # ------------------------------------------------------------------
    # Core resolution method (called from account.payment / account.move)
    # ------------------------------------------------------------------

    @api.model
    def _get_effective_approver(self, user_id):
        """Return the effective approver for user_id, considering substitutions.

        Resolution priority:
        1. Manual substitution: trigger_mode in (manual, both),
           date_start <= today <= date_end (or date_end is False).
        2. HR Leave auto: user has an approved hr.leave today AND a substitution
           with trigger_mode in (hr_leave, both) exists (no date restriction).
        3. Original user_id — safe fallback when no substitution applies.

        Only ONE level of substitution is resolved (no chaining). If the
        resolved substitute also has a substitution, it is NOT followed.
        """
        today = fields.Date.today()

        # ------ Priority 1: manual substitution active by date ------
        manual_sub = self.search([
            ('original_user_id', '=', user_id),
            ('active', '=', True),
            ('trigger_mode', 'in', ['manual', 'both']),
            ('date_start', '<=', today),
            '|', ('date_end', '=', False), ('date_end', '>=', today),
        ], limit=1)
        if manual_sub:
            return manual_sub.substitute_user_id.id

        # ------ Priority 2: HR Leave auto-detection ------
        HrLeave = self.env.get('hr.leave')
        if HrLeave is not None:
            now = fields.Datetime.now()
            # sudo() is required: the calling user may not have HR read rights.
            on_leave = bool(HrLeave.sudo().search([
                ('employee_id.user_id', '=', user_id),
                ('state', '=', 'validate'),
                ('date_from', '<=', now),
                ('date_to', '>=', now),
            ], limit=1))
            if on_leave:
                hr_sub = self.search([
                    ('original_user_id', '=', user_id),
                    ('active', '=', True),
                    ('trigger_mode', 'in', ['hr_leave', 'both']),
                ], limit=1)
                if hr_sub:
                    return hr_sub.substitute_user_id.id
                _logger.warning(
                    'econovo_payment_approval: approver %s (id=%s) has an approved '
                    'HR leave but no substitution is configured. '
                    'Activity assigned to the original user.',
                    self.env['res.users'].browse(user_id).name,
                    user_id,
                )

        # ------ Priority 3: no substitution — use original ------
        return user_id

    # ------------------------------------------------------------------
    # Action: reassign pending activities (button on form)
    # ------------------------------------------------------------------

    def action_reassign_pending_activities(self):
        """Reassign all pending approval activities from original_user to substitute.

        Touches only the four activity types owned by this module:
        revisar_pago, pago_rechazado, aprobar_asiento, asiento_rechazado.
        Posts a chatter note on each affected record for traceability.
        Returns a success notification with the count of reassigned activities.
        """
        self.ensure_one()

        # Collect the relevant activity type records (may not all exist yet).
        activity_types = self.env['mail.activity.type']
        for xml_id in _APPROVAL_ACTIVITY_XML_IDS:
            atype = self.env.ref(xml_id, raise_if_not_found=False)
            if atype:
                activity_types |= atype

        if not activity_types:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin tipos de actividad'),
                    'message': _('No se encontraron tipos de actividad de aprobación.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        activities = self.env['mail.activity'].sudo().search([
            ('user_id', '=', self.original_user_id.id),
            ('activity_type_id', 'in', activity_types.ids),
        ])

        if not activities:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin actividades pendientes'),
                    'message': _(
                        'No hay actividades de aprobación pendientes para %s.',
                        self.original_user_id.name,
                    ),
                    'type': 'info',
                    'sticky': False,
                },
            }

        reassigned_count = len(activities)
        activities.sudo().write({'user_id': self.substitute_user_id.id})

        # Post a chatter note on each affected record for full traceability.
        for activity in activities:
            record = self.env[activity.res_model].sudo().browse(activity.res_id)
            if record.exists():
                record.message_post(
                    body=Markup(
                        '<p>Aprobador reasignado de <strong>%(original)s</strong> '
                        'a <strong>%(substitute)s</strong> por sustitución activa.</p>'
                    ) % {
                        'original': Markup.escape(self.original_user_id.name),
                        'substitute': Markup.escape(self.substitute_user_id.name),
                    },
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Actividades reasignadas'),
                'message': _(
                    '%(count)s actividad(es) de %(original)s reasignada(s) a %(substitute)s.',
                    count=reassigned_count,
                    original=self.original_user_id.name,
                    substitute=self.substitute_user_id.name,
                ),
                'type': 'success',
                'sticky': False,
            },
        }

    # ------------------------------------------------------------------
    # Cron: daily alert for approvers on leave without a substitution
    # ------------------------------------------------------------------

    @api.model
    def _cron_alert_missing_substitutions(self):
        """Daily cron: detect approvers on HR leave without a configured substitution.

        Collects all users referenced in active approval rules who have an
        approved hr.leave today but no active substitution of any trigger mode.
        Sends one summary email to all accounting managers.
        Skips silently if the hr module is not installed or no issues are found.
        """
        HrLeave = self.env.get('hr.leave')
        if HrLeave is None:
            return  # hr module not installed — nothing to check

        # Collect all user_ids referenced in active approval rules.
        rule_users = list(set(
            self.env['econovo.approval.rule']
            .search([('active', '=', True), ('user_id', '!=', False)])
            .mapped('user_id.id')
        ))
        if not rule_users:
            return

        today = fields.Date.today()
        now = fields.Datetime.now()

        # Find which rule-users have an approved leave today.
        on_leave_user_ids = (
            HrLeave.sudo()
            .search([
                ('employee_id.user_id', 'in', rule_users),
                ('state', '=', 'validate'),
                ('date_from', '<=', now),
                ('date_to', '>=', now),
            ])
            .mapped('employee_id.user_id.id')
        )

        missing = []
        for uid in on_leave_user_ids:
            # Check for any active manual substitution covering today.
            has_manual = bool(self.search([
                ('original_user_id', '=', uid),
                ('active', '=', True),
                ('trigger_mode', 'in', ['manual', 'both']),
                ('date_start', '<=', today),
                '|', ('date_end', '=', False), ('date_end', '>=', today),
            ], limit=1))
            # Check for any hr_leave substitution (dates not required).
            has_hr_sub = bool(self.search([
                ('original_user_id', '=', uid),
                ('active', '=', True),
                ('trigger_mode', 'in', ['hr_leave', 'both']),
            ], limit=1))
            if not has_manual and not has_hr_sub:
                user = self.env['res.users'].browse(uid)
                missing.append(user.name)

        if not missing:
            return

        _logger.info(
            'econovo_payment_approval cron: %d approver(s) on leave without '
            'substitution: %s',
            len(missing),
            ', '.join(missing),
        )

        # Send one summary email to all accounting managers.
        manager_group = self.env.ref(
            'account.group_account_manager', raise_if_not_found=False
        )
        if not manager_group:
            return

        manager_emails = [u.email for u in manager_group.users if u.email]
        if not manager_emails:
            return

        user_list_html = ''.join(
            '<li>%s</li>' % name for name in missing
        )
        body_html = Markup(
            '<p><strong>⚠️ Aprobadores sin sustitución configurada</strong></p>'
            '<p>Los siguientes aprobadores tienen licencia aprobada hoy '
            'pero no tienen una sustitución de aprobación configurada:</p>'
            '<ul>%(users)s</ul>'
            '<p>Por favor configure las sustituciones en:<br/>'
            '<em>Contabilidad → Configuración → Sustituciones de Aprobación</em></p>'
        ) % {'users': Markup(user_list_html)}

        self.env['mail.mail'].sudo().create({
            'subject': _('[Econovo] Aprobadores sin sustitución configurada — %s', today),
            'body_html': body_html,
            'email_to': ','.join(manager_emails),
            'auto_delete': True,
        }).send()
