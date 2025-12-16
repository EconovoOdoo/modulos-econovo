# ACTUALIZACIÓN DE DISEÑO - Integración con Fechas Nativas y Estados Dinámicos

**Fecha**: 16 de Diciembre de 2025  
**Versión**: 1.1

---

## 1. INTEGRACIÓN CON FECHAS NATIVAS DE ODOO

### 1.1 Campos de Fecha Existentes en Odoo Nativo

| Módulo | Modelo | Campo | Descripción |
|--------|--------|-------|-------------|
| **purchase** | `purchase.order` | `date_planned` | Fecha esperada de llegada (ETA) |
| **purchase** | `purchase.order.line` | `date_planned` | Fecha esperada por línea |
| **stock** | `stock.picking` | `scheduled_date` | Fecha programada de la operación |
| **stock** | `stock.picking` | `date_deadline` | Fecha límite prometida al cliente |
| **stock** | `stock.picking` | `date_done` | Fecha real de transferencia |
| **stock** | `stock.move` | `date` | Fecha programada del movimiento |
| **stock** | `stock.move` | `date_deadline` | Fecha límite del movimiento |

### 1.2 Nuevo Diseño: Sincronización Bidireccional

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    SINCRONIZACIÓN DE FECHAS ETA/ETD                          │
└──────────────────────────────────────────────────────────────────────────────┘

COMEX.OPERATION                    PURCHASE.ORDER                  STOCK.PICKING
─────────────────                  ──────────────                  ─────────────
                                   
     date_etd  ◄────────────────────────────────────────────────► (No aplica)
     (Salida)                                                      
                                                                   
     date_eta  ◄─────────────────► date_planned ◄───────────────► scheduled_date
     (Llegada)                     (Fecha esperada)               (Fecha programada)
                                                                   
     date_arrival ◄──────────────────────────────────────────────► date_done
     (Llegada real)                                                (Fecha real)


FLUJO DE SINCRONIZACIÓN:
────────────────────────

1. USUARIO CREA OPERACIÓN COMEX:
   ┌─────────────────────────────────────────────────────────────────────┐
   │  Al ingresar date_eta en comex.operation:                          │
   │  → Actualiza purchase.order.date_planned (si está vinculado)       │
   │  → Actualiza stock.picking.scheduled_date (recepciones asociadas)  │
   └─────────────────────────────────────────────────────────────────────┘

2. USUARIO MODIFICA DESDE COMPRA:
   ┌─────────────────────────────────────────────────────────────────────┐
   │  Al modificar date_planned en purchase.order:                      │
   │  → Actualiza comex.operation.date_eta (si existe operación COMEX)  │
   │  → Actualiza stock.picking.scheduled_date                          │
   └─────────────────────────────────────────────────────────────────────┘

3. ARRIBO REAL:
   ┌─────────────────────────────────────────────────────────────────────┐
   │  Al validar stock.picking (recepción):                             │
   │  → Se registra date_done automáticamente                           │
   │  → Actualiza comex.operation.date_arrival                          │
   │  → Cambia estado de embarque a 'arrived'                           │
   └─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Código: Sincronización con Purchase y Stock

