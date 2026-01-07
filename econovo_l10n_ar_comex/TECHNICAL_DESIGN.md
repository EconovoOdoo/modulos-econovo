# DISEÑO TÉCNICO: Módulo COMEX para Argentina - Odoo 17

**Autor**: Jose D. Leonett  
**Fecha de Análisis**: 7 de Enero de 2026  
**Versión**: 1.3 (Trazabilidad Stock + Integración Compras/Ventas)  
**Licencia**: AGPL-3

---

## 1. RESUMEN EJECUTIVO

Este documento presenta el análisis técnico completo para el desarrollo de un módulo de **Comercio Exterior (COMEX)** adaptado a la legislación argentina vigente para Odoo 17, siguiendo los principios de OCA y sin impacto a la funcionalidad nativa de Odoo.

### 1.1 Objetivos Principales

- Gestionar operaciones de importación/exportación según normativa argentina (ARCA, BCRA)
- Integrar armoniosamente con módulos nativos de Odoo (purchase, sale, stock, account)
- Reutilizar patrones de diseño probados de OCA (purchase_container, intrastat_product, product_harmonized_system)
- Soportar trazabilidad documental completa del ciclo COMEX
- **Sincronización bidireccional** de fechas ETA/ETD con purchase.order y stock.picking
- **Estados dinámicos** configurables por el administrador (patrón CRM/Project)

---

## 2. ANÁLISIS DE LEGISLACIÓN ARGENTINA VIGENTE

### 2.1 Marco Regulatorio Principal

#### 2.1.1 ARCA (Agencia de Recaudación y Control Aduanero)
*Anteriormente AFIP - Reestructurado en 2024/2025*

| Concepto | Descripción | Impacto en Sistema |
|----------|-------------|-------------------|
| **Sistema Malvina** | Sistema Informático Aduanero | Integración para despachos |
| **CIVUCE** | Central de Información VUCE | Consulta certificados |
| **Posición Arancelaria (NCM)** | Nomenclatura Común del Mercosur (8 dígitos base SH) | Campo obligatorio |
| **Despacho de Importación** | Documento oficial de nacionalización | Tracking documental |

#### 2.1.2 BCRA - Régimen de Cambios

| Normativa | Descripción | Estado 2025 |
|-----------|-------------|-------------|
| **MULC** | Mercado Único y Libre de Cambios | Acceso a divisas regulado |
| **SIRA/SIRASE** | Sistema de Importaciones de la República Argentina | Discontinuado/Simplificado |
| **Plazo de Pago** | Restricciones temporales para acceso a divisas | Variable según NCM |
| **Comunicación "A"** | Normativas BCRA aplicables | Consultar vigentes |

### 2.2 Flujo de Operación de Importación Argentina

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLUJO DE IMPORTACIÓN ARGENTINA                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. ORDEN DE COMPRA          2. EMBARQUE               3. TRÁNSITO          │
│  ┌─────────────────┐        ┌─────────────────┐       ┌─────────────────┐   │
│  │ • Proveedor     │───────▶│ • Bill of Lading│──────▶│ • ETD           │   │
│  │ • Incoterm      │        │ • Contenedor    │       │ • ETA           │   │
│  │ • FOB/CIF/etc   │        │ • Agente Carga  │       │ • Naviera       │   │
│  │ • NCM (HS Code) │        │ • Puerto Origen │       │ • Puerto Destino│   │
│  └─────────────────┘        └─────────────────┘       └─────────────────┘   │
│           │                          │                         │            │
│           ▼                          ▼                         ▼            │
│  4. DESPACHO ADUANERO       5. NACIONALIZACIÓN         6. PAGO/MULC        │
│  ┌─────────────────┐        ┌─────────────────┐       ┌─────────────────┐   │
│  │ • Despachante   │───────▶│ • Nro. Despacho │──────▶│ • Banco Nominado│   │
│  │ • Aforo/Canal   │        │ • Derechos Imp. │       │ • Fecha Acceso  │   │
│  │ • Documentación │        │ • IVA Adicional │       │ • Estado MULC   │   │
│  │ • Certificados  │        │ • Estadística   │       │ • Giro Divisas  │   │
│  └─────────────────┘        └─────────────────┘       └─────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. INTEGRACIÓN CON FECHAS NATIVAS DE ODOO

### 3.1 Campos de Fecha Existentes en Odoo Nativo

| Módulo | Modelo | Campo | Descripción |
|--------|--------|-------|-------------|
| **purchase** | `purchase.order` | `date_planned` | Fecha esperada de llegada (ETA) |
| **purchase** | `purchase.order.line` | `date_planned` | Fecha esperada por línea |
| **stock** | `stock.picking` | `scheduled_date` | Fecha programada de la operación |
| **stock** | `stock.picking` | `date_deadline` | Fecha límite prometida al cliente |
| **stock** | `stock.picking` | `date_done` | Fecha real de transferencia |
| **stock** | `stock.move` | `date` | Fecha programada del movimiento |
| **stock** | `stock.move` | `date_deadline` | Fecha límite del movimiento |

### 3.2 Sincronización Bidireccional

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
   → Al ingresar date_eta: Actualiza purchase.order.date_planned y stock.picking.scheduled_date

2. USUARIO MODIFICA DESDE COMPRA:
   → Al modificar date_planned: Actualiza comex.operation.date_eta

3. ARRIBO REAL:
   → Al validar stock.picking: Se registra date_done → Actualiza comex.operation.date_arrival
