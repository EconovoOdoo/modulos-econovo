# DISEÑO TÉCNICO: Módulo COMEX para Argentina - Odoo 17

**Autor**: Jose D. Leonett  
**Fecha de Análisis**: 16 de Diciembre de 2025  
**Versión**: 1.0  
**Licencia**: AGPL-3

---

## 1. RESUMEN EJECUTIVO

Este documento presenta el análisis técnico completo para el desarrollo de un módulo de **Comercio Exterior (COMEX)** adaptado a la legislación argentina vigente para Odoo 17, siguiendo los principios de OCA y sin impacto a la funcionalidad nativa de Odoo.

### 1.1 Objetivos Principales

- Gestionar operaciones de importación/exportación según normativa argentina (ARCA, BCRA)
- Integrar armoniosamente con módulos nativos de Odoo (purchase, sale, stock, account)
- Reutilizar patrones de diseño probados de OCA (purchase_container, intrastat_product, product_harmonized_system)
- Soportar trazabilidad documental completa del ciclo COMEX

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

## 3. ANÁLISIS DE MÓDULOS OCA REUTILIZABLES

### 3.1 Módulo Base: `purchase_container` (OCA/purchase-workflow)

**Versión**: 18.0.1.1.0  
**Estado**: Maduro, mantenido activamente

#### Campos Reutilizables Directamente

| Campo OCA | Tipo | Descripción | Uso en COMEX AR |
|-----------|------|-------------|-----------------|
| `code` | Char | Referencia contenedor | ✅ Directo |
| `bill_of_lading_ref` | Char | Número B/L | ✅ Directo |
| `shipping_agent_id` | Many2one(res.partner) | Agente de carga | ✅ Directo |
| `type_id` | Many2one(container.type) | Tipo contenedor | ✅ Directo |
| `date_eta` | Date | Estimated Time of Arrival | ✅ Directo |
| `date_etd` | Date | Estimated Time of Departure | ✅ Directo |
| `date_ata` | Date | Actual Time of Arrival | ✅ Directo |
| `date_atd` | Date | Actual Time of Departure | ✅ Directo |
| `displayed_incoterm_id` | Many2one(account.incoterms) | Incoterm | ✅ Directo |
| `state` | Selection | waiting/transit/arrived/locked | ⚠️ Extender |
| `departure_location_id` | Many2one(res.partner) | Puerto origen | ✅ Directo |
| `arrival_location_id` | Many2one(res.partner) | Puerto destino | ✅ Directo |

#### Código de Referencia

```python
# De OCA purchase_container/models/purchase_container.py
class PurchaseContainer(models.Model):
    _name = "purchase.container"
    _description = "Purchase order related container"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    
    bill_of_lading_ref = fields.Char("Bill Of Lading No.", copy=False)
    shipping_agent_id = fields.Many2one(
        comodel_name="res.partner", string="Shipping Agent"
    )
    date_eta = fields.Date(
        string="ETA Date", help="Estimated Time Of Arrival", tracking=True
    )
    date_etd = fields.Date(
        string="ETD Date", help="Estimated Time Of Departure", tracking=True
    )
    displayed_incoterm_id = fields.Many2one(
        "account.incoterms",
        compute="_compute_displayed_incoterm_id",
        inverse="_inverse_displayed_incoterm_id",
        store=True,
        tracking=True,
    )
```

### 3.2 Módulo: `product_harmonized_system` (OCA/intrastat-extrastat)

**Versión**: 18.0.1.0.0  
**Aplicabilidad**: Gestión de códigos HS (NCM en Argentina)

#### Campos Relevantes

| Campo | Tipo | Descripción | Uso en COMEX AR |
|-------|------|-------------|-----------------|
| `hs_code` | Char(6) | Código Sistema Armonizado | Base para NCM |
| `local_code` | Char | Código nacional (8 dígitos para NCM) | ✅ NCM Mercosur |
| `origin_country_id` | Many2one(res.country) | País de origen | ✅ Obligatorio |
| `description` | Char | Descripción HS | ✅ Para despacho |

#### Extensión para Argentina

