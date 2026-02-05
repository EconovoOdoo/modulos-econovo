# DISEÑO TÉCNICO: Módulo COMEX para Argentina - Odoo 17

**Autor**: Jose D. Leonett  
**Última Actualización**: 5 de Febrero de 2026  
**Versión**: 17.0.4.1.0 (Phase 4.1 Complete - Production Ready)  
**Licencia**: AGPL-3

---

## 1. ESTADO ACTUAL DEL PROYECTO

### 1.1 Versión en Producción: v17.0.4.1.0

**✅ IMPLEMENTADO Y FUNCIONAL:**
- Gestión completa de operaciones de importación/exportación
- **Phase 4.1: Sistema automático de cálculo de tributos aduaneros**
- Workflow dinámico con estados configurables (patrón Kanban)
- Gestión de embarques y contenedores (via `stock.quant.package`)
- Despachos aduaneros con tracking completo
- Operaciones MULC (BCRA)
- Integración con purchase orders y stock movements
- Multi-company support

### 1.2 Phase 4.1: Sistema de Tributos Aduaneros (COMPLETADO)

El sistema implementa **cálculo automático de tributos** usando Tax Groups nativos de Odoo combinado con **computed fields bidireccionales**.

**Características principales:**
1. ✅ **Automatic Tax Calculation**: IVA 21%, IIGG 6%, IIBB 3%
2. ✅ **Smart Invoice Creation**: Creación directa desde customs clearance
3. ✅ **Bidirectional Sync**: Cambios en invoice ↔ clearance sincronizados automáticamente
4. ✅ **Configurable Mappings**: Productos y keywords para mapeo flexible
5. ✅ **Parse Logs**: Audit trail completo de parsing de facturas
6. ✅ **Production Ready**: Sin debug logging, documentación completa

---

## 2. ARQUITECTURA DE TRIBUTOS (PHASE 4.1)

### 2.1 Tax Groups System

Estructura de impuestos usando Tax Groups nativo de Odoo:

```
Import Tributes (Tax Group)
├── IVA Import 21% (purchase tax, type_tax_use='purchase')
├── IIGG Perception 6% (purchase tax)
└── IIBB Perception 3% (purchase tax)
```

**Configuración (data/comex_tax_data.xml):**
- Tax Group: `comex_tax_group_import_tributes`
- Todos los impuestos: `amount_type='percent'`, `price_include=False`
- Aplicables a compras: `type_tax_use='purchase'`
- Sin repartition lines explícitas (usa defaults de Odoo)

### 2.2 Productos de Tributos

Tres productos de servicio mapeados a campos específicos:

| XML ID | Nombre | Campo Clearance | Tax Group Aplicado |
|--------|--------|-----------------|-------------------|
| `comex_product_die` | DIE - Derecho de Importación | `amount_duties` | ✅ Import Tributes |
| `comex_product_statistics` | Tasa Estadística | `amount_statistics` | ✅ Import Tributes |
| `comex_product_guard_service` | Servicios de Guarda | `amount_fees` | ❌ Sin impuestos |

**Configuración:**
- Type: `service`
- `supplier_taxes_id`: Referencia a Tax Group
- `can_be_expensed`: True

### 2.3 Campos de Tributos (Computed + Inverse Pattern)

Los campos de tributos implementan el patrón **Smart Computed with Inverse**:

```python
class ComexCustomsClearance(models.Model):
    _name = 'comex.customs.clearance'
    
    # Tribute amounts (3 campos principales)
    amount_duties = fields.Monetary(
        compute='_compute_tribute_amounts',
        inverse='_inverse_amount_duties',
        store=True,
        # Readonly en UI cuando vendor_bill_id existe
    )
    amount_statistics = fields.Monetary(
        compute='_compute_tribute_amounts',
        inverse='_inverse_amount_statistics',
        store=True,
    )
    amount_fees = fields.Monetary(
        compute='_compute_tribute_amounts',
        inverse='_inverse_amount_fees',
        store=True,
    )
```

