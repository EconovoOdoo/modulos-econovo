import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WebsiteFormFieldWhitelist(models.Model):
    """Configure which model fields are exposed to the Website Form Builder.

    Each active record sets ``website_form_blacklisted = False`` on the targeted
    field of the live registry. Deactivating or removing a record restores
    ``website_form_blacklisted = True`` for that field.

    :meth:`_register_hook` runs on every worker startup and re-applies the
    persisted configuration. Runtime changes are propagated to other workers
    through :meth:`odoo.modules.registry.Registry.signal_changes`.
    """

    _name = 'econovo.website.form.field.whitelist'
    _description = 'Website Form Field Whitelist (Blacklist Manager)'
    _rec_name = 'display_name'
    _order = 'model_name, field_name'

    active = fields.Boolean(default=True)
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        help="Model that owns the field to expose in the Form Builder.",
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Field',
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', model_id), ('store', '=', True)]",
        help="Field to whitelist. Must belong to the selected model.",
    )
    model_name = fields.Char(related='model_id.model', store=True, readonly=True)
    field_name = fields.Char(related='field_id.name', store=True, readonly=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)
    note = fields.Char(
        string='Note',
        help="Free-form comment explaining why this field is whitelisted.",
    )

    _sql_constraints = [
        (
            'unique_model_field',
            'UNIQUE(model_id, field_id)',
            'A whitelist entry already exists for this field.',
        ),
    ]

    # ---------------------------------------------------------------------
    # Compute & constraints
    # ---------------------------------------------------------------------
    @api.depends('model_id.model', 'field_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s.%s' % (
                rec.model_id.model or '?', rec.field_id.name or '?',
            )

    @api.constrains('model_id', 'field_id')
    def _check_field_belongs_to_model(self):
        for rec in self:
            if rec.field_id.model_id != rec.model_id:
                raise ValidationError(_(
                    "Field %(field)s does not belong to model %(model)s.",
                    field=rec.field_id.name, model=rec.model_id.model,
                ))

    # ---------------------------------------------------------------------
    # Registry application
    # ---------------------------------------------------------------------
    def _apply_to_registry(self, blacklisted):
        """Toggle ``website_form_blacklisted`` on the live registry field object.

        :param blacklisted: True to restore the blacklist, False to whitelist.
        """
        registry = self.env.registry
        for rec in self:
            model_name = rec.model_id.model
            field_name = rec.field_id.name
            if not model_name or not field_name:
                continue
            Model = registry.get(model_name)
            if Model is None:
                _logger.warning(
                    "Whitelist %s: model %s is not available in the registry",
                    rec.display_name, model_name,
                )
                continue
            field = Model._fields.get(field_name)
            if field is None:
                _logger.warning(
                    "Whitelist %s: field %s not found on model %s",
                    rec.display_name, field_name, model_name,
                )
                continue
            field.website_form_blacklisted = blacklisted
            _logger.info(
                "Website Form Blacklist: %s.%s -> website_form_blacklisted=%s",
                model_name, field_name, blacklisted,
            )

    @api.model
    def _apply_all_active(self):
        """Apply the whole whitelist: enable active entries, restore inactive ones."""
        active_recs = self.search([('active', '=', True)])
        inactive_recs = self.search([('active', '=', False)])
        active_recs._apply_to_registry(blacklisted=False)
        inactive_recs._apply_to_registry(blacklisted=True)

    def _signal_registry_change(self):
        """Notify other workers so they reload the registry on next request."""
        try:
            self.env.registry.signal_changes()
        except Exception:  # noqa: BLE001
            _logger.exception("signal_changes() failed after whitelist change")

    # ---------------------------------------------------------------------
    # Hook executed when the module is loaded on each worker
    # ---------------------------------------------------------------------
    def _register_hook(self):
        """Re-apply the persisted configuration on every worker startup."""
        res = super()._register_hook()
        try:
            self._apply_all_active()
        except Exception:  # noqa: BLE001
            _logger.exception("Error applying website form whitelist on load")
        return res

    # ---------------------------------------------------------------------
    # CRUD
    # ---------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered('active')._apply_to_registry(blacklisted=False)
        records._signal_registry_change()
        return records

    def write(self, vals):
        # Snapshot previous state so we can restore fields that are swapped out
        previous = {
            rec.id: (rec.model_id.model, rec.field_id.name, rec.active)
            for rec in self
        }
        res = super().write(vals)
        for rec in self:
            prev_model, prev_field, _prev_active = previous[rec.id]
            new_model = rec.model_id.model
            new_field = rec.field_id.name
            target_changed = (prev_model, prev_field) != (new_model, new_field)
            if target_changed and prev_model and prev_field:
                self._restore_raw(prev_model, prev_field)
        self.filtered('active')._apply_to_registry(blacklisted=False)
        self.filtered(lambda r: not r.active)._apply_to_registry(blacklisted=True)
        self._signal_registry_change()
        return res

    def unlink(self):
        # Restore blacklist before deleting
        self._apply_to_registry(blacklisted=True)
        res = super().unlink()
        self._signal_registry_change()
        return res

    def _restore_raw(self, model_name, field_name):
        """Restore the blacklist on a field identified by raw names."""
        Model = self.env.registry.get(model_name)
        if Model is None:
            return
        field = Model._fields.get(field_name)
        if field is None:
            return
        field.website_form_blacklisted = True
        _logger.info(
            "Website Form Blacklist: %s.%s -> website_form_blacklisted=True (restored)",
            model_name, field_name,
        )

    # ---------------------------------------------------------------------
    # Manual actions
    # ---------------------------------------------------------------------
    def action_reapply(self):
        """Re-apply the configuration (debug helper)."""
        self._apply_all_active()
        self._signal_registry_change()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Whitelist applied"),
                'message': _("Form Builder configuration was re-applied."),
                'type': 'success',
                'sticky': False,
            },
        }