```python
# Modelo a heredar para NCM argentino
class HSCodeArgentina(models.Model):
    _inherit = "hs.code"
    
    # NCM tiene 8 dígitos (HS 6 dígitos + 2 Mercosur)
    ncm_code = fields.Char(
        string="Código NCM",
        size=8,
        help="Nomenclatura Común del Mercosur (8 dígitos)"
    )
    derecho_importacion = fields.Float(
        string="D.I. %",
        help="Derecho de Importación Extrazona"
    )
    tasa_estadistica = fields.Float(
        string="Tasa Estadística %",
        help="Tasa de Estadística (0.5% general)"
    )
```

### 3.3 Módulo: `purchase_partner_incoterm` (OCA/purchase-workflow)

**Versión**: 18.0.1.0.0  
**Aplicabilidad**: Incoterm por defecto en proveedor

```python
# De OCA - agregar incoterm preferido a proveedor
class ResPartner(models.Model):
    _inherit = "res.partner"
    
    purchase_incoterm_id = fields.Many2one(
        "account.incoterms",
        string="Purchase Incoterm",
        help="Default incoterm for purchases from this partner"
    )
    purchase_incoterm_address_id = fields.Many2one(
        "res.partner",
        string="Incoterm Address",
        help="Default delivery address for incoterm"
    )
```

---

## 4. DISEÑO DE LA SOLUCIÓN

### 4.1 Arquitectura de Módulos

```
l10n_ar_comex/
├── __init__.py
├── __manifest__.py
├── controllers/
│   └── __init__.py
├── data/
│   ├── l10n_ar_comex_data.xml           # Datos base
│   ├── comex_operation_state_data.xml   # Estados operación
│   └── mulc_bank_data.xml               # Bancos autorizados MULC
├── models/
│   ├── __init__.py
│   ├── comex_operation.py               # Modelo principal operación
│   ├── comex_operation_line.py          # Líneas de operación
│   ├── comex_shipment.py                # Embarques/Contenedores
│   ├── comex_customs_clearance.py       # Despachos aduaneros
│   ├── comex_mulc.py                    # Gestión MULC/Pagos
│   ├── hs_code.py                       # Extensión NCM Argentina
│   ├── res_partner.py                   # Extensión partners
│   ├── purchase_order.py                # Extensión purchase.order
│   └── sale_order.py                    # Extensión sale.order
├── report/
│   ├── __init__.py
│   ├── comex_operation_report.xml
│   └── comex_operation_templates.xml
├── security/
│   ├── ir.model.access.csv
│   ├── l10n_ar_comex_groups.xml
│   └── l10n_ar_comex_security.xml
├── static/
│   └── description/
│       ├── icon.png
│       └── index.html
├── views/
│   ├── comex_operation_views.xml
│   ├── comex_shipment_views.xml
│   ├── comex_customs_clearance_views.xml
│   ├── comex_mulc_views.xml
│   ├── hs_code_views.xml
│   ├── res_partner_views.xml
│   ├── purchase_order_views.xml
│   ├── l10n_ar_comex_menus.xml
│   └── res_config_settings_views.xml
├── wizard/
│   ├── __init__.py
│   ├── comex_import_wizard.py
│   └── comex_import_wizard_views.xml
└── README.md
```

### 4.2 Modelos de Datos

#### 4.2.1 Modelo Principal: `comex.operation`