```python
class ComexOperation(models.Model):
    _name = 'comex.operation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # === FECHAS - INTEGRADAS CON ODOO NATIVO ===
    date_etd = fields.Date(
        string="ETD (Fecha Embarque)",
        tracking=True,
        help="Estimated Time of Departure - Fecha estimada de salida del puerto origen"
    )
    date_eta = fields.Date(
        string="ETA (Fecha Llegada)",
        tracking=True,
        help="Estimated Time of Arrival - Fecha estimada de arribo. "
             "Se sincroniza con fecha programada de recepciones."
    )
    date_arrival = fields.Date(
        string="Fecha Arribo Real",
        tracking=True,
        compute='_compute_date_arrival',
        store=True,
        help="Fecha real de arribo. Se calcula desde la validación de recepciones."
    )
    
    # Campos para mostrar alertas de atraso
    is_late = fields.Boolean(
        string="Atrasado",
        compute='_compute_is_late',
        store=True
    )
    days_delay = fields.Integer(
        string="Días de Atraso",
        compute='_compute_is_late',
        store=True
    )
    
    @api.depends('date_eta')
    def _compute_is_late(self):
        today = fields.Date.today()
        for record in self:
            if record.date_eta and record.state not in ('received', 'closed', 'cancelled'):
                record.days_delay = (today - record.date_eta).days if today > record.date_eta else 0
                record.is_late = record.days_delay > 0
            else:
                record.is_late = False
                record.days_delay = 0
    
    @api.depends('picking_ids.date_done')
    def _compute_date_arrival(self):
        for record in self:
            done_pickings = record.picking_ids.filtered(lambda p: p.state == 'done')
            if done_pickings:
                record.date_arrival = max(done_pickings.mapped('date_done')).date()
            else:
                record.date_arrival = False
    
    # === SINCRONIZACIÓN CON PURCHASE.ORDER ===
    @api.onchange('date_eta')
    def _onchange_date_eta_sync(self):
        """Sincroniza ETA con fecha planificada de órdenes de compra"""
        if self.date_eta and self.purchase_order_ids:
            # Mostrar advertencia al usuario
            return {
                'warning': {
                    'title': _('Sincronización de Fechas'),
                    'message': _(
                        'La fecha ETA se sincronizará con la fecha esperada de las '
                        'órdenes de compra y recepciones vinculadas al guardar.'
                    )
                }
            }
    
    def write(self, vals):
        res = super().write(vals)
        if 'date_eta' in vals:
            self._sync_dates_to_purchase_stock()
        return res
    
    def _sync_dates_to_purchase_stock(self):
        """Sincroniza date_eta con purchase.order y stock.picking"""
        for record in self:
            if not record.date_eta:
                continue
            
            # Convertir a datetime para campos Datetime
            eta_datetime = fields.Datetime.to_datetime(record.date_eta)
            
            # Sincronizar con órdenes de compra
            if record.purchase_order_ids:
                record.purchase_order_ids.write({
                    'date_planned': eta_datetime
                })
                # También actualizar líneas
                record.purchase_order_ids.order_line.write({
                    'date_planned': eta_datetime
                })
            
            # Sincronizar con recepciones (pickings)
            if record.picking_ids:
                pending_pickings = record.picking_ids.filtered(
                    lambda p: p.state not in ('done', 'cancel')
                )
                pending_pickings.write({
                    'scheduled_date': eta_datetime
                })
    
    # === RELACIÓN CON STOCK.PICKING ===
    picking_ids = fields.One2many(
        'stock.picking',
        'comex_operation_id',
        string="Recepciones/Entregas"
    )
    picking_count = fields.Integer(
        compute='_compute_picking_count',
        string="Transferencias"
    )
    
    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for record in self:
            record.picking_count = len(record.picking_ids)
```

### 1.4 Extensión de Stock.Picking

```python
class StockPickingComex(models.Model):
    _inherit = 'stock.picking'
    
    comex_operation_id = fields.Many2one(
        'comex.operation',
        string="Operación COMEX",
        tracking=True,
        copy=False,
        help="Operación de comercio exterior asociada"
    )
    comex_customs_number = fields.Char(
        string="Nro. Despacho",
        related='comex_operation_id.customs_clearance_number',
        store=True,
        help="Número de despacho de la operación COMEX"
    )
    
    def button_validate(self):
        """Extiende validación para actualizar operación COMEX"""
        res = super().button_validate()
        
        # Actualizar operación COMEX al validar recepción
        for picking in self.filtered(lambda p: p.comex_operation_id and p.state == 'done'):
            operation = picking.comex_operation_id
            
            # Si es la última recepción, cambiar estado a 'received'
            pending_pickings = operation.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel') and p.id != picking.id
            )
            if not pending_pickings and operation.state in ('released', 'in_warehouse'):
                operation.write({'state': 'received'})
        
        return res
```