```

---

## 4. ANÁLISIS DE MÓDULOS OCA REUTILIZABLES

### 4.1 Módulo Base: `purchase_container` (OCA/purchase-workflow)

**Versión**: 18.0.1.1.0 | **Estado**: Maduro, mantenido activamente

| Campo OCA | Tipo | Descripción | Uso en COMEX AR |
|-----------|------|-------------|-----------------|
| `code` | Char | Referencia contenedor | ✅ Directo |
| `bill_of_lading_ref` | Char | Número B/L | ✅ Directo |
| `shipping_agent_id` | Many2one(res.partner) | Agente de carga | ✅ Directo |
| `date_eta` / `date_etd` | Date | Fechas estimadas | ✅ Directo |
| `displayed_incoterm_id` | Many2one(account.incoterms) | Incoterm | ✅ Directo |

### 4.2 Módulo: `product_harmonized_system` (OCA/intrastat-extrastat)

**Versión**: 18.0.1.0.0 | **Aplicabilidad**: Gestión de códigos HS (NCM en Argentina)

| Campo | Tipo | Descripción | Uso en COMEX AR |
|-------|------|-------------|-----------------|
| `hs_code` | Char(6) | Código Sistema Armonizado | Base para NCM |
| `local_code` | Char | Código nacional (8 dígitos para NCM) | ✅ NCM Mercosur |
| `origin_country_id` | Many2one(res.country) | País de origen | ✅ Obligatorio |

---

## 5. DISEÑO DE LA SOLUCIÓN

### 5.1 Arquitectura de Módulos

```
econovo_l10n_ar_comex/
├── __init__.py
├── __manifest__.py
├── controllers/
│   └── __init__.py
├── data/
│   ├── comex_operation_stage_data.xml   # Etapas dinámicas
│   ├── comex_data.xml                   # Datos base
│   └── mulc_bank_data.xml               # Bancos autorizados MULC
├── models/
│   ├── __init__.py
│   ├── comex_operation.py               # Modelo principal operación
│   ├── comex_operation_stage.py         # Etapas configurables
│   ├── comex_shipment.py                # Embarques/Contenedores
│   ├── comex_customs_clearance.py       # Despachos aduaneros
│   ├── comex_mulc.py                    # Gestión MULC/Pagos
│   ├── hs_code.py                       # Extensión NCM Argentina
│   ├── res_partner.py                   # Extensión partners
│   ├── purchase_order.py                # Extensión purchase.order
│   ├── stock_picking.py                 # Extensión stock.picking
│   └── sale_order.py                    # Extensión sale.order
├── security/
│   ├── ir.model.access.csv
│   ├── comex_groups.xml
│   └── comex_security.xml
├── views/
│   ├── comex_operation_views.xml
│   ├── comex_operation_stage_views.xml
│   ├── comex_shipment_views.xml
│   ├── comex_customs_clearance_views.xml
│   ├── comex_mulc_views.xml
│   ├── res_partner_views.xml
│   ├── purchase_order_views.xml
│   ├── comex_menus.xml
│   └── res_config_settings_views.xml
├── wizard/
│   ├── __init__.py
│   ├── comex_import_wizard.py
│   └── comex_import_wizard_views.xml
└── README.md
```

### 5.2 Modelos de Datos

#### 5.2.1 Modelo: `comex.operation.stage` (Estados Dinámicos)

Siguiendo el patrón de `crm.stage` y `project.task.type`:

```python
class ComexOperationStage(models.Model):
    _name = 'comex.operation.stage'
    _description = 'Etapa de Operación COMEX'
    _order = 'sequence, id'
    
    name = fields.Char(string="Nombre de Etapa", required=True, translate=True)
    sequence = fields.Integer(string="Secuencia", default=10)
    description = fields.Text(string="Descripción", translate=True)
    
    # === COMPORTAMIENTO ===
    fold = fields.Boolean(string="Plegado en Kanban")
    is_initial = fields.Boolean(string="Es Etapa Inicial")
    is_closed = fields.Boolean(string="Es Etapa de Cierre")
    is_cancelled = fields.Boolean(string="Es Etapa de Cancelación")
    color = fields.Integer(string="Color")
    
    # === AUTOMATIZACIONES ===
    mail_template_id = fields.Many2one(
        'mail.template', string="Plantilla de Email",
        domain="[('model', '=', 'comex.operation')]"
    )
    
    # === RESTRICCIONES ===
    operation_type = fields.Selection([
        ('all', 'Todas'),
        ('import', 'Solo Importaciones'),
        ('export', 'Solo Exportaciones'),
    ], string="Tipo de Operación", default='all')
    
    company_id = fields.Many2one('res.company', string="Compañía",
        default=lambda self: self.env.company)
    active = fields.Boolean(string="Activo", default=True)
    operation_count = fields.Integer(compute='_compute_operation_count')