```python
class ComexOperation(models.Model):
    _name = 'comex.operation'
    _description = 'Operación de Comercio Exterior'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'
    
    # === IDENTIFICACIÓN ===
    name = fields.Char(
        string="Número Operación",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    operation_type = fields.Selection([
        ('import', 'Importación'),
        ('export', 'Exportación'),
    ], string="Tipo Operación", required=True, default='import', tracking=True)
    
    company_id = fields.Many2one(
        'res.company',
        string="Compañía",
        required=True,
        default=lambda self: self.env.company
    )
    
    # === PROVEEDOR/CLIENTE ===
    partner_id = fields.Many2one(
        'res.partner',
        string="Proveedor/Cliente",
        required=True,
        tracking=True
    )
    
    # === DOCUMENTOS COMERCIALES ===
    purchase_order_ids = fields.Many2many(
        'purchase.order',
        string="Órdenes de Compra",
        tracking=True
    )
    sale_order_ids = fields.Many2many(
        'sale.order',
        string="Órdenes de Venta",
        tracking=True
    )
    invoice_ids = fields.Many2many(
        'account.move',
        string="Facturas Relacionadas"
    )
    
    # === INCOTERM Y VALORES ===
    incoterm_id = fields.Many2one(
        'account.incoterms',
        string="Incoterm",
        required=True,
        tracking=True,
        help="Término de comercio internacional (ICC 2020)"
    )
    incoterm_location = fields.Char(
        string="Lugar Incoterm",
        help="Puerto/Ciudad donde aplica el Incoterm"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        required=True,
        default=lambda self: self.env.ref('base.USD')
    )
    
    amount_fob = fields.Monetary(
        string="Valor FOB",
        currency_field='currency_id',
        tracking=True,
        help="Free On Board - Valor de la mercadería en puerto de origen"
    )
    amount_freight = fields.Monetary(
        string="Flete",
        currency_field='currency_id',
        help="Costo del flete internacional"
    )
    amount_insurance = fields.Monetary(
        string="Seguro",
        currency_field='currency_id',
        help="Costo del seguro internacional"
    )
    amount_cif = fields.Monetary(
        string="Valor CIF",
        currency_field='currency_id',
        compute='_compute_amount_cif',
        store=True,
        help="Cost, Insurance & Freight - Base imponible para derechos"
    )
    
    # === FECHAS CLAVE ===
    date_order = fields.Date(
        string="Fecha Orden",
        default=fields.Date.context_today,
        tracking=True
    )
    date_etd = fields.Date(
        string="ETD",
        help="Estimated Time of Departure - Fecha estimada de embarque",
        tracking=True
    )
    date_eta = fields.Date(
        string="ETA",
        help="Estimated Time of Arrival - Fecha estimada de arribo",
        tracking=True
    )
    date_arrival = fields.Date(
        string="Fecha Arribo Real",
        tracking=True
    )
    date_customs_release = fields.Date(
        string="Fecha Liberación Aduana",
        tracking=True
    )
    
    # === EMBARQUE ===
    shipment_ids = fields.One2many(
        'comex.shipment',
        'operation_id',
        string="Embarques"
    )
    shipment_count = fields.Integer(
        compute='_compute_shipment_count',
        string="Nro. Embarques"
    )
    
    # === AGENTES ===
    freight_agent_id = fields.Many2one(
        'res.partner',
        string="Agente de Carga",
        domain="[('is_freight_agent', '=', True)]",
        tracking=True,
        help="Freight Forwarder / Agente de Carga"
    )
    customs_agent_id = fields.Many2one(
        'res.partner',
        string="Despachante de Aduana",
        domain="[('is_customs_agent', '=', True)]",
        tracking=True
    )
    
    # === DESPACHO ADUANERO ===
    customs_clearance_ids = fields.One2many(
        'comex.customs.clearance',
        'operation_id',
        string="Despachos"
    )
    customs_clearance_number = fields.Char(
        string="Nro. Despacho Principal",
        tracking=True,
        help="Número de Despacho de Importación/Exportación"
    )
    
    # === MULC / PAGOS ===
    mulc_ids = fields.One2many(
        'comex.mulc',
        'operation_id',
        string="Operaciones MULC"
    )
    nominated_bank_id = fields.Many2one(
        'res.partner',
        string="Banco Nominado",
        domain="[('is_bank', '=', True)]",
        tracking=True,
        help="Banco autorizado para operaciones de cambio"
    )
    
    # === ESTADO DE OPERACIÓN ===
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('coordinating', 'En Coordinación'),
        ('in_transit', 'En Viaje'),
        ('at_port', 'En Puerto'),
        ('customs', 'En Aduana'),
        ('released', 'Liberado'),
        ('in_warehouse', 'En Depósito'),
        ('received', 'Recibido'),
        ('closed', 'Cerrado'),
        ('cancelled', 'Cancelado'),
    ], string="Estado", default='draft', tracking=True, copy=False)
    
    payment_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('partial', 'Parcial'),
        ('mulc_pending', 'Pendiente MULC'),
        ('mulc_approved', 'MULC Aprobado'),
        ('paid', 'Pagado'),
    ], string="Estado Pago", default='pending', tracking=True)
    
    # === NOTAS ===
    notes = fields.Html(string="Notas Internas")
    
    # === COMPUTE METHODS ===
    @api.depends('amount_fob', 'amount_freight', 'amount_insurance')
    def _compute_amount_cif(self):
        for record in self:
            record.amount_cif = record.amount_fob + record.amount_freight + record.amount_insurance
    
    @api.depends('shipment_ids')
    def _compute_shipment_count(self):
        for record in self:
            record.shipment_count = len(record.shipment_ids)
    
    # === SEQUENCE ===
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                prefix = 'IMP' if vals.get('operation_type') == 'import' else 'EXP'
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'comex.operation'
                ) or _('New')
        return super().create(vals_list)
    
    # === ACTION METHODS ===
    def action_confirm(self):
        self.write({'state': 'confirmed'})
    
    def action_coordinate(self):
        self.write({'state': 'coordinating'})
    
    def action_in_transit(self):
        self.write({'state': 'in_transit'})
    
    def action_at_port(self):
        self.write({'state': 'at_port'})
    
    def action_in_customs(self):
        self.write({'state': 'customs'})
    
    def action_release(self):
        self.write({'state': 'released', 'date_customs_release': fields.Date.today()})
    
    def action_warehouse(self):
        self.write({'state': 'in_warehouse'})
    
    def action_receive(self):
        self.write({'state': 'received'})
    
    def action_close(self):
        self.write({'state': 'closed'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        self.write({'state': 'draft'})
```

