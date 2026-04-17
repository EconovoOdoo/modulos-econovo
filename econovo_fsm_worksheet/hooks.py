# -*- coding: utf-8 -*-
"""
post_init_hook for econovo_fsm_worksheet.

Runs once at module install. Creates all custom x_* fields on the auto-generated
worksheet model, updates the technician form view, updates the search view for the
Analysis button, and regenerates the standard worksheet QWeb report from the new
form view.

This approach is used instead of the _default_project_task_template_fields() hook
to avoid polluting ALL project.task worksheet template creations.
"""
import logging

_logger = logging.getLogger(__name__)

_TEMPLATE_NAME = 'Orden de Trabajo SVT-04'

# Fields that existed in v1.0.0 and must be removed from the DB on install/upgrade.
# They are replaced by the auto-populated x_so_* related fields.
_FIELDS_TO_REMOVE = ['x_num_remito', 'x_oc_cliente', 'x_num_factura']

_WORKSHEET_FIELDS = [
    {
        'name': 'x_horometro',
        'field_description': 'Horómetro',
        'ttype': 'float',
    },
    {
        'name': 'x_num_interno',
        'field_description': 'Nro Interno',
        'ttype': 'char',
    },
    {
        'name': 'x_obs_interno',
        'field_description': 'Obs. Interno',
        'ttype': 'text',
    },
    {
        'name': 'x_tipo_servicio',
        'field_description': 'Tipo de Servicio',
        'ttype': 'selection',
        'selection': (
            "[('50_250hs','50/250 HS'),('500hs','500 HS'),"
            "('750hs','750 HS'),('1000hs','1000 HS'),('otro','Otro')]"
        ),
    },
    {
        'name': 'x_tipo_falla',
        'field_description': 'Tipo de Falla',
        'ttype': 'selection',
        'selection': (
            "[('electrico','Eléctrico'),('mecanico','Mecánico'),"
            "('hidraulico','Hidráulico'),('otro','Otro')]"
        ),
    },
    {
        'name': 'x_equipo_operativo',
        'field_description': 'Equipo Operativo',
        'ttype': 'boolean',
    },
    {
        'name': 'x_proxima_visita_hs',
        'field_description': 'Próxima Visita (hs)',
        'ttype': 'float',
    },
    {
        'name': 'x_observaciones',
        'field_description': 'Observaciones',
        'ttype': 'text',
    },
    {
        'name': 'x_dni_firmante',
        'field_description': 'DNI Firmante',
        'ttype': 'char',
    },
    # --- Auto-populated from sale order / pickings ---
    {
        'name': 'x_so_name',
        'field_description': 'Ref. Orden de Venta',
        'ttype': 'char',
        'related': 'x_project_task_id.so_name',
    },
    {
        'name': 'x_so_oc_cliente',
        'field_description': 'OC Cliente',
        'ttype': 'char',
        'related': 'x_project_task_id.so_client_order_ref',
    },
    {
        'name': 'x_so_factura',
        'field_description': 'Nro Factura',
        'ttype': 'char',
        'related': 'x_project_task_id.so_invoice_name',
    },
    {
        'name': 'x_so_remito',
        'field_description': 'Nro Remito',
        'ttype': 'char',
        'related': 'x_project_task_id.so_remito_voucher',
    },
]

# x_lot_id is a stored related field — created after the simple fields.
_LOT_FIELD = {
    'name': 'x_lot_id',
    'field_description': 'Equipo (N/S)',
    'ttype': 'many2one',
    'relation': 'stock.lot',
    'related': 'x_project_task_id.lot_id',
    'store': True,
}