```

#### 5.2.2 Modelo Principal: `comex.operation`

```python
class ComexOperation(models.Model):
    _name = 'comex.operation'
    _description = 'Operación de Comercio Exterior'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'
    
    # === IDENTIFICACIÓN ===
    name = fields.Char(string="Número Operación", required=True, copy=False,
        readonly=True, default=lambda self: _('New'))
    operation_type = fields.Selection([
        ('import', 'Importación'),
        ('export', 'Exportación'),
    ], string="Tipo Operación", required=True, default='import', tracking=True)
    company_id = fields.Many2one('res.company', string="Compañía",
        required=True, default=lambda self: self.env.company)
    
    # === ETAPA DINÁMICA (reemplaza campo state fijo) ===
    stage_id = fields.Many2one(
        'comex.operation.stage', string="Etapa", tracking=True, copy=False,
        group_expand='_read_group_stage_ids',
        domain="['|', ('operation_type', '=', 'all'), ('operation_type', '=', operation_type)]",
        default=lambda self: self._get_default_stage()
    )
    is_closed = fields.Boolean(related='stage_id.is_closed', store=True)
    is_cancelled = fields.Boolean(related='stage_id.is_cancelled', store=True)
    kanban_state = fields.Selection([
        ('normal', 'Gris'), ('done', 'Verde'), ('blocked', 'Rojo'),
    ], string="Estado Kanban", default='normal', copy=False)
    color = fields.Integer(related='stage_id.color')
    
    # === PROVEEDOR/CLIENTE ===
    partner_id = fields.Many2one('res.partner', string="Proveedor/Cliente",
        required=True, tracking=True)
    
    # === DOCUMENTOS COMERCIALES ===
    purchase_order_ids = fields.Many2many('purchase.order', string="Órdenes de Compra")
    sale_order_ids = fields.Many2many('sale.order', string="Órdenes de Venta")
    invoice_ids = fields.Many2many('account.move', string="Facturas Relacionadas")
    
    # === INCOTERM Y VALORES ===
    incoterm_id = fields.Many2one('account.incoterms', string="Incoterm",
        required=True, tracking=True)
    incoterm_location = fields.Char(string="Lugar Incoterm")
    currency_id = fields.Many2one('res.currency', string="Moneda", required=True,
        default=lambda self: self.env.ref('base.USD'))
    amount_fob = fields.Monetary(string="Valor FOB", currency_field='currency_id', tracking=True)
    amount_freight = fields.Monetary(string="Flete", currency_field='currency_id')
    amount_insurance = fields.Monetary(string="Seguro", currency_field='currency_id')
    amount_cif = fields.Monetary(string="Valor CIF", compute='_compute_amount_cif', store=True)
    
    # === FECHAS - INTEGRADAS CON ODOO NATIVO ===
    date_order = fields.Date(string="Fecha Orden", default=fields.Date.context_today)
    date_etd = fields.Date(string="ETD (Fecha Embarque)", tracking=True)
    date_eta = fields.Date(string="ETA (Fecha Llegada)", tracking=True)
    date_arrival = fields.Date(string="Fecha Arribo Real", compute='_compute_date_arrival', store=True)
    date_customs_release = fields.Date(string="Fecha Liberación Aduana", tracking=True)
    date_closed = fields.Date(string="Fecha de Cierre", tracking=True, copy=False)
    
    # === ALERTAS DE ATRASO ===
    is_late = fields.Boolean(string="Atrasado", compute='_compute_is_late', store=True)
    days_delay = fields.Integer(string="Días de Atraso", compute='_compute_is_late', store=True)
    
    # === EMBARQUE ===
    shipment_ids = fields.One2many('comex.shipment', 'operation_id', string="Embarques")
    shipment_count = fields.Integer(compute='_compute_shipment_count')
    
    # === STOCK.PICKING (para sincronización) ===
    picking_ids = fields.One2many('stock.picking', 'comex_operation_id', string="Recepciones/Entregas")
    picking_count = fields.Integer(compute='_compute_picking_count')
    
    # === AGENTES ===
    freight_agent_id = fields.Many2one('res.partner', string="Agente de Carga",
        domain="[('is_freight_agent', '=', True)]", tracking=True)
    customs_agent_id = fields.Many2one('res.partner', string="Despachante de Aduana",
        domain="[('is_customs_agent', '=', True)]", tracking=True)
    
    # === DESPACHO ADUANERO ===
    customs_clearance_ids = fields.One2many('comex.customs.clearance', 'operation_id')
    customs_clearance_number = fields.Char(string="Nro. Despacho Principal", tracking=True)
    
    # === MULC / PAGOS ===
    mulc_ids = fields.One2many('comex.mulc', 'operation_id', string="Operaciones MULC")
    nominated_bank_id = fields.Many2one('res.partner', string="Banco Nominado",
        domain="[('is_bank', '=', True)]", tracking=True)
    payment_state = fields.Selection([
        ('pending', 'Pendiente'), ('partial', 'Parcial'),
        ('mulc_pending', 'Pendiente MULC'), ('mulc_approved', 'MULC Aprobado'),
        ('paid', 'Pagado'),
    ], string="Estado Pago", default='pending', tracking=True)
    
    notes = fields.Html(string="Notas Internas")
    
    # === COMPUTE METHODS ===
    @api.depends('amount_fob', 'amount_freight', 'amount_insurance')
    def _compute_amount_cif(self):
        for record in self:
            record.amount_cif = record.amount_fob + record.amount_freight + record.amount_insurance
    
    @api.depends('date_eta', 'stage_id.is_closed', 'stage_id.is_cancelled')
    def _compute_is_late(self):
        today = fields.Date.today()
        for record in self:
            if record.date_eta and not record.is_closed and not record.is_cancelled:
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
    
    # === SINCRONIZACIÓN DE FECHAS ===
    def write(self, vals):
        res = super().write(vals)
        if 'date_eta' in vals:
            self._sync_dates_to_purchase_stock()
        if 'stage_id' in vals:
            self._on_stage_change()
        return res
    
    def _sync_dates_to_purchase_stock(self):
        """Sincroniza date_eta con purchase.order y stock.picking"""
        for record in self:
            if not record.date_eta:
                continue
            eta_datetime = fields.Datetime.to_datetime(record.date_eta)
            if record.purchase_order_ids:
                record.purchase_order_ids.write({'date_planned': eta_datetime})
                record.purchase_order_ids.order_line.write({'date_planned': eta_datetime})
            if record.picking_ids:
                pending = record.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
                pending.write({'scheduled_date': eta_datetime})
    
    def _on_stage_change(self):
        """Acciones automáticas al cambiar de etapa"""
        for record in self:
            stage = record.stage_id
            if stage.mail_template_id:
                stage.mail_template_id.send_mail(record.id, force_send=True)
            if stage.is_closed and not record.date_closed:
                record.date_closed = fields.Date.today()
    
    @api.model
    def _get_default_stage(self):
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
        search_domain = ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)]
        if operation_type:
            search_domain = expression.AND([search_domain,
                ['|', ('operation_type', '=', 'all'), ('operation_type', '=', operation_type)]])
        return stages.search(search_domain, order=order)