#### 4.2.2 Modelo: `comex.shipment` (Embarques)

```python
class ComexShipment(models.Model):
    _name = 'comex.shipment'
    _description = 'Embarque COMEX'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_etd desc'
    
    name = fields.Char(string="Referencia", required=True)
    operation_id = fields.Many2one(
        'comex.operation',
        string="Operación COMEX",
        required=True,
        ondelete='cascade'
    )
    
    # === BILL OF LADING ===
    bill_of_lading = fields.Char(
        string="Bill of Lading (B/L)",
        tracking=True,
        help="Número de Conocimiento de Embarque"
    )
    bl_type = fields.Selection([
        ('ocean', 'Marítimo (Ocean B/L)'),
        ('air', 'Aéreo (AWB)'),
        ('road', 'Terrestre (CMR/CRT)'),
        ('multimodal', 'Multimodal'),
    ], string="Tipo B/L", default='ocean')
    
    # === CONTENEDOR ===
    container_number = fields.Char(string="Nro. Contenedor")
    container_type_id = fields.Many2one(
        'comex.container.type',
        string="Tipo Contenedor"
    )
    seal_number = fields.Char(string="Nro. Precinto")
    
    # === TRANSPORTE ===
    carrier_id = fields.Many2one(
        'res.partner',
        string="Transportista/Naviera",
        domain="[('is_carrier', '=', True)]"
    )
    vessel_name = fields.Char(string="Nombre Buque/Vuelo")
    voyage_number = fields.Char(string="Nro. Viaje")
    
    # === PUERTOS ===
    port_loading_id = fields.Many2one(
        'comex.port',
        string="Puerto Carga",
        help="Port of Loading (POL)"
    )
    port_discharge_id = fields.Many2one(
        'comex.port',
        string="Puerto Descarga",
        help="Port of Discharge (POD)"
    )
    
    # === FECHAS ===
    date_etd = fields.Date(string="ETD", tracking=True)
    date_atd = fields.Date(string="ATD", tracking=True)
    date_eta = fields.Date(string="ETA", tracking=True)
    date_ata = fields.Date(string="ATA", tracking=True)
    
    transit_days = fields.Integer(
        string="Días Tránsito",
        compute='_compute_transit_days',
        store=True
    )
    
    # === PESOS Y MEDIDAS ===
    weight_gross = fields.Float(string="Peso Bruto (Kg)")
    weight_net = fields.Float(string="Peso Neto (Kg)")
    volume = fields.Float(string="Volumen (M³)")
    packages_qty = fields.Integer(string="Cantidad Bultos")
    packages_type = fields.Char(string="Tipo Bultos")
    
    # === ESTADO ===
    state = fields.Selection([
        ('pending', 'Pendiente Embarque'),
        ('loaded', 'Embarcado'),
        ('in_transit', 'En Tránsito'),
        ('arrived', 'Arribado'),
        ('delivered', 'Entregado'),
    ], string="Estado", default='pending', tracking=True)
    
    @api.depends('date_etd', 'date_eta')
    def _compute_transit_days(self):
        for record in self:
            if record.date_etd and record.date_eta:
                record.transit_days = (record.date_eta - record.date_etd).days
            else:
                record.transit_days = 0
```

#### 4.2.3 Modelo: `comex.customs.clearance` (Despacho Aduanero)