**Métodos clave:**

| Método | Propósito | Trigger |
|--------|-----------|---------|
| `_compute_tribute_amounts()` | Lee valores desde invoice lines | @api.depends('vendor_bill_id.invoice_line_ids') |
| `_inverse_amount_duties()` | Actualiza invoice line de DIE | User edits amount_duties |
| `_inverse_amount_statistics()` | Actualiza invoice line de Statistics | User edits amount_statistics |
| `_inverse_amount_fees()` | Actualiza invoice line de Fees | User edits amount_fees |
| `_inverse_tribute_amount()` | Lógica compartida de inverse | Called by all inverse methods |

**Comportamiento:**

1. **Sin invoice vinculada**:
   - Campos editables manualmente
   - Valores almacenados en clearance
   - Usados para crear invoice

2. **Con invoice vinculada**:
   - Campos compute desde invoice lines (single source of truth)
   - Readonly en UI (atributo `readonly="vendor_bill_id"`)
   - Si usuario edita (programáticamente): inverse actualiza invoice

3. **Ediciones en invoice**:
   - Cambios trigger recompute en clearance
   - Sincronización automática vía @api.depends

### 2.4 Flujo de Creación de Invoice

**Método**: `action_create_tribute_invoice()` en `comex.customs.clearance`

**Ejemplo de cálculo:**

```
INPUT (clearance):
- amount_duties: $20,000
- amount_statistics: $5,500
- amount_fees: $5,000

OUTPUT (invoice lines):
1. DIE: $20,000
   - IVA: $4,200 (21%)
   - IIGG: $1,200 (6%)
   - IIBB: $600 (3%)

2. Tasa Estadística: $5,500
   - IVA: $1,155
   - IIGG: $330
   - IIBB: $165

3. Servicios: $5,000
   (sin impuestos)

TOTAL INVOICE:
- Subtotal: $30,500
- Taxes: $7,650
- TOTAL: $38,150
```

### 2.5 Sistema de Mapeos

#### 2.5.1 Tribute Fields

```python
class ComexTributeField(models.Model):
    _name = 'comex.tribute.field'
    
    name = fields.Char()              # "Import Duties (DIE)"
    technical_name = fields.Char()    # "amount_duties"
    sequence = fields.Integer()
```

Tres registros en `data/comex_tribute_fields_data.xml`:
- `comex_tribute_field_duties` → amount_duties
- `comex_tribute_field_statistics` → amount_statistics
- `comex_tribute_field_fees` → amount_fees

#### 2.5.2 Product Mappings

```python
class ComexTributeProductMapping(models.Model):
    _name = 'comex.tribute.product.mapping'
    
    tribute_field_id = fields.Many2one('comex.tribute.field')
    product_id = fields.Many2one('product.product')
    company_id = fields.Many2one('res.company')
    active = fields.Boolean(default=True)
```

**Uso:**
- Mapea productos a campos de tributos
- Usado en creación de invoice y parsing
- Configurable desde UI: `COMEX > Configuration > Tribute Product Mappings`

#### 2.5.3 Keyword Mappings (Fallback)

```python
class ComexTributeKeywordMapping(models.Model):
    _name = 'comex.tribute.keyword.mapping'
    
    tribute_field_id = fields.Many2one('comex.tribute.field')
    keyword = fields.Char()           # "die", "estadística", "guarda"
    match_type = fields.Selection([
        ('contains', 'Contains'),
        ('startswith', 'Starts with'),
        ('endswith', 'Ends with'),
        ('exact', 'Exact match'),
        ('regex', 'Regular expression'),
    ])
    priority = fields.Integer(default=10)
    stop_on_match = fields.Boolean(default=True)
```

**Uso:**
- Sistema de fallback cuando no hay match por producto
- Match por descripción de invoice line
- Prioridad configurable (mayor = primero)