```

#### 5.2.3 Modelo: `comex.shipment` (Embarques)

```python
class ComexShipment(models.Model):
    _name = 'comex.shipment'
    _description = 'Embarque COMEX'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_etd desc'
    
    name = fields.Char(string="Referencia", required=True)
    operation_id = fields.Many2one('comex.operation', required=True, ondelete='cascade')
    
    # === BILL OF LADING ===
    bill_of_lading = fields.Char(string="Bill of Lading (B/L)", tracking=True)
    bl_type = fields.Selection([
        ('ocean', 'Marítimo (Ocean B/L)'), ('air', 'Aéreo (AWB)'),
        ('road', 'Terrestre (CMR/CRT)'), ('multimodal', 'Multimodal'),
    ], string="Tipo B/L", default='ocean')
    
    # === CONTENEDOR ===
    container_number = fields.Char(string="Nro. Contenedor")
    container_type_id = fields.Many2one('comex.container.type', string="Tipo Contenedor")
    seal_number = fields.Char(string="Nro. Precinto")
    
    # === TRANSPORTE ===
    carrier_id = fields.Many2one('res.partner', string="Transportista/Naviera",
        domain="[('is_carrier', '=', True)]")
    vessel_name = fields.Char(string="Nombre Buque/Vuelo")
    voyage_number = fields.Char(string="Nro. Viaje")
    
    # === PUERTOS ===
    port_loading_id = fields.Many2one('comex.port', string="Puerto Carga")
    port_discharge_id = fields.Many2one('comex.port', string="Puerto Descarga")
    
    # === FECHAS ===
    date_etd = fields.Date(string="ETD", tracking=True)
    date_atd = fields.Date(string="ATD", tracking=True)
    date_eta = fields.Date(string="ETA", tracking=True)
    date_ata = fields.Date(string="ATA", tracking=True)
    transit_days = fields.Integer(compute='_compute_transit_days', store=True)
    
    # === PESOS Y MEDIDAS ===
    weight_gross = fields.Float(string="Peso Bruto (Kg)")
    weight_net = fields.Float(string="Peso Neto (Kg)")
    volume = fields.Float(string="Volumen (M³)")
    packages_qty = fields.Integer(string="Cantidad Bultos")
    packages_type = fields.Char(string="Tipo Bultos")
    
    # === ESTADO ===
    state = fields.Selection([
        ('pending', 'Pendiente Embarque'), ('loaded', 'Embarcado'),
        ('in_transit', 'En Tránsito'), ('arrived', 'Arribado'), ('delivered', 'Entregado'),
    ], string="Estado", default='pending', tracking=True)
```

#### 5.2.4 Modelo: `comex.customs.clearance` (Despacho Aduanero)

```python
class ComexCustomsClearance(models.Model):
    _name = 'comex.customs.clearance'
    _description = 'Despacho Aduanero'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string="Nro. Despacho", required=True, tracking=True)
    operation_id = fields.Many2one('comex.operation', required=True, ondelete='cascade')
    
    # === TIPO Y RÉGIMEN ===
    clearance_type = fields.Selection([
        ('import', 'Importación Definitiva'), ('import_temp', 'Importación Temporal'),
        ('export', 'Exportación Definitiva'), ('export_temp', 'Exportación Temporal'),
        ('transit', 'Tránsito'),
    ], string="Tipo Despacho", required=True)
    customs_regime = fields.Selection([
        ('general', 'Régimen General'), ('simplified', 'Régimen Simplificado'),
        ('courier', 'Courier/PSP'),
    ], string="Régimen", default='general')
    customs_office_id = fields.Many2one('comex.customs.office', string="Aduana")
    
    # === FECHAS ===
    date_register = fields.Date(string="Fecha Registro")
    date_release = fields.Date(string="Fecha Liberación", tracking=True)
    
    # === CANAL ===
    channel = fields.Selection([
        ('green', 'Verde'), ('orange', 'Naranja'),
        ('red', 'Rojo'), ('purple', 'Violeta'),
    ], string="Canal", tracking=True)
    
    # === TRIBUTOS ===
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.ref('base.ARS'))
    amount_duties = fields.Monetary(string="Derechos Importación")
    amount_statistics = fields.Monetary(string="Tasa Estadística")
    amount_vat = fields.Monetary(string="IVA")
    amount_vat_additional = fields.Monetary(string="IVA Adicional")
    amount_profits = fields.Monetary(string="Percepción Ganancias")
    amount_gross_income = fields.Monetary(string="Percepción IIBB")
    amount_total = fields.Monetary(string="Total Tributos", compute='_compute_amount_total', store=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'), ('registered', 'Oficializado'),
        ('verification', 'En Verificación'), ('released', 'Liberado'), ('cancelled', 'Anulado'),
    ], string="Estado", default='draft', tracking=True)
```

#### 5.2.5 Modelo: `comex.mulc` (Operaciones MULC)

```python
class ComexMULC(models.Model):
    _name = 'comex.mulc'
    _description = 'Operación MULC - Acceso a Divisas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_request desc'
    
    name = fields.Char(string="Referencia MULC", required=True, copy=False,
        default=lambda self: _('New'))
    operation_id = fields.Many2one('comex.operation', required=True, ondelete='cascade')
    bank_id = fields.Many2one('res.partner', string="Banco Operador",
        domain="[('is_bank', '=', True)]", required=True, tracking=True)
    
    # === MONTOS ===
    currency_id = fields.Many2one('res.currency', required=True,
        default=lambda self: self.env.ref('base.USD'))
    amount_requested = fields.Monetary(string="Monto Solicitado", required=True, tracking=True)
    amount_approved = fields.Monetary(string="Monto Aprobado", tracking=True)
    
    # === TIPO DE CAMBIO ===
    rate_type = fields.Selection([
        ('official', 'Oficial'), ('mep', 'MEP'), ('ccl', 'CCL'),
    ], string="Tipo Cambio", default='official')
    exchange_rate = fields.Float(string="Tipo de Cambio", digits=(16, 4))
    
    # === FECHAS ===
    date_request = fields.Date(string="Fecha Solicitud", default=fields.Date.context_today)
    date_due = fields.Date(string="Fecha Vencimiento Acceso")
    date_approval = fields.Date(string="Fecha Aprobación", tracking=True)
    date_execution = fields.Date(string="Fecha Ejecución", tracking=True)
    
    bcra_communication = fields.Char(string="Comunicación BCRA")
    state = fields.Selection([
        ('draft', 'Borrador'), ('requested', 'Solicitado'), ('approved', 'Aprobado'),
        ('executed', 'Ejecutado'), ('rejected', 'Rechazado'), ('cancelled', 'Cancelado'),
    ], string="Estado", default='draft', tracking=True)
    notes = fields.Text(string="Observaciones")