```python
class ComexCustomsClearance(models.Model):
    _name = 'comex.customs.clearance'
    _description = 'Despacho Aduanero'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string="Nro. Despacho",
        required=True,
        tracking=True,
        help="Número de Despacho de Importación/Exportación"
    )
    operation_id = fields.Many2one(
        'comex.operation',
        string="Operación COMEX",
        required=True,
        ondelete='cascade'
    )
    
    # === TIPO Y RÉGIMEN ===
    clearance_type = fields.Selection([
        ('import', 'Importación Definitiva'),
        ('import_temp', 'Importación Temporal'),
        ('export', 'Exportación Definitiva'),
        ('export_temp', 'Exportación Temporal'),
        ('transit', 'Tránsito'),
    ], string="Tipo Despacho", required=True)
    
    customs_regime = fields.Selection([
        ('general', 'Régimen General'),
        ('simplified', 'Régimen Simplificado'),
        ('courier', 'Courier/PSP'),
    ], string="Régimen", default='general')
    
    # === ADUANA ===
    customs_office_id = fields.Many2one(
        'comex.customs.office',
        string="Aduana",
        help="Aduana de registro del despacho"
    )
    
    # === FECHAS ===
    date_register = fields.Date(
        string="Fecha Registro",
        help="Fecha de oficialización del despacho"
    )
    date_release = fields.Date(
        string="Fecha Liberación",
        tracking=True
    )
    
    # === CANAL ===
    channel = fields.Selection([
        ('green', 'Verde'),
        ('orange', 'Naranja'),
        ('red', 'Rojo'),
        ('purple', 'Violeta'),
    ], string="Canal", tracking=True)
    
    # === TRIBUTOS ===
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.ref('base.ARS')
    )
    amount_duties = fields.Monetary(
        string="Derechos Importación",
        currency_field='currency_id'
    )
    amount_statistics = fields.Monetary(
        string="Tasa Estadística",
        currency_field='currency_id'
    )
    amount_vat = fields.Monetary(
        string="IVA",
        currency_field='currency_id'
    )
    amount_vat_additional = fields.Monetary(
        string="IVA Adicional",
        currency_field='currency_id'
    )
    amount_profits = fields.Monetary(
        string="Percepción Ganancias",
        currency_field='currency_id'
    )
    amount_gross_income = fields.Monetary(
        string="Percepción IIBB",
        currency_field='currency_id'
    )
    amount_total = fields.Monetary(
        string="Total Tributos",
        compute='_compute_amount_total',
        store=True,
        currency_field='currency_id'
    )
    
    # === ESTADO ===
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('registered', 'Oficializado'),
        ('verification', 'En Verificación'),
        ('released', 'Liberado'),
        ('cancelled', 'Anulado'),
    ], string="Estado", default='draft', tracking=True)
    
    @api.depends(
        'amount_duties', 'amount_statistics', 'amount_vat',
        'amount_vat_additional', 'amount_profits', 'amount_gross_income'
    )
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = (
                record.amount_duties +
                record.amount_statistics +
                record.amount_vat +
                record.amount_vat_additional +
                record.amount_profits +
                record.amount_gross_income
            )
```

#### 4.2.4 Modelo: `comex.mulc` (Operaciones MULC)

```python
class ComexMULC(models.Model):
    _name = 'comex.mulc'
    _description = 'Operación MULC - Acceso a Divisas'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_request desc'
    
    name = fields.Char(
        string="Referencia MULC",
        required=True,
        copy=False,
        default=lambda self: _('New')
    )
    operation_id = fields.Many2one(
        'comex.operation',
        string="Operación COMEX",
        required=True,
        ondelete='cascade'
    )
    
    # === BANCO ===
    bank_id = fields.Many2one(
        'res.partner',
        string="Banco Operador",
        domain="[('is_bank', '=', True)]",
        required=True,
        tracking=True
    )
    
    # === MONTOS ===
    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        required=True,
        default=lambda self: self.env.ref('base.USD')
    )
    amount_requested = fields.Monetary(
        string="Monto Solicitado",
        currency_field='currency_id',
        required=True,
        tracking=True
    )
    amount_approved = fields.Monetary(
        string="Monto Aprobado",
        currency_field='currency_id',
        tracking=True
    )
    
    # === TIPO DE CAMBIO ===
    rate_type = fields.Selection([
        ('official', 'Oficial'),
        ('mep', 'MEP'),
        ('ccl', 'CCL'),
    ], string="Tipo Cambio", default='official')
    exchange_rate = fields.Float(
        string="Tipo de Cambio",
        digits=(16, 4)
    )
    
    # === FECHAS ===
    date_request = fields.Date(
        string="Fecha Solicitud",
        default=fields.Date.context_today,
        tracking=True
    )
    date_due = fields.Date(
        string="Fecha Vencimiento Acceso",
        help="Fecha límite para acceso a divisas según normativa BCRA"
    )
    date_approval = fields.Date(
        string="Fecha Aprobación",
        tracking=True
    )
    date_execution = fields.Date(
        string="Fecha Ejecución",
        tracking=True
    )
    
    # === NORMATIVA ===
    bcra_communication = fields.Char(
        string="Comunicación BCRA",
        help="Comunicación 'A' aplicable"
    )
    
    # === ESTADO ===
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('requested', 'Solicitado'),
        ('approved', 'Aprobado'),
        ('executed', 'Ejecutado'),
        ('rejected', 'Rechazado'),
        ('cancelled', 'Cancelado'),
    ], string="Estado", default='draft', tracking=True)
    
    notes = fields.Text(string="Observaciones")
```

