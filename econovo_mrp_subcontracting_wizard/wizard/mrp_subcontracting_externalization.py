# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpSubcontractingExternalization(models.TransientModel):
    _name = 'mrp.subcontracting.externalization'
    _description = 'Externalize a Manufacturing Operation'

    state = fields.Selection(
        [('setup', 'Setup'), ('review', 'Review')], default='setup', required=True,
    )
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
    )
    bom_id = fields.Many2one(
        'mrp.bom', string='Bill of Materials', required=True, check_company=True,
        domain="[('type', '=', 'normal'), ('company_id', '=', company_id)]",
    )
    operation_id = fields.Many2one(
        'mrp.routing.workcenter', string='Operation to Externalize',
        domain="[('bom_id', '=', bom_id)]",
        help='Leave empty to subcontract the whole product instead of a single operation.',
    )
    subcontractor_id = fields.Many2one(
        'res.partner', string='Subcontractor', required=True,
        domain="[('is_company', '=', True)]",
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse', required=True, check_company=True,
    )
    seller_price = fields.Float(string='Subcontracting Price')
    add_mto_route = fields.Boolean(
        string='Replenish on Order (MTO)',
        help='Also add the MTO route so that confirming a sale triggers the purchase order.',
    )
    eco_type_id = fields.Many2one(
        'mrp.eco.type', string='ECO Type', required=True,
        help='Type of Engineering Change Order created to register this change.',
    )
    eco_handling = fields.Selection(
        [
            ('validated', 'Create the ECO already applied'),
            ('auto', 'Create the ECO and follow the approval circuit'),
        ],
        default='validated', required=True, string='PLM Registration',
    )
    line_ids = fields.One2many(
        'mrp.subcontracting.externalization.line', 'wizard_id', string='Components',
    )
    precheck_html = fields.Html(compute='_compute_precheck_html')
    preview_html = fields.Html(compute='_compute_preview_html')

    @api.model
    def default_get(self, fields_list):
        """Derive the company and the warehouse when opened straight from an operation."""
        values = super().default_get(fields_list)
        bom = self.env['mrp.bom'].browse(values.get('bom_id'))
        if bom:
            values['company_id'] = bom.company_id.id
            if not values.get('warehouse_id'):
                values['warehouse_id'] = self.env['stock.warehouse'].search(
                    [('company_id', '=', bom.company_id.id)], limit=1).id
        return values

    @api.depends('subcontractor_id', 'warehouse_id', 'eco_type_id', 'eco_handling')
    def _compute_precheck_html(self):
        for wizard in self:
            wizard.precheck_html = wizard._render_messages(wizard._collect_prechecks())

    @api.depends('bom_id', 'operation_id', 'subcontractor_id')
    def _compute_preview_html(self):
        for wizard in self:
            wizard.preview_html = wizard._render_preview()

    @api.onchange('bom_id')
    def _onchange_bom_id(self):
        self.operation_id = False
        if self.bom_id:
            self.company_id = self.bom_id.company_id

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.warehouse_id = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1)

    def _collect_prechecks(self):
        """Return the list of blocking/non-blocking findings shown before confirming."""
        self.ensure_one()
        messages = []
        if self.subcontractor_id and not self.subcontractor_id.supplier_rank:
            messages.append(('warning', _(
                '%s is not flagged as a vendor yet. Odoo will flag it automatically on the '
                'first purchase order.', self.subcontractor_id.display_name)))
        if self.warehouse_id and not self.warehouse_id.subcontracting_to_resupply:
            messages.append(('danger', _(
                'Warehouse %s does not resupply subcontractors, so no resupply route exists '
                'and the components will never be sent automatically.',
                self.warehouse_id.display_name)))
        if self.eco_handling == 'validated' and self.eco_type_id and not self._get_apply_stage():
            messages.append(('danger', _(
                'The ECO type "%s" has no stage allowing changes to be applied. Pick another '
                'type or choose to follow the approval circuit.', self.eco_type_id.display_name)))
        return messages

    @api.model
    def _render_messages(self, messages):
        if not messages:
            return False
        return ''.join(
            '<div class="alert alert-%s" role="alert">%s</div>' % (level, body)
            for level, body in messages
        )

    def _get_apply_stage(self):
        self.ensure_one()
        return self.env['mrp.eco.stage'].search([
            ('allow_apply_change', '=', True),
            ('type_ids', 'in', self.eco_type_id.ids),
        ], order='sequence, id', limit=1)

    def _get_initial_stage(self):
        """Return the stage the ECO must be created in.

        An ECO meant to be applied right away is created directly in a stage allowing it,
        because ``mrp.eco.write()`` refuses to move an ECO across a blocking stage.
        """
        self.ensure_one()
        if self.eco_handling == 'validated':
            return self._get_apply_stage()
        return self.env['mrp.eco.stage'].search(
            [('type_ids', 'in', self.eco_type_id.ids)], order='sequence, id', limit=1)

    def _render_preview(self):
        self.ensure_one()
        if not self.bom_id:
            return False
        Chain = self.env['mrp.subcontracting.chain']
        before, after = Chain._split_route(self.bom_id, self.operation_id)
        stages = []
        if before:
            stages.append(_('In-house: %s', ', '.join(before.mapped('name'))))
        stages.append(_('Subcontracted at %s: %s', self.subcontractor_id.display_name or '?',
                        self.operation_id.name or _('whole product')))
        if after:
            stages.append(_('In-house: %s', ', '.join(after.mapped('name'))))
        phantom_count = int(bool(before)) + int(bool(after))
        summary = _(
            '<p><strong>%(stages)s Bill(s) of Materials</strong> and '
            '<strong>%(phantoms)s intermediate product(s)</strong> will result from this change.</p>',
            stages=len(stages), phantoms=phantom_count,
        )
        return summary + '<ol>%s</ol>' % ''.join('<li>%s</li>' % stage for stage in stages)

    def action_next(self):
        self.ensure_one()
        self._validate_setup()
        Chain = self.env['mrp.subcontracting.chain']
        before, after = Chain._split_route(self.bom_id, self.operation_id)
        Chain._check_operation_categories(self.operation_id, before, after)
        dummy, lines_operation, dummy2 = Chain._split_components(
            self.bom_id, self.operation_id, before, after)
        self.line_ids = [(5, 0, 0)] + [
            (0, 0, {'product_tmpl_id': product_tmpl.id})
            for product_tmpl in lines_operation.product_id.product_tmpl_id
        ]
        self.state = 'review'
        return self._reopen()

    def action_previous(self):
        self.ensure_one()
        self.state = 'setup'
        return self._reopen()

    def action_confirm(self):
        self.ensure_one()
        self._validate_setup()
        blocking = [msg for level, msg in self._collect_prechecks() if level == 'danger']
        if blocking:
            raise UserError('\n'.join(blocking))
        chain = self._run_with_eco()
        return {
            'name': _('Subcontracting Chain'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.subcontracting.chain',
            'view_mode': 'form',
            'res_id': chain.id,
        }

    def _validate_setup(self):
        self.ensure_one()
        if self.operation_id and self.operation_id.bom_id != self.bom_id:
            raise UserError(_('The selected operation does not belong to the selected '
                              'Bill of Materials.'))
        chain = self.bom_id.subcontracting_chain_id
        if chain.state == 'externalized':
            raise UserError(_(
                'This Bill of Materials is already subcontracted through the chain %s. '
                'Internalize it before externalizing it again.',
                chain.display_name,
            ))

    def _run_with_eco(self):
        """Create the ECO, build the chain on its revision, and apply it when requested."""
        self.ensure_one()
        eco = self.env['mrp.eco'].create({
            'name': _('Externalize %(operation)s of %(product)s',
                      operation=self.operation_id.name or _('the whole product'),
                      product=self.bom_id.product_tmpl_id.display_name),
            'type_id': self.eco_type_id.id,
            'stage_id': self._get_initial_stage().id,
            'type': 'bom',
            'product_tmpl_id': self.bom_id.product_tmpl_id.id,
            'bom_id': self.bom_id.id,
            'company_id': self.company_id.id,
        })
        eco.action_new_revision()
        revision_operation = self.env['mrp.routing.workcenter']
        if self.operation_id:
            revision_operation = eco.new_bom_id.operation_ids.filtered(
                lambda op: op.name == self.operation_id.name
                and op.sequence == self.operation_id.sequence
            )[:1]
            if not revision_operation:
                raise UserError(_(
                    'The operation %s could not be located on the Bill of Materials revision.',
                    self.operation_id.display_name,
                ))
        chain = self.env['mrp.subcontracting.chain']._externalize(
            eco.new_bom_id,
            revision_operation,
            self.subcontractor_id,
            self.warehouse_id,
            seller_price=self.seller_price,
            add_mto_route=self.add_mto_route,
            resupply_product_tmpls=self.line_ids.filtered('apply_route').product_tmpl_id,
            activate=False,
        )
        eco.subcontracting_chain_id = chain.id
        if self.eco_handling == 'validated':
            eco.action_apply()
            chain.write({
                'validated_by_id': self.env.user.id,
                'validated_date': fields.Datetime.now(),
            })
            eco.message_post(body=_(
                'Applied automatically by the operation subcontracting assistant, without '
                'going through the manual approval circuit.'))
        return chain

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class MrpSubcontractingExternalizationLine(models.TransientModel):
    _name = 'mrp.subcontracting.externalization.line'
    _description = 'Component Sent to the Subcontractor'

    wizard_id = fields.Many2one(
        'mrp.subcontracting.externalization', required=True, ondelete='cascade',
    )
    product_tmpl_id = fields.Many2one('product.template', string='Component', required=True)
    has_resupply_route = fields.Boolean(
        string='Route Already Set', compute='_compute_has_resupply_route',
    )
    apply_route = fields.Boolean(
        string='Add Resupply Route', default=True,
        help='Without this route Odoo never generates the delivery of this component to the '
             'subcontractor, and it fails silently.',
    )

    @api.depends('product_tmpl_id.route_ids')
    def _compute_has_resupply_route(self):
        route = self.env['mrp.subcontracting.chain']._get_resupply_route()
        for line in self:
            line.has_resupply_route = bool(route) and route in line.product_tmpl_id.route_ids