### 1.5 Extensión de Purchase.Order

```python
class PurchaseOrderComex(models.Model):
    _inherit = 'purchase.order'
    
    comex_operation_id = fields.Many2one(
        'comex.operation',
        string="Operación COMEX",
        tracking=True,
        copy=False
    )
    
    def write(self, vals):
        """Sincroniza cambios de fecha con operación COMEX"""
        res = super().write(vals)
        
        # Si cambia date_planned y tiene operación COMEX
        if 'date_planned' in vals:
            for order in self.filtered('comex_operation_id'):
                if order.date_planned:
                    order.comex_operation_id.write({
                        'date_eta': order.date_planned.date()
                    })
        
        return res
    
    def button_confirm(self):
        """Al confirmar PO, vincular pickings a operación COMEX"""
        res = super().button_confirm()
        
        for order in self.filtered('comex_operation_id'):
            # Obtener pickings generados
            pickings = order.picking_ids.filtered(
                lambda p: not p.comex_operation_id
            )
            pickings.write({
                'comex_operation_id': order.comex_operation_id.id
            })
        
        return res
```

---

## 2. ESTADOS DINÁMICOS (CONFIGURABLES POR USUARIO)

### 2.1 Nuevo Modelo: `comex.operation.stage`

Siguiendo el patrón de `crm.stage` y `project.task.type`, los estados serán configurables:

```python
class ComexOperationStage(models.Model):
    _name = 'comex.operation.stage'
    _description = 'Etapa de Operación COMEX'
    _order = 'sequence, id'
    
    name = fields.Char(
        string="Nombre de Etapa",
        required=True,
        translate=True
    )
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
        help="Orden de aparición en vistas Kanban y formularios"
    )
    description = fields.Text(
        string="Descripción",
        translate=True,
        help="Descripción interna de esta etapa"
    )
    
    # === COMPORTAMIENTO ===
    fold = fields.Boolean(
        string="Plegado en Kanban",
        help="Si está marcado, esta etapa aparecerá plegada en la vista Kanban"
    )
    is_initial = fields.Boolean(
        string="Es Etapa Inicial",
        help="Etapa por defecto al crear una operación"
    )
    is_closed = fields.Boolean(
        string="Es Etapa de Cierre",
        help="Indica que la operación está finalizada"
    )
    is_cancelled = fields.Boolean(
        string="Es Etapa de Cancelación",
        help="Indica que la operación fue cancelada"
    )
    
    # === APARIENCIA ===
    color = fields.Integer(
        string="Color",
        help="Color para identificar visualmente la etapa"
    )
    
    # === AUTOMATIZACIONES ===
    mail_template_id = fields.Many2one(
        'mail.template',
        string="Plantilla de Email",
        domain="[('model', '=', 'comex.operation')]",
        help="Si se configura, se enviará un email automático al alcanzar esta etapa"
    )
    
    # === RESTRICCIONES ===
    operation_type = fields.Selection([
        ('all', 'Todas'),
        ('import', 'Solo Importaciones'),
        ('export', 'Solo Exportaciones'),
    ], string="Tipo de Operación", default='all',
        help="Limitar esta etapa a un tipo específico de operación"
    )
    
    company_id = fields.Many2one(
        'res.company',
        string="Compañía",
        default=lambda self: self.env.company,
        help="Dejar vacío para usar en todas las compañías"
    )
    
    active = fields.Boolean(
        string="Activo",
        default=True
    )
    
    # === INDICADORES ===
    operation_count = fields.Integer(
        string="Operaciones",
        compute='_compute_operation_count'
    )
    
    @api.depends()
    def _compute_operation_count(self):
        for stage in self:
            stage.operation_count = self.env['comex.operation'].search_count([
                ('stage_id', '=', stage.id)
            ])
    
    @api.constrains('is_initial')
    def _check_single_initial(self):
        """Solo puede haber una etapa inicial por tipo de operación"""
        for stage in self.filtered('is_initial'):
            domain = [
                ('is_initial', '=', True),
                ('id', '!=', stage.id),
                ('operation_type', 'in', [stage.operation_type, 'all'])
            ]
            if stage.company_id:
                domain.append(('company_id', '=', stage.company_id.id))
            
            existing = self.search(domain, limit=1)
            if existing:
                existing.is_initial = False
```