_FORM_ARCH = """
<form create="false" duplicate="false">
    <sheet>
        <h1 invisible="context.get('studio') or context.get('default_x_project_task_id')">
            <field name="x_project_task_id"/>
        </h1>
        <group>
            <group string="Identificación">
                <field name="x_horometro" string="Horómetro actual"/>
                <field name="x_so_name" string="Ref. Orden de Venta"/>
                <field name="x_so_remito" string="Nro Remito"/>
                <field name="x_so_oc_cliente" string="OC Cliente"/>
                <field name="x_num_interno" string="Nro Interno"/>
                <field name="x_so_factura" string="Nro Factura"/>
                <field name="x_obs_interno" string="Obs. Interno"/>
            </group>
            <group string="Clasificación">
                <field name="x_tipo_servicio"/>
                <field name="x_tipo_falla"/>
                <field name="x_equipo_operativo" string="Equipo Operativo (SI)"/>
                <field name="x_proxima_visita_hs" string="Próxima Visita (hs)"/>
            </group>
        </group>
        <group>
            <field name="x_observaciones" string="Observaciones" colspan="2"/>
            <field name="x_dni_firmante" string="DNI Firmante"/>
        </group>
    </sheet>
</form>
"""

_SEARCH_ARCH = """
<search>
    <field name="x_name"/>
    <field name="x_lot_id" string="Equipo"/>
    <filter string="Mes" date="create_date" name="create_date"/>
    <filter name="group_by_month" string="Por mes" context="{'group_by': 'create_date:month'}"/>
    <filter name="group_by_lot" string="Por equipo" context="{'group_by': 'x_lot_id'}"/>
</search>
"""


def setup_svt04_worksheet(env):
    """Add custom fields, update views, and regenerate the QWeb report for the SVT-04 template."""
    template = env['worksheet.template'].search(
        [('name', '=', _TEMPLATE_NAME)], limit=1
    )
    if not template:
        _logger.warning(
            'econovo_fsm_worksheet: template "%s" not found — skipping setup.',
            _TEMPLATE_NAME,
        )
        return

    model_id = template.model_id
    if not model_id:
        _logger.warning(
            'econovo_fsm_worksheet: template "%s" has no model_id — skipping setup.',
            _TEMPLATE_NAME,
        )
        return

    _logger.info(
        'econovo_fsm_worksheet: setting up fields and views for model %s',
        model_id.model,
    )

    existing_field_names = set(
        env['ir.model.fields'].sudo().search(
            [('model_id', '=', model_id.id)]
        ).mapped('name')
    )

    # --- Remove obsolete fields from previous versions ---
    obsolete = env['ir.model.fields'].sudo().search([
        ('model_id', '=', model_id.id),
        ('name', 'in', _FIELDS_TO_REMOVE),
    ])
    if obsolete:
        _logger.info(
            'econovo_fsm_worksheet: removing obsolete fields: %s',
            obsolete.mapped('name'),
        )
        obsolete.sudo().unlink()
        # Refresh existing field names after deletion
        existing_field_names -= set(_FIELDS_TO_REMOVE)

    # --- Create simple x_* fields (skip any already present) ---
    new_fields = [
        dict(f, model_id=model_id.id)
        for f in _WORKSHEET_FIELDS
        if f['name'] not in existing_field_names
    ]
    if new_fields:
        env['ir.model.fields'].sudo().create(new_fields)

    # --- Create x_lot_id stored related (after simple fields exist) ---
    if _LOT_FIELD['name'] not in existing_field_names:
        env['ir.model.fields'].sudo().create(dict(_LOT_FIELD, model_id=model_id.id))

    # --- Update technician's form view ---
    form_view = env['ir.ui.view'].search(
        [('model', '=', model_id.model), ('type', '=', 'form')],
        limit=1,
    )
    if form_view:
        form_view.sudo().write({'arch': _FORM_ARCH})
    else:
        _logger.warning(
            'econovo_fsm_worksheet: form view for %s not found.', model_id.model
        )

    # --- Update search view (for Analysis button grouping) ---
    search_view = env['ir.ui.view'].search(
        [('model', '=', model_id.model), ('type', '=', 'search')],
        limit=1,
    )
    if search_view:
        search_view.sudo().write({'arch': _SEARCH_ARCH})
    else:
        _logger.warning(
            'econovo_fsm_worksheet: search view for %s not found.', model_id.model
        )

    # --- Regenerate the standard worksheet QWeb from the updated form view ---
    # This gives a decent auto-gen rendering in the standard "Field Service Report".
    template.sudo()._generate_qweb_report_template()

    _logger.info('econovo_fsm_worksheet: SVT-04 worksheet setup complete.')