```

### 5.3 Extensión de Modelos Nativos

#### 5.3.1 Extensión `stock.picking`

```python
class StockPickingComex(models.Model):
    _inherit = 'stock.picking'
    
    comex_operation_id = fields.Many2one('comex.operation', string="Operación COMEX",
        tracking=True, copy=False)
    comex_customs_number = fields.Char(string="Nro. Despacho",
        related='comex_operation_id.customs_clearance_number', store=True)
    
    def button_validate(self):
        """Extiende validación para actualizar operación COMEX"""
        res = super().button_validate()
        for picking in self.filtered(lambda p: p.comex_operation_id and p.state == 'done'):
            operation = picking.comex_operation_id
            # Si es la última recepción, buscar etapa "Recibido"
            pending = operation.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel') and p.id != picking.id)
            if not pending:
                received_stage = self.env['comex.operation.stage'].search([
                    ('name', 'ilike', 'Recibido'), ('is_closed', '=', False)
                ], limit=1)
                if received_stage:
                    operation.write({'stage_id': received_stage.id})
        return res
```

#### 5.3.2 Extensión `purchase.order`

```python
class PurchaseOrderComex(models.Model):
    _inherit = 'purchase.order'
    
    comex_operation_id = fields.Many2one('comex.operation', string="Operación COMEX", tracking=True)
    is_comex = fields.Boolean(compute='_compute_is_comex', store=True)
    proforma_number = fields.Char(string="Nro. Proforma")
    
    @api.depends('partner_id.country_id', 'company_id.country_id')
    def _compute_is_comex(self):
        for order in self:
            order.is_comex = (order.partner_id.country_id and
                order.partner_id.country_id != order.company_id.country_id)
    
    def write(self, vals):
        res = super().write(vals)
        if 'date_planned' in vals:
            for order in self.filtered('comex_operation_id'):
                if order.date_planned:
                    order.comex_operation_id.write({'date_eta': order.date_planned.date()})
        return res
    
    def button_confirm(self):
        res = super().button_confirm()
        for order in self.filtered('comex_operation_id'):
            pickings = order.picking_ids.filtered(lambda p: not p.comex_operation_id)
            pickings.write({'comex_operation_id': order.comex_operation_id.id})
        return res
```

#### 5.3.3 Extensión `res.partner`

```python
class ResPartnerComex(models.Model):
    _inherit = 'res.partner'
    
    is_freight_agent = fields.Boolean(string="Agente de Carga")
    is_customs_agent = fields.Boolean(string="Despachante de Aduana")
    is_carrier = fields.Boolean(string="Transportista/Naviera")
    is_authorized_bank = fields.Boolean(string="Banco Autorizado MULC")
    customs_license = fields.Char(string="Matrícula Despachante")
    default_incoterm_id = fields.Many2one('account.incoterms', string="Incoterm por Defecto")
    comex_operation_ids = fields.One2many('comex.operation', 'partner_id')
    comex_operation_count = fields.Integer(compute='_compute_comex_operation_count')
```

---

## 6. DATOS INICIALES DE ETAPAS

```xml
<!-- data/comex_operation_stage_data.xml -->
<odoo>
    <data noupdate="1">
        <record id="stage_draft" model="comex.operation.stage">
            <field name="name">Borrador</field>
            <field name="sequence">10</field>
            <field name="is_initial">True</field>
            <field name="color">0</field>
        </record>
        <record id="stage_confirmed" model="comex.operation.stage">
            <field name="name">Confirmado</field>
            <field name="sequence">20</field>
            <field name="color">1</field>
        </record>
        <record id="stage_coordinating" model="comex.operation.stage">
            <field name="name">En Coordinación</field>
            <field name="sequence">30</field>
            <field name="color">2</field>
        </record>
        <record id="stage_in_transit" model="comex.operation.stage">
            <field name="name">En Viaje</field>
            <field name="sequence">40</field>
            <field name="color">4</field>
        </record>
        <record id="stage_at_port" model="comex.operation.stage">
            <field name="name">En Puerto</field>
            <field name="sequence">50</field>
            <field name="color">5</field>
        </record>
        <record id="stage_customs" model="comex.operation.stage">
            <field name="name">En Aduana</field>
            <field name="sequence">60</field>
            <field name="color">3</field>
        </record>
        <record id="stage_released" model="comex.operation.stage">
            <field name="name">Liberado</field>
            <field name="sequence">70</field>
            <field name="color">9</field>
        </record>
        <record id="stage_in_warehouse" model="comex.operation.stage">
            <field name="name">En Depósito</field>
            <field name="sequence">80</field>
            <field name="color">8</field>
        </record>
        <record id="stage_received" model="comex.operation.stage">
            <field name="name">Recibido</field>
            <field name="sequence">90</field>
            <field name="color">10</field>
        </record>
        <record id="stage_closed" model="comex.operation.stage">
            <field name="name">Cerrado</field>
            <field name="sequence">100</field>
            <field name="is_closed">True</field>
            <field name="fold">True</field>
            <field name="color">10</field>
        </record>
        <record id="stage_cancelled" model="comex.operation.stage">
            <field name="name">Cancelado</field>
            <field name="sequence">200</field>
            <field name="is_cancelled">True</field>
            <field name="fold">True</field>
            <field name="color">1</field>
        </record>
    </data>
</odoo>
```

---

## 7. FLUJO CON ETAPAS DINÁMICAS

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

    PERSONALIZACIÓN:
    ─────────────────
    ✓ Sin modificar código
    ✓ Solo desde interfaz de administración
    ✓ Configurar secuencia, color, comportamiento
```

---