### 2.6 Parse Logs (Audit Trail)

```python
class ComexTributeParseLog(models.Model):
    _name = 'comex.tribute.parse.log'
    
    clearance_id = fields.Many2one('comex.customs.clearance', ondelete='cascade')
    invoice_id = fields.Many2one('account.move', ondelete='cascade')
    invoice_line_id = fields.Many2one('account.move.line', ondelete='cascade')
    
    matched = fields.Boolean()
    match_type = fields.Selection([
        ('product', 'Product Match'),
        ('keyword', 'Keyword Match'),
        ('manual', 'Manual Assignment'),
        ('none', 'No Match'),
    ])
    matched_keyword = fields.Char()
    tribute_field_id = fields.Many2one('comex.tribute.field')
```

**Acceso UI:**
- Vista tree: `COMEX > Configuration > Parsing Logs`
- Filtros: por matched/unmatched, por tribute field, por fecha

---

## 3. MODELOS PRINCIPALES DEL MÓDULO

### 3.1 comex.operation

**Propósito**: Operación COMEX (import/export) con workflow dinámico

**Campos clave:**
- `name`: Secuencia IMP/YYYY/NNNNN o EXP/YYYY/NNNNN
- `operation_type`: Selection('import', 'export')
- `stage_id`: Many2one('comex.operation.stage') - Estados configurables
- `partner_id`: Proveedor/Cliente
- `purchase_order_ids`: M2M a purchase.order
- `shipment_ids`: O2M a comex.shipment
- `customs_clearance_ids`: O2M a comex.customs.clearance
- `mulc_ids`: O2M a comex.mulc
- `incoterm_id`, `currency_id`, `amount_fob`, `amount_freight`, `amount_insurance`

### 3.2 comex.operation.stage

**Propósito**: Etapas configurables del workflow (patrón CRM/Project)

**Datos iniciales** (7 etapas):
- Draft, Confirmed, Coordinating, In Transit, At Port, Customs, Released, Closed

### 3.3 comex.shipment

**Propósito**: Embarque/contenedor individual

**Campos:**
- `name`: Bill of Lading / Air Waybill (identificador principal)
- `internal_reference`: Secuencia interna (SHP/YYYY/NNNNN)
- `package_ids`: M2M a stock.quant.package (contenedores)
- `date_etd`, `date_eta`: Fechas estimadas

**Patrón de naming**:
- `name` = BL/AWB real (ej: "COSCO123456789")
- `internal_reference` = Audit trail (ej: "SHP/2026/00001")

### 3.4 comex.customs.clearance

**Propósito**: Despacho de aduana con tributos

**Campos principales:**
- `name`: Secuencia CLC/YYYY/NNNNN
- `dispatch_number`: Char (nro oficial ARCA)
- `clearance_type`: Selection('definitive', 'temporary', 'transit', 'export')
- **Tribute amounts** (Phase 4.1):
  - `amount_duties`, `amount_statistics`, `amount_fees` (computed+inverse)
  - `amount_total`: Computed sum
- `vendor_bill_id`: Many2one('account.move') - Invoice vinculada
- `channel`: Selection('green', 'orange', 'red', 'purple')

**Métodos:**
- `action_create_tribute_invoice()`: Crea invoice con taxes automáticos
- `_compute_tribute_amounts()`: Lee desde invoice lines
- `_inverse_amount_*()`: Actualiza invoice lines

### 3.5 comex.mulc

**Propósito**: Operación MULC (acceso a divisas BCRA)

**Campos:**
- `name`: Secuencia MULC/YYYY/NNNNN
- `bank_partner_id`: Banco nominado
- `amount_usd`, `exchange_rate`, `amount_ars`: Montos
- `state`: Selection('draft', 'requested', 'approved', 'executed', 'cancelled')

---

## 4. PATRONES DE DISEÑO IMPLEMENTADOS