### 4.3 Extensión de Modelos Nativos

#### 4.3.1 Extensión `res.partner`

```python
class ResPartnerComex(models.Model):
    _inherit = 'res.partner'
    
    # === ROLES COMEX ===
    is_freight_agent = fields.Boolean(
        string="Agente de Carga",
        help="Es un Freight Forwarder / Agente de Carga"
    )
    is_customs_agent = fields.Boolean(
        string="Despachante de Aduana"
    )
    is_carrier = fields.Boolean(
        string="Transportista/Naviera"
    )
    is_authorized_bank = fields.Boolean(
        string="Banco Autorizado MULC",
        help="Banco autorizado para operaciones de cambio"
    )
    
    # === DATOS DESPACHANTE ===
    customs_license = fields.Char(
        string="Matrícula Despachante"
    )
    
    # === INCOTERM POR DEFECTO ===
    default_incoterm_id = fields.Many2one(
        'account.incoterms',
        string="Incoterm por Defecto",
        help="Incoterm preferido para operaciones con este proveedor"
    )
    
    # === OPERACIONES RELACIONADAS ===
    comex_operation_ids = fields.One2many(
        'comex.operation',
        'partner_id',
        string="Operaciones COMEX"
    )
    comex_operation_count = fields.Integer(
        compute='_compute_comex_operation_count',
        string="Operaciones"
    )
    
    def _compute_comex_operation_count(self):
        for partner in self:
            partner.comex_operation_count = self.env['comex.operation'].search_count([
                ('partner_id', '=', partner.id)
            ])
```

#### 4.3.2 Extensión `purchase.order`

```python
class PurchaseOrderComex(models.Model):
    _inherit = 'purchase.order'
    
    comex_operation_id = fields.Many2one(
        'comex.operation',
        string="Operación COMEX",
        tracking=True
    )
    is_comex = fields.Boolean(
        string="Es COMEX",
        compute='_compute_is_comex',
        store=True
    )
    
    # === INCOTERM (heredado de nativo) ===
    # incoterm_id ya existe en purchase.order nativo
    
    # === CAMPOS ADICIONALES ===
    proforma_number = fields.Char(
        string="Nro. Proforma",
        help="Número de factura proforma del proveedor"
    )
    
    @api.depends('partner_id.country_id', 'company_id.country_id')
    def _compute_is_comex(self):
        for order in self:
            order.is_comex = (
                order.partner_id.country_id and
                order.partner_id.country_id != order.company_id.country_id
            )
```

---

## 5. MAPEO DE CAMPOS SOLICITADOS

| Campo Solicitado | Modelo | Nombre Campo | Tipo | Notas |
|------------------|--------|--------------|------|-------|
| **BL** | comex.shipment | `bill_of_lading` | Char | Bill of Lading |
| **Incoterm** | comex.operation | `incoterm_id` | Many2one(account.incoterms) | Nativo Odoo |
| **FOB R** | comex.operation | `amount_fob` | Monetary | Valor FOB |
| **ETD** | comex.shipment | `date_etd` | Date | Estimated Time Departure |
| **ETA** | comex.shipment | `date_eta` | Date | Estimated Time Arrival |
| **Despacho** | comex.customs.clearance | `name` | Char | Nro. Despacho |
| **Agente de carga** | comex.operation | `freight_agent_id` | Many2one(res.partner) | Freight Forwarder |
| **Banco nominado** | comex.operation | `nominated_bank_id` | Many2one(res.partner) | Para MULC |
| **Estado operación** | comex.operation | `state` | Selection | 11 estados definidos |
| **MULC** | comex.mulc | (modelo completo) | Model | Acceso a divisas |
| **Estado de pago** | comex.operation | `payment_state` | Selection | 5 estados |