### 2.2 Modelo Principal Actualizado: `comex.operation`

```python
class ComexOperation(models.Model):
    _name = 'comex.operation'
    _description = 'Operación de Comercio Exterior'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'
    
    # === ETAPA DINÁMICA (reemplaza campo state fijo) ===
    stage_id = fields.Many2one(
        'comex.operation.stage',
        string="Etapa",
        tracking=True,
        copy=False,
        group_expand='_read_group_stage_ids',
        domain="['|', ('operation_type', '=', 'all'), ('operation_type', '=', operation_type)]",
        default=lambda self: self._get_default_stage()
    )
    
    # Campos computados para compatibilidad y reportes
    is_closed = fields.Boolean(
        string="Cerrado",
        related='stage_id.is_closed',
        store=True
    )
    is_cancelled = fields.Boolean(
        string="Cancelado",
        related='stage_id.is_cancelled',
        store=True
    )
    kanban_state = fields.Selection([
        ('normal', 'Gris'),
        ('done', 'Verde'),
        ('blocked', 'Rojo'),
    ], string="Estado Kanban", default='normal', copy=False,
        help="Estado visual adicional para indicar progreso dentro de la etapa")
    
    color = fields.Integer(
        string="Color",
        related='stage_id.color'
    )
    
    # === MÉTODOS PARA ETAPAS ===
    @api.model
    def _get_default_stage(self):
        """Obtiene la etapa inicial por defecto"""
        operation_type = self.env.context.get('default_operation_type', 'import')
        return self.env['comex.operation.stage'].search([
            ('is_initial', '=', True),
            '|', ('operation_type', '=', 'all'), ('operation_type', '=', operation_type),
            '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)
        ], limit=1)
    
    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Muestra todas las etapas en vista Kanban, incluso vacías"""
        operation_type = self.env.context.get('default_operation_type')
        search_domain = [
            '|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)
        ]
        if operation_type:
            search_domain = expression.AND([
                search_domain,
                ['|', ('operation_type', '=', 'all'), ('operation_type', '=', operation_type)]
            ])
        return stages.search(search_domain, order=order)
    
    def write(self, vals):
        """Ejecuta acciones al cambiar de etapa"""
        res = super().write(vals)
        
        if 'stage_id' in vals:
            self._on_stage_change()
        
        return res
    
    def _on_stage_change(self):
        """Acciones automáticas al cambiar de etapa"""
        for record in self:
            stage = record.stage_id
            
            # Enviar email si está configurado
            if stage.mail_template_id:
                stage.mail_template_id.send_mail(record.id, force_send=True)
            
            # Registrar fecha de cierre
            if stage.is_closed and not record.date_closed:
                record.date_closed = fields.Date.today()
    
    # Campo para fecha de cierre
    date_closed = fields.Date(
        string="Fecha de Cierre",
        tracking=True,
        copy=False
    )
```

### 2.3 Datos Iniciales de Etapas