## 8. MAPEO DE CAMPOS SOLICITADOS

| Campo Solicitado | Modelo | Nombre Campo | Tipo |
|------------------|--------|--------------|------|
| **BL** | comex.shipment | `bill_of_lading` | Char |
| **Incoterm** | comex.operation | `incoterm_id` | Many2one(account.incoterms) |
| **FOB R** | comex.operation | `amount_fob` | Monetary |
| **ETD** | comex.operation | `date_etd` | Date |
| **ETA** | comex.operation | `date_eta` | Date |
| **Despacho** | comex.customs.clearance | `name` | Char |
| **Agente de carga** | comex.operation | `freight_agent_id` | Many2one(res.partner) |
| **Banco nominado** | comex.operation | `nominated_bank_id` | Many2one(res.partner) |
| **Estado operación** | comex.operation | `stage_id` | Many2one(comex.operation.stage) |
| **MULC** | comex.mulc | (modelo completo) | Model |
| **Estado de pago** | comex.operation | `payment_state` | Selection |

---

## 9. DEPENDENCIAS DE MÓDULOS

```python
'depends': [
    'base',
    'mail',
    'purchase_stock',
    'sale_stock',
    'account',
    'stock',
    'contacts',
],
```

---

## 10. SEGURIDAD Y PERMISOS

### 10.1 Grupos de Usuarios

```xml
<record id="module_category_comex" model="ir.module.category">
    <field name="name">Comercio Exterior</field>
    <field name="sequence">50</field>
</record>

<record id="group_comex_user" model="res.groups">
    <field name="name">Usuario COMEX</field>
    <field name="category_id" ref="module_category_comex"/>
</record>

<record id="group_comex_manager" model="res.groups">
    <field name="name">Administrador COMEX</field>
    <field name="category_id" ref="module_category_comex"/>
    <field name="implied_ids" eval="[(4, ref('group_comex_user'))]"/>
</record>

<record id="group_comex_mulc" model="res.groups">
    <field name="name">Operador MULC</field>
    <field name="category_id" ref="module_category_comex"/>
    <field name="implied_ids" eval="[(4, ref('group_comex_user'))]"/>
</record>
```

### 10.2 Permisos de Acceso (ir.model.access.csv)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_comex_operation_user,comex.operation.user,model_comex_operation,group_comex_user,1,1,1,0
access_comex_operation_manager,comex.operation.manager,model_comex_operation,group_comex_manager,1,1,1,1
access_comex_stage_user,comex.operation.stage.user,model_comex_operation_stage,group_comex_user,1,0,0,0
access_comex_stage_manager,comex.operation.stage.manager,model_comex_operation_stage,group_comex_manager,1,1,1,1
access_comex_shipment_user,comex.shipment.user,model_comex_shipment,group_comex_user,1,1,1,0
access_comex_shipment_manager,comex.shipment.manager,model_comex_shipment,group_comex_manager,1,1,1,1
access_comex_customs_user,comex.customs.user,model_comex_customs_clearance,group_comex_user,1,0,0,0
access_comex_customs_manager,comex.customs.manager,model_comex_customs_clearance,group_comex_manager,1,1,1,1
access_comex_mulc_user,comex.mulc.user,model_comex_mulc,group_comex_mulc,1,1,1,0
access_comex_mulc_manager,comex.mulc.manager,model_comex_mulc,group_comex_manager,1,1,1,1
```

---

## 11. ROADMAP DE DESARROLLO

### Fase 1: MVP (4-6 semanas)
- [x] Análisis y diseño técnico
- [ ] Modelos base: comex.operation, comex.operation.stage, comex.shipment
- [ ] Extensión res.partner, purchase.order, stock.picking
- [ ] Sincronización bidireccional de fechas
- [ ] Vistas básicas CRUD + Kanban
- [ ] Seguridad y permisos

### Fase 2: Despachos y MULC (4 semanas)
- [ ] Modelo comex.customs.clearance
- [ ] Modelo comex.mulc
- [ ] Cálculo de tributos aduaneros
- [ ] Estados de pago

### Fase 3: Integraciones (4 semanas)
- [ ] Integración con stock (recepciones automáticas)
- [ ] Integración con account (facturas, pagos)
- [ ] Integración con product_harmonized_system (NCM)
- [ ] Reportes básicos

### Fase 4: Avanzado (según demanda)
- [ ] Dashboard COMEX
- [ ] Alertas y notificaciones automáticas
- [ ] API para integraciones externas
- [ ] Integración Sistema Malvina (si disponible API)

---

## 12. TRAZABILIDAD DE STOCK Y UBICACIONES COMEX

### 12.1 Estructura de Ubicaciones para Etapas COMEX

Para visualizar el stock de productos importados según la etapa del proceso COMEX, se implementará una jerarquía de ubicaciones nativas de Odoo:

```
📦 Ubicaciones / Locations
│
├── 🏠 WH/Stock (internal)                    ← Stock nacionalizado
│   ├── Almacén Principal
│   ├── Almacén Secundario
│   └── ...
│
└── 📋 COMEX (view)                           ← Ubicación padre COMEX
    │
    ├── 🚢 En Viaje (view)                    ← Padre para tránsitos marítimos/aéreos
    │   ├── Marítimo (transit)
    │   └── Aéreo (transit)
    │
    ├── ⚓ Puerto (view)                       ← Padre para puertos
    │   ├── Buenos Aires (transit)
    │   ├── Rosario (transit)
    │   ├── Bahía Blanca (transit)
    │   └── Mendoza - Paso Los Libertadores (transit)
    │
    ├── 🏭 Zona Franca (view)                  ← Padre para zonas francas
    │   ├── ZF La Plata (transit)
    │   ├── ZF Córdoba (transit)
    │   ├── ZF General Pico (transit)
    │   └── ZF Tucumán (transit)
    │
    └── 🏛️ Depósito Fiscal (view)             ← Padre para depósitos fiscales
        ├── DF EXOLGAN (transit)
        ├── DF Terminal 4 (transit)
        ├── DF Andreani Fiscales (transit)
        ├── DF GEFCO (transit)
        └── DF Interior - Córdoba (transit)