### 4.1 Computed + Inverse Pattern (Bidirectional Sync)

**Similar a**: `sale.order` ↔ `stock.picking.date_deadline`

```python
# Clearance field
amount_duties = fields.Monetary(
    compute='_compute_tribute_amounts',  # Read from invoice
    inverse='_inverse_amount_duties',    # Write to invoice
    store=True,                          # Searchable
)

# Compute: Single source of truth = invoice
@api.depends('vendor_bill_id.invoice_line_ids.price_subtotal')
def _compute_tribute_amounts(self):
    for record in self:
        if record.vendor_bill_id:
            record.amount_duties = compute_from_lines()

# Inverse: Update invoice when clearance edited
def _inverse_amount_duties(self):
    for record in self:
        if record.vendor_bill_id:
            line = record._find_invoice_line_for_field('amount_duties')
            if line:
                line.price_unit = record.amount_duties
```

**Benefits:**
- ✅ Single source of truth (invoice)
- ✅ Edit from either side
- ✅ Automatic sync via @api.depends
- ✅ No data duplication

### 4.2 Tax Groups Pattern (Native Odoo)

**Benefits:**
- ✅ Uses native Odoo functionality
- ✅ Automatic tax calculation on invoice lines
- ✅ Compatible with accounting reports
- ✅ Easy to modify rates without code

### 4.3 Mapping Pattern (Configurable)

```python
# Abstract mapping concept
Product Mapping: product_id → tribute_field_id
Keyword Mapping: keyword → tribute_field_id (with match_type)
```

**Benefits:**
- ✅ User-configurable without code
- ✅ Flexible fallback system
- ✅ Regex support for complex patterns

---

## 5. CONFIGURACIÓN INICIAL (QUICK START)

### 5.1 Step 1: Configure Default Tribute Vendor

```
Settings > General Settings > COMEX Configuration
- Default Tribute Vendor: "Aduana Argentina"
- Default Document Type: "Despacho de Importación (66)"
```

### 5.2 Step 2: Verify Tax Groups

```
Accounting > Configuration > Taxes > Search "Import"
```

**Expected: 4 taxes auto-created**
- Import Tributes (Tax Group)
- IVA Import 21%
- IIGG Perception 6%
- IIBB Perception 3%

### 5.3 Step 3: Review Tribute Products

```
COMEX > Configuration > Tribute Product Mappings
```

**Expected: 3 mappings**
- DIE - Derecho de Importación → amount_duties
- Tasa Estadística → amount_statistics
- Servicios de Guarda → amount_fees

### 5.4 Step 4: Test Workflow

1. Create customs clearance
2. Enter amounts: DIE $20k, Statistics $5.5k, Fees $5k
3. Click "Create Tribute Invoice"
4. Verify: Total $38,150 (base $30.5k + taxes $7.65k)

---

## 6. ROADMAP

### 6.1 Completed (Phase 4.1)

- ✅ Tax Groups system
- ✅ Automatic tax calculation
- ✅ Bidirectional sync clearance ↔ invoice
- ✅ Product and keyword mappings
- ✅ Parse logs audit trail
- ✅ Production-ready (no debug logs)
- ✅ Comprehensive documentation

### 6.2 Future Phases

**Phase 5: NCM Code Management**
- Integration with product.harmonized.system (OCA)
- NCM code validation
- Tariff database

**Phase 6: ARCA Integration**
- API integration with Sistema Malvina
- Automatic dispatch download
- Electronic certificates (CIVUCE)

**Phase 7: Enhanced MULC**
- Automatic exchange rate fetching
- BCRA compliance checks

---

## 7. SUPPORT

- GitHub: https://github.com/josedleonett/econovo_l10n_ar_comex
- Author: Jose D. Leonett

---

**Document Version**: 2.0 (Phase 4.1 Complete)  
**Last Updated**: February 5, 2026