```xml
<!-- data/comex_operation_stage_data.xml -->
<odoo>
    <data noupdate="1">
        
        <!-- ETAPAS POR DEFECTO -->
        <record id="stage_draft" model="comex.operation.stage">
            <field name="name">Borrador</field>
            <field name="sequence">10</field>
            <field name="is_initial">True</field>
            <field name="color">0</field>
            <field name="description">Operación en preparación, aún no confirmada.</field>
        </record>
        
        <record id="stage_confirmed" model="comex.operation.stage">
            <field name="name">Confirmado</field>
            <field name="sequence">20</field>
            <field name="color">1</field>
            <field name="description">Operación confirmada, pendiente de coordinación.</field>
        </record>
        
        <record id="stage_coordinating" model="comex.operation.stage">
            <field name="name">En Coordinación</field>
            <field name="sequence">30</field>
            <field name="color">2</field>
            <field name="description">Coordinando embarque con proveedor y agente de carga.</field>
        </record>
        
        <record id="stage_in_transit" model="comex.operation.stage">
            <field name="name">En Viaje</field>
            <field name="sequence">40</field>
            <field name="color">4</field>
            <field name="description">Mercadería embarcada, en tránsito internacional.</field>
        </record>
        
        <record id="stage_at_port" model="comex.operation.stage">
            <field name="name">En Puerto</field>
            <field name="sequence">50</field>
            <field name="color">5</field>
            <field name="description">Arribado a puerto, pendiente de despacho.</field>
        </record>
        
        <record id="stage_customs" model="comex.operation.stage">
            <field name="name">En Aduana</field>
            <field name="sequence">60</field>
            <field name="color">3</field>
            <field name="description">En proceso de despacho aduanero.</field>
        </record>
        
        <record id="stage_released" model="comex.operation.stage">
            <field name="name">Liberado</field>
            <field name="sequence">70</field>
            <field name="color">9</field>
            <field name="description">Despacho liberado, listo para retiro.</field>
        </record>
        
        <record id="stage_in_warehouse" model="comex.operation.stage">
            <field name="name">En Depósito</field>
            <field name="sequence">80</field>
            <field name="color">8</field>
            <field name="description">Mercadería en depósito fiscal o transitorio.</field>
        </record>
        
        <record id="stage_received" model="comex.operation.stage">
            <field name="name">Recibido</field>
            <field name="sequence">90</field>
            <field name="color">10</field>
            <field name="description">Mercadería recibida en almacén propio.</field>
        </record>
        
        <record id="stage_closed" model="comex.operation.stage">
            <field name="name">Cerrado</field>
            <field name="sequence">100</field>
            <field name="is_closed">True</field>
            <field name="fold">True</field>
            <field name="color">10</field>
            <field name="description">Operación finalizada y documentación completa.</field>
        </record>
        
        <record id="stage_cancelled" model="comex.operation.stage">
            <field name="name">Cancelado</field>
            <field name="sequence">200</field>
            <field name="is_cancelled">True</field>
            <field name="fold">True</field>
            <field name="color">1</field>
            <field name="description">Operación cancelada.</field>
        </record>
        
    </data>
</odoo>
```

### 2.4 Vista de Configuración de Etapas