```

**Regla de tipos de ubicación:**
- `view` = Ubicaciones padre (agrupan sub-ubicaciones, no pueden tener stock directamente)
- `transit` = Ubicaciones hoja donde realmente está el stock
- `internal` = Stock nacionalizado en almacén

### 12.2 Visualización en Ficha de Producto

Odoo nativo muestra en la ficha del producto el botón **"On Hand"** que abre `stock.quant`, permitiendo ver el desglose por ubicación:

```
Vista en Producto "Motor Industrial ABC":
┌──────────────────────────────────────────────────────────────────┐
│ Location                            │ On Hand │ Operación COMEX  │
├─────────────────────────────────────┼─────────┼──────────────────┤
│ COMEX/En Viaje/Marítimo             │    5    │ OP/2026/00018    │
│ COMEX/Puerto/Rosario                │    3    │ OP/2026/00015    │
│ COMEX/Depósito Fiscal/DF EXOLGAN    │    8    │ OP/2026/00012    │
│ COMEX/Depósito Fiscal/DF GEFCO      │    4    │ OP/2026/00010    │
│ WH/Stock/Almacén Principal          │   12    │ (nacionalizado)  │
├─────────────────────────────────────┼─────────┼──────────────────┤
│ TOTAL                               │   32    │                  │
└──────────────────────────────────────────────────────────────────┘
```

### 12.3 Integración con Lotes y Números de Serie

La trazabilidad de lotes/series funciona nativamente:
- Cada `stock.move.line` vincula el `lot_id` (número de serie)
- Los quants (`stock.quant`) mantienen la relación producto + ubicación + lote
- Al mover stock entre etapas COMEX, el lote/serie se preserva automáticamente

---

## 13. INTEGRACIÓN CON FLUJO DE COMPRAS/VENTAS

### 13.1 Opciones de Implementación Analizadas

| Aspecto | Opción 1: Ruta Fija | Opción 2: COMEX Controla | Opción 3: Híbrido |
|---------|---------------------|--------------------------|-------------------|
| **Complejidad desarrollo** | Baja | Alta | Media |
| **Flexibilidad ubicaciones** | Baja (fijas en ruta) | Alta (dinámicas) | Alta |
| **Integración nativa** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Control desde COMEX** | Limitado | Total | Total |
| **Pickings pre-creados** | Todos al inicio | Bajo demanda | Mixto |
| **Selección puerto/DF** | No | Sí | Sí |
| **Saltar etapas** | Difícil | Fácil | Fácil |

### 13.2 Implementación Seleccionada: OPCIÓN 3 (Híbrido)

Se implementará un enfoque híbrido que combina la robustez de las rutas nativas con la flexibilidad del control desde la operación COMEX:

**Principios:**
1. La ruta COMEX solo define el **primer paso** (Vendor → COMEX/En Viaje) y el **último** (DF → Stock)
2. Los movimientos intermedios los genera la **Operación COMEX** al cambiar de etapa
3. El usuario selecciona el **puerto/depósito específico** en cada cambio de etapa
4. Máxima flexibilidad con mínima complejidad

### 13.3 Flujo de Importación con Control Híbrido

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      FLUJO HÍBRIDO DE IMPORTACIÓN                               │
└─────────────────────────────────────────────────────────────────────────────────┘

CONFIGURACIÓN:
══════════════
• Ruta "COMEX Importación" con 2 pasos base:
  1. Proveedor → COMEX/En Viaje (automático desde PO)
  2. COMEX/[Última ubicación] → WH/Stock (nacionalización)

• Los movimientos intermedios los genera la Operación COMEX


FLUJO OPERATIVO:
════════════════

PO Confirmada                    Operación COMEX                    Stock Final
─────────────                    ───────────────                    ───────────

┌──────────────┐                ┌───────────────────┐              ┌─────────────┐
│ PO00123      │                │ OP/2026/00015     │              │             │
│ Ruta: COMEX  │───────────────►│ Etapa: Embarcado  │              │             │
└──────────────┘                └───────────────────┘              │             │
       │                                 │                         │             │
       ▼                                 │                         │             │
┌──────────────────┐                     │                         │             │
│ PICKING RECEPCIÓN│                     │                         │             │
│ (Auto-generado)  │                     │                         │             │
│                  │                     │                         │             │
│ Vendor →         │                     │                         │             │
│ COMEX/En Viaje   │ ◄── Validar ────────┤ ETD Confirmado          │             │
└──────────────────┘                     │                         │             │
                                         │                         │             │
                         ┌───────────────┤ Cambio Etapa            │             │
                         │               │ → En Puerto/Buenos Aires│             │
                         ▼               │                         │             │
               ┌──────────────────┐      │                         │             │
               │ PICKING INTERNO  │      │                         │             │
               │ (Generado COMEX) │      │                         │             │
               │                  │      │                         │             │
               │ En Viaje →       │      │                         │             │
               │ Puerto/BsAs      │      │                         │             │
               └──────────────────┘      │                         │             │
                         │               │                         │             │
                         ▼               │ Cambio Etapa            │             │
               ┌──────────────────┐      │ → Dep. Fiscal/EXOLGAN   │             │
               │ PICKING INTERNO  │◄─────┘                         │             │
               │ Puerto/BsAs →    │                                │             │
               │ DF/EXOLGAN       │                                │             │
               └──────────────────┘                                │             │
                         │                                         │             │
                         │ Nacionalización                         │             │
                         │ (Despacho aprobado)                     │             │
                         ▼                                         ▼             │
               ┌──────────────────┐                       ┌─────────────────────┐│
               │ PICKING FINAL    │──────────────────────►│ Stock Nacionalizado ││
               │ (Generado COMEX) │                       │ WH/Stock            ││
               │ DF/EXOLGAN →     │                       │ 50 Laptops ✓        ││
               │ WH/Stock         │                       └─────────────────────┘│
               └──────────────────┘                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 13.4 Caso de Uso: Importación de Equipos Electrónicos

| Campo | Valor |
|-------|-------|
| **Operación COMEX** | OP/2026/00015 |
| **Proveedor** | Shenzhen Electronics Co. |
| **Productos** | 50x Laptop Model X (c/serie), 200x Mouse Wireless |
| **Contenedor** | MSKU-1234567 |
| **Incoterm** | CIF Buenos Aires |
| **Puerto Destino** | Buenos Aires |
| **Depósito Fiscal** | DF EXOLGAN |

**Secuencia de Pickings Generados:**

| Etapa | Picking | Origen | Destino | Trigger |
|-------|---------|--------|---------|---------|
| Embarque | WH/IN/00234 | Partners/Vendors | COMEX/En Viaje/Marítimo | Confirmar PO + Operación COMEX |
| Arribo Puerto | WH/INT/00089 | COMEX/En Viaje/Marítimo | COMEX/Puerto/Buenos Aires | Cambio etapa COMEX |
| Ingreso DF | WH/INT/00090 | COMEX/Puerto/Buenos Aires | COMEX/DF/EXOLGAN | Cambio etapa COMEX |
| Nacionalización | WH/IN/00235 | COMEX/DF/EXOLGAN | WH/Stock | Despacho aprobado |

### 13.5 Flujo de Exportación (Ventas)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      FLUJO DE EXPORTACIÓN (Venta)                               │
└─────────────────────────────────────────────────────────────────────────────────┘

SALE ORDER                       COMEX OPERATION                    PICKINGS
──────────                       ───────────────                    ────────

┌──────────────┐                ┌───────────────────┐
│ SO00456      │                │ OP/2026/00016     │
│ Cliente: USA │───────────────►│ Tipo: Exportación │
│ Incoterm:FOB │                │ Etapa: Preparación│
└──────────────┘                └───────────────────┘
       │                                 │
       ▼                                 │
┌──────────────────┐                     │
│ PICKING DELIVERY │                     │
│ WH/Stock →       │                     │
│ COMEX/Export/    │ ◄── Generado ───────┤
│   Preparación    │                     │
└──────────────────┘                     │
                                         │
                    ┌────────────────────┤ Etapa: En Puerto
                    ▼                    │
          ┌──────────────────┐           │
          │ PICKING INTERNO  │           │
          │ Preparación →    │           │
          │ Puerto/BsAs      │           │
          └──────────────────┘           │
                    │                    │
                    ▼                    │ Etapa: Embarcado
          ┌──────────────────┐           │
          │ PICKING SALIDA   │◄──────────┘
          │ Puerto/BsAs →    │
          │ Customer         │
          └──────────────────┘
```

