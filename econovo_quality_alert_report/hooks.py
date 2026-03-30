# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)

# Mapping: Studio text value → severity XML ID
_SEVERITY_MAP = {
    'nc mayor': 'econovo_quality_alert_report.severity_nc_mayor',
    'nc menor': 'econovo_quality_alert_report.severity_nc_menor',
    'observación': 'econovo_quality_alert_report.severity_observacion',
    'observacion': 'econovo_quality_alert_report.severity_observacion',
    'oportunidad de mejora': 'econovo_quality_alert_report.severity_oportunidad_mejora',
}


def migrate_studio_fields(env):
    """Migrate Studio custom field values to the new proper fields.

    Called from post_init_hook. Reads x_studio_* fields (if they exist)
    and copies values to the corresponding new fields.
    """
    QualityAlert = env['quality.alert']

    # Check if Studio fields exist
    studio_fields = [
        'x_studio_tipo_de_hallazgo',
        'x_studio_departamento',
        'x_studio_responsable_de_contencin',
        'x_studio_fecha_de_verificacin',
    ]
    existing_fields = [f for f in studio_fields if f in QualityAlert._fields]
    if not existing_fields:
        _logger.info("No Studio fields found on quality.alert, skipping migration.")
        return

    alerts = QualityAlert.search([])
    _logger.info("Migrating Studio fields for %d quality.alert records...", len(alerts))
    migrated = 0

    for alert in alerts:
        vals = {}

        # Severity: map free text to Many2one
        if 'x_studio_tipo_de_hallazgo' in existing_fields and alert.x_studio_tipo_de_hallazgo:
            text_lower = alert.x_studio_tipo_de_hallazgo.strip().lower()
            xml_id = _SEVERITY_MAP.get(text_lower)
            if xml_id:
                severity = env.ref(xml_id, raise_if_not_found=False)
                if severity:
                    vals['severity_id'] = severity.id
            else:
                _logger.warning(
                    "quality.alert %s: unmapped severity '%s'",
                    alert.name, alert.x_studio_tipo_de_hallazgo,
                )

        # Department: Many2one → Many2one (direct copy)
        if 'x_studio_departamento' in existing_fields and alert.x_studio_departamento:
            vals['department_id'] = alert.x_studio_departamento.id

        # Containment responsible: Many2one res.partner → Many2one res.users
        if 'x_studio_responsable_de_contencin' in existing_fields and alert.x_studio_responsable_de_contencin:
            partner = alert.x_studio_responsable_de_contencin
            user = env['res.users'].search([('partner_id', '=', partner.id)], limit=1)
            if user:
                vals['containment_responsible_id'] = user.id
            else:
                _logger.warning(
                    "quality.alert %s: no user found for partner '%s' (id=%d)",
                    alert.name, partner.name, partner.id,
                )

        # Verification date: Datetime → Date
        if 'x_studio_fecha_de_verificacin' in existing_fields and alert.x_studio_fecha_de_verificacin:
            vals['verification_date'] = alert.x_studio_fecha_de_verificacin.date()

        if vals:
            alert.write(vals)
            migrated += 1

    _logger.info("Studio field migration complete: %d/%d records updated.", migrated, len(alerts))