```xml
<!-- views/comex_operation_stage_views.xml -->
<odoo>
    
    <!-- VISTA TREE -->
    <record id="comex_operation_stage_view_tree" model="ir.ui.view">
        <field name="name">comex.operation.stage.view.tree</field>
        <field name="model">comex.operation.stage</field>
        <field name="arch" type="xml">
            <tree editable="bottom">
                <field name="sequence" widget="handle"/>
                <field name="name"/>
                <field name="operation_type"/>
                <field name="is_initial"/>
                <field name="is_closed"/>
                <field name="is_cancelled"/>
                <field name="fold"/>
                <field name="operation_count"/>
                <field name="company_id" groups="base.group_multi_company"/>
            </tree>
        </field>
    </record>
    
    <!-- VISTA FORM -->
    <record id="comex_operation_stage_view_form" model="ir.ui.view">
        <field name="name">comex.operation.stage.view.form</field>
        <field name="model">comex.operation.stage</field>
        <field name="arch" type="xml">
            <form string="Etapa COMEX">
                <sheet>
                    <div class="oe_title">
                        <h1>
                            <field name="name" placeholder="Nombre de la etapa..."/>
                        </h1>
                    </div>
                    <group>
                        <group name="left">
                            <field name="sequence"/>
                            <field name="operation_type"/>
                            <field name="company_id" groups="base.group_multi_company"/>
                        </group>
                        <group name="right">
                            <field name="is_initial"/>
                            <field name="is_closed"/>
                            <field name="is_cancelled"/>
                            <field name="fold"/>
                            <field name="color" widget="color_picker"/>
                        </group>
                    </group>
                    <group string="Automatizaciones">
                        <field name="mail_template_id"/>
                    </group>
                    <group string="Descripción">
                        <field name="description" nolabel="1"/>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    
    <!-- ACCIÓN -->
    <record id="comex_operation_stage_action" model="ir.actions.act_window">
        <field name="name">Etapas COMEX</field>
        <field name="res_model">comex.operation.stage</field>
        <field name="view_mode">tree,form</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                Crear etapas para el flujo de operaciones COMEX
            </p>
            <p>
                Las etapas permiten personalizar el flujo de trabajo según 
                las necesidades de su empresa. Puede agregar, quitar o 
                reordenar etapas sin necesidad de modificar código.
            </p>
        </field>
    </record>
    
    <!-- MENÚ -->
    <menuitem id="menu_comex_stage_config"
        name="Etapas de Operación"
        parent="menu_comex_config"
        action="comex_operation_stage_action"
        sequence="10"/>
    
</odoo>
```

---

## 3. DIAGRAMA ACTUALIZADO: FLUJO CON ETAPAS DINÁMICAS

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    FLUJO CON ETAPAS CONFIGURABLES                            │
└──────────────────────────────────────────────────────────────────────────────┘

                         ETAPAS ESTÁNDAR (configurables)
                         ═══════════════════════════════

    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
    │Borrador  │────▶│Confirmado│────▶│Coordinac.│────▶│En Viaje  │
    │  (10)    │     │   (20)   │     │   (30)   │     │   (40)   │
    └──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                              │
    ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────▼────┐
    │ Cerrado  │◀────│ Recibido │◀────│ Liberado │◀────│En Puerto │
    │  (100)   │     │   (90)   │     │   (70)   │     │   (50)   │
    └──────────┘     └──────────┘     └──────────┘     └──────────┘
                                            ▲               │
                                            │         ┌─────▼─────┐
                                            └─────────│ En Aduana │
                                                      │   (60)    │
                                                      └───────────┘

    PERSONALIZACIÓN POR EL ADMINISTRADOR:
    ─────────────────────────────────────
    
    Ejemplo: Agregar etapa "Inspección Calidad" entre Recibido y Cerrado:
    
    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │ Recibido │────▶│Inspección│────▶│ Cerrado  │
    │   (90)   │     │ Calidad  │     │  (100)   │
    └──────────┘     │   (95)   │     └──────────┘
                     └──────────┘
                     
    ✓ Sin modificar código
    ✓ Solo desde interfaz de administración
    ✓ Configurar secuencia, color, comportamiento
```

---

## 4. RESUMEN DE CAMBIOS AL DISEÑO ORIGINAL

| Aspecto | Diseño Original | Diseño Actualizado |
|---------|-----------------|-------------------|
| **Estados** | Campo Selection fijo (11 opciones) | Modelo `comex.operation.stage` configurable |
| **ETA/ETD** | Campos propios independientes | Sincronizados con `purchase.order.date_planned` y `stock.picking.scheduled_date` |
| **Fecha arribo real** | Campo manual | Computado desde `stock.picking.date_done` |
| **Alertas de atraso** | No incluido | Campo `is_late` y `days_delay` computados |
| **Flujo de trabajo** | Fijo en código | Configurable por administrador |
| **Acciones automáticas** | Métodos action_* | Configurables por etapa (email, etc.) |

---

**Documento preparado por**: GitHub Copilot  
**Fecha**: 16 de Diciembre de 2025