### 13.6 Modelo de Datos para Control de Ubicaciones

```python
class ComexOperationStage(models.Model):
    _name = 'comex.operation.stage'
    
    # Ubicación padre de tipo 'view' para esta etapa
    parent_location_id = fields.Many2one(
        'stock.location',
        string='Location Category',
        domain="[('usage', '=', 'view')]",
        help='Parent location for this stage (e.g., COMEX/Depósito Fiscal)',
    )


class ComexOperation(models.Model):
    _name = 'comex.operation'
    
    # Ubicación específica donde está la mercadería (hijo de parent_location_id)
    current_location_id = fields.Many2one(
        'stock.location',
        string='Current Location',
        domain="[('usage', '=', 'transit'), "
               "('id', 'child_of', stage_id.parent_location_id)]",
        help='Specific transit location (port, fiscal warehouse, etc.)',
    )
    
    @api.onchange('stage_id')
    def _onchange_stage_id(self):
        """Reset location when stage changes, show only valid children."""
        self.current_location_id = False
        return {
            'domain': {
                'current_location_id': [
                    ('usage', '=', 'transit'),
                    ('id', 'child_of', self.stage_id.parent_location_id.id),
                ]
            }
        }
    
    def _create_stage_transfer_picking(self, origin_location, dest_location):
        """Create internal transfer picking for stage change."""
        # Genera picking interno automático
        ...
```

### 13.7 Configuración de Ruta COMEX

```xml
<!-- Ruta COMEX Importación -->
<record id="route_comex_import" model="stock.route">
    <field name="name">COMEX - Importación Argentina</field>
    <field name="sequence">10</field>
    <field name="product_selectable">True</field>
    <field name="sale_selectable">False</field>
    <field name="purchase_selectable">True</field>
</record>

<!-- Regla: Proveedor → COMEX/En Viaje -->
<record id="rule_comex_receipt" model="stock.rule">
    <field name="name">COMEX: Receipt to Transit</field>
    <field name="route_id" ref="route_comex_import"/>
    <field name="action">pull</field>
    <field name="picking_type_id" ref="stock.picking_type_in"/>
    <field name="location_src_id" ref="stock.stock_location_suppliers"/>
    <field name="location_dest_id" ref="comex_location_in_transit_sea"/>
</record>
```

---

## 14. CONSIDERACIONES FINALES

### 14.1 Compatibilidad
- ✅ Compatible con Odoo 17 CE y EE
- ✅ No modifica comportamiento nativo de Odoo
- ✅ Sigue guías de desarrollo OCA
- ✅ Preparado para localización argentina (l10n_ar)

### 14.2 Extensibilidad
- Etapas configurables sin modificar código
- Ubicaciones COMEX configurables por usuario (puertos, depósitos fiscales, zonas francas)
- Campos adicionales vía herencia
- Integración con otros módulos COMEX de OCA

### 14.3 Mantenimiento
- Código documentado en inglés
- Tests unitarios para flujos críticos
- Versionado semántico

---

**Documento preparado por**: Jose D. Leonett / GitHub Copilot  
**Fecha**: 7 de Enero de 2026  
**Revisión**: 1.3 (Agrega secciones 12-13: Trazabilidad Stock y Integración Compras/Ventas)