---

## 6. DEPENDENCIAS DE MÓDULOS

### 6.1 Dependencias Nativas Odoo

```python
'depends': [
    'base',
    'mail',
    'purchase_stock',     # Para integración con compras
    'sale_stock',         # Para integración con ventas
    'account',            # Para facturas e incoterms
    'stock',              # Para recepciones
    'contacts',           # Para tipos de contacto
],
```

### 6.2 Dependencias OCA Recomendadas (Opcionales)

```python
# En versión extendida, considerar:
'depends_optional': [
    'product_harmonized_system',     # Para códigos HS/NCM
    'purchase_partner_incoterm',     # Incoterm por proveedor
    'purchase_container',            # Gestión de contenedores avanzada
],
```

---

## 7. SEGURIDAD Y PERMISOS

### 7.1 Grupos de Usuarios

```xml
<!-- security/l10n_ar_comex_groups.xml -->
<odoo>
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
</odoo>
```

### 7.2 Permisos de Acceso

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_comex_operation_user,comex.operation.user,model_comex_operation,group_comex_user,1,1,1,0
access_comex_operation_manager,comex.operation.manager,model_comex_operation,group_comex_manager,1,1,1,1
access_comex_shipment_user,comex.shipment.user,model_comex_shipment,group_comex_user,1,1,1,0
access_comex_shipment_manager,comex.shipment.manager,model_comex_shipment,group_comex_manager,1,1,1,1
access_comex_customs_clearance_user,comex.customs.clearance.user,model_comex_customs_clearance,group_comex_user,1,0,0,0
access_comex_customs_clearance_manager,comex.customs.clearance.manager,model_comex_customs_clearance,group_comex_manager,1,1,1,1
access_comex_mulc_user,comex.mulc.user,model_comex_mulc,group_comex_mulc,1,1,1,0
access_comex_mulc_manager,comex.mulc.manager,model_comex_mulc,group_comex_manager,1,1,1,1
```

---

## 8. VISTAS XML (Ejemplos)

### 8.1 Vista Form Principal

```xml
<!-- views/comex_operation_views.xml -->
<odoo>
    <record id="comex_operation_view_form" model="ir.ui.view">
        <field name="name">comex.operation.view.form</field>
        <field name="model">comex.operation</field>
        <field name="arch" type="xml">
            <form string="Operación COMEX">
                <header>
                    <button name="action_confirm" string="Confirmar"
                        type="object" class="btn-primary"
                        invisible="state != 'draft'"/>
                    <button name="action_coordinate" string="Coordinar"
                        type="object"
                        invisible="state != 'confirmed'"/>
                    <button name="action_in_transit" string="En Viaje"
                        type="object"
                        invisible="state != 'coordinating'"/>
                    <button name="action_at_port" string="En Puerto"
                        type="object"
                        invisible="state != 'in_transit'"/>
                    <button name="action_in_customs" string="En Aduana"
                        type="object"
                        invisible="state != 'at_port'"/>
                    <button name="action_release" string="Liberar"
                        type="object"
                        invisible="state != 'customs'"/>
                    <button name="action_warehouse" string="En Depósito"
                        type="object"
                        invisible="state != 'released'"/>
                    <button name="action_receive" string="Recibir"
                        type="object"
                        invisible="state != 'in_warehouse'"/>
                    <button name="action_close" string="Cerrar"
                        type="object" class="btn-success"
                        invisible="state != 'received'"/>
                    <button name="action_cancel" string="Cancelar"
                        type="object"
                        invisible="state in ('closed', 'cancelled')"/>
                    <field name="state" widget="statusbar"
                        statusbar_visible="draft,confirmed,in_transit,at_port,customs,released,received,closed"/>
                </header>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                        <button class="oe_stat_button" type="object"
                            name="action_view_shipments" icon="fa-ship">
                            <field name="shipment_count" widget="statinfo"
                                string="Embarques"/>
                        </button>
                    </div>
                    <div class="oe_title">
                        <h1>
                            <field name="name" readonly="1"/>
                        </h1>
                    </div>
                    <group>
                        <group name="main_left">
                            <field name="operation_type"/>
                            <field name="partner_id"/>
                            <field name="date_order"/>
                            <field name="company_id" groups="base.group_multi_company"/>
                        </group>
                        <group name="main_right">
                            <field name="incoterm_id"/>
                            <field name="incoterm_location"/>
                            <field name="payment_state"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Valores" name="values">
                            <group>
                                <group>
                                    <field name="currency_id"/>
                                    <field name="amount_fob"/>
                                    <field name="amount_freight"/>
                                    <field name="amount_insurance"/>
                                </group>
                                <group>
                                    <field name="amount_cif"/>
                                </group>
                            </group>
                        </page>
                        <page string="Fechas" name="dates">
                            <group>
                                <group>
                                    <field name="date_etd"/>
                                    <field name="date_eta"/>
                                </group>
                                <group>
                                    <field name="date_arrival"/>
                                    <field name="date_customs_release"/>
                                </group>
                            </group>
                        </page>
                        <page string="Embarques" name="shipments">
                            <field name="shipment_ids" mode="tree">
                                <tree editable="bottom">
                                    <field name="name"/>
                                    <field name="bill_of_lading"/>
                                    <field name="container_number"/>
                                    <field name="date_etd"/>
                                    <field name="date_eta"/>
                                    <field name="state"/>
                                </tree>
                            </field>
                        </page>
                        <page string="Agentes" name="agents">
                            <group>
                                <group>
                                    <field name="freight_agent_id"/>
                                    <field name="customs_agent_id"/>
                                </group>
                                <group>
                                    <field name="nominated_bank_id"/>
                                </group>
                            </group>
                        </page>
                        <page string="Despachos" name="customs">
                            <field name="customs_clearance_ids"/>
                        </page>
                        <page string="MULC" name="mulc" groups="l10n_ar_comex.group_comex_mulc">
                            <field name="mulc_ids"/>
                        </page>
                        <page string="Documentos" name="documents">
                            <group>
                                <field name="purchase_order_ids" widget="many2many_tags"/>
                                <field name="sale_order_ids" widget="many2many_tags"/>
                                <field name="invoice_ids" widget="many2many_tags"/>
                            </group>
                        </page>
                        <page string="Notas" name="notes">
                            <field name="notes"/>
                        </page>
                    </notebook>
                </sheet>
                <chatter/>
            </form>
        </field>
    </record>
</odoo>
```

---

## 9. ROADMAP DE DESARROLLO

### Fase 1: MVP (4-6 semanas)
- [x] Análisis y diseño técnico
- [ ] Modelos base: comex.operation, comex.shipment
- [ ] Extensión res.partner y purchase.order
- [ ] Vistas básicas CRUD
- [ ] Flujo de estados básico
- [ ] Seguridad y permisos

### Fase 2: Despachos y MULC (4 semanas)
- [ ] Modelo comex.customs.clearance
- [ ] Modelo comex.mulc
- [ ] Cálculo de tributos aduaneros
- [ ] Estados de pago

### Fase 3: Integraciones (4 semanas)
- [ ] Integración con stock (recepciones)
- [ ] Integración con account (facturas, pagos)
- [ ] Integración con product_harmonized_system (NCM)
- [ ] Reportes básicos

### Fase 4: Avanzado (según demanda)
- [ ] Dashboard COMEX
- [ ] Alertas y notificaciones
- [ ] API para integraciones externas
- [ ] Integración Sistema Malvina (si disponible API)

---

## 10. CONSIDERACIONES FINALES

### 10.1 Compatibilidad

- ✅ Compatible con Odoo 17 CE y EE
- ✅ No modifica comportamiento nativo de Odoo
- ✅ Sigue guías de desarrollo OCA
- ✅ Preparado para localización argentina (l10n_ar)

### 10.2 Extensibilidad

El módulo está diseñado para ser extendido fácilmente:
- Nuevos estados de operación
- Campos adicionales vía herencia
- Integración con otros módulos COMEX de OCA

### 10.3 Mantenimiento

- Código documentado en español e inglés
- Tests unitarios para flujos críticos
- Versionado semántico

---

**Documento preparado por**: GitHub Copilot  
**Fecha**: 16 de Diciembre de 2025  
**Revisión**: 1.0
