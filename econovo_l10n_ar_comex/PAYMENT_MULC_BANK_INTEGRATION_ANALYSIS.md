# Análisis: Integración Payment Terms + MULC + Banco Nominado

## Resumen Ejecutivo

Este análisis examina la integración de tres elementos críticos en operaciones COMEX:
1. **Payment Terms** (Instrumento + Timing) → Define "cómo" y "cuándo" se paga
2. **MULC** (Mercado Único y Libre de Cambios) → Acceso al mercado de divisas
3. **Banco Nominado** → Banco designado para la operación

## 1. Contexto y Relaciones de Negocio

### 1.1 Flujo de Operación COMEX

```
Contrato Comercial
    ├─→ Payment Terms definidos (L/C 180 días)
    ├─→ Banco Nominado designado
    └─→ Bienes embarcados
         └─→ MULC solicitado (acceso a divisas)
              ├─→ Validación: payment_timing vs BCRA limits
              ├─→ Ejecución: pago a través del Banco
              └─→ Registro: payment_id en account.payment
```

### 1.2 Relación Entre Conceptos

| Concepto | Momento | Propósito | Información Clave |
|----------|---------|-----------|-------------------|
| **Payment Terms** | Contrato | Acordar forma y plazo | Instrumento + Timing |
| **Banco Nominado** | Contrato/Previo | Designar intermediario | Banco + SWIFT |
| **MULC** | Ejecución | Acceder a divisas | Monto + Fecha + Boleto |

**Relación Lógica:**
- Payment Terms **determina** MULC (L/C 180d → solicitud 180 días post-embarque)
- Banco Nominado **ejecuta** MULC (banco procesa acceso a divisas)
- Payment Instrument **define** si se requiere Banco (L/C sí, TT puede ser directo)

---

## 2. Estado Actual de los Modelos

### 2.1 comex.operation (Operación COMEX)

```python
# FINANCIAL FIELDS (Existing + New)
currency_id = fields.Many2one('res.currency')
payment_instrument_id = fields.Many2one('comex.payment.instrument')  # NEW ✅
payment_timing_id = fields.Many2one('comex.payment.timing')         # NEW ✅
payment_terms_display = fields.Char(compute='_compute_...')          # NEW ✅
amount_fob = fields.Monetary(...)
amount_freight = fields.Monetary(...)
amount_insurance = fields.Monetary(...)
amount_cif = fields.Monetary(...)

# MISSING: nominated_bank_id (to be added)
```

### 2.2 comex.mulc (Operación MULC)

```python
# EXISTING FIELDS
operation_id = fields.Many2one('comex.operation')     # Link to parent
mulc_type = fields.Selection([...])                   # Type of operation
date = fields.Date(...)                               # MULC date
due_date = fields.Date(...)                           # Expiration

# BANK FIELDS (EXISTING - DUAL APPROACH)
bank_id = fields.Many2one('res.bank')                 # Bank entity
bank_partner_id = fields.Many2one('res.partner')      # Bank as partner
swift_code = fields.Char(related='bank_id.bic')      # SWIFT/BIC

# AMOUNTS
currency_id = fields.Many2one('res.currency')
amount_foreign = fields.Monetary(...)
exchange_rate = fields.Float(...)
amount_local = fields.Monetary(compute='...')

# INTEGRATION
payment_id = fields.Many2one('account.payment')       # Actual payment
vendor_bill_id = fields.Many2one('account.move')      # Vendor bill

# REGULATORY
boleto_number = fields.Char(...)                      # BCRA reference
concept_code = fields.Char(...)                       # BCRA concept
```

**Observación Crítica:**
- MULC ya tiene campos de banco (`bank_id` y `bank_partner_id`)
- Pregunta: ¿Banco Nominado es el mismo que ejecuta MULC?
- Respuesta usual: **SÍ**, pero no siempre (puede cambiar)

---

## 3. Propuestas de Integración

### PROPUESTA A ⭐⭐⭐ - Banco Nominado en Operación (Cascada a MULC)

**Concepto:** Banco nominado se define en `comex.operation` y se propaga a MULC.

#### Implementación

```python
# models/comex_operation.py
class ComexOperation(models.Model):
    _name = 'comex.operation'
    
    # Payment Terms (EXISTING - IMPLEMENTED)
    payment_instrument_id = fields.Many2one('comex.payment.instrument')
    payment_timing_id = fields.Many2one('comex.payment.timing')
    payment_terms_display = fields.Char(compute='_compute_payment_terms_display', store=True)
    
    # Nominated Bank (NEW)
    nominated_bank_id = fields.Many2one(
        'res.partner',
        string="Nominated Bank",
        domain="[('is_company', '=', True)]",
        tracking=True,
        help="Bank nominated for this COMEX operation (for L/C, payments, etc.)",
    )
    swift_code = fields.Char(
        string="Bank SWIFT Code",
        related='nominated_bank_id.bank_ids.bic',
        help="SWIFT/BIC code of the nominated bank",
    )
    
    # Computed: Is bank intervention required?
    requires_bank_intervention = fields.Boolean(
        compute='_compute_requires_bank_intervention',
        store=True,
        string="Requires Bank",
        help="Based on payment instrument (L/C, D/P, D/A require bank)",
    )
    
    @api.depends('payment_instrument_id.bank_intervention')
    def _compute_requires_bank_intervention(self):
        for record in self:
            record.requires_bank_intervention = bool(
                record.payment_instrument_id and 
                record.payment_instrument_id.bank_intervention
            )
    
    @api.constrains('payment_instrument_id', 'nominated_bank_id')
    def _check_bank_required(self):
        """Validate that bank is nominated when payment instrument requires it."""
        for record in self:
            if record.requires_bank_intervention and not record.nominated_bank_id:
                raise ValidationError(_(
                    "Payment instrument '%s' requires bank intervention. "
                    "Please nominate a bank for this operation."
                ) % record.payment_instrument_id.name)
```

```python
# models/comex_mulc.py
class ComexMulc(models.Model):
    _name = 'comex.mulc'
    
    # EXISTING
    operation_id = fields.Many2one('comex.operation')
    bank_id = fields.Many2one('res.bank')
    bank_partner_id = fields.Many2one('res.partner')
    
    # NEW: Default from operation
    @api.onchange('operation_id')
    def _onchange_operation_id(self):
        if self.operation_id and self.operation_id.nominated_bank_id:
            self.bank_partner_id = self.operation_id.nominated_bank_id
            # Also update bank_id if partner has associated res.bank
            if self.bank_partner_id.bank_ids:
                self.bank_id = self.bank_partner_id.bank_ids[0]
    
    # NEW: Computed field showing if bank matches nominated
    bank_matches_nominated = fields.Boolean(
        compute='_compute_bank_matches_nominated',
        string="Bank Matches Nominated",
        help="Indicates if MULC bank is the same as operation's nominated bank",
    )
    
    @api.depends('bank_partner_id', 'operation_id.nominated_bank_id')
    def _compute_bank_matches_nominated(self):
        for record in self:
            record.bank_matches_nominated = (
                record.bank_partner_id == record.operation_id.nominated_bank_id
            )
```

#### Validación BCRA

```python
# models/comex_mulc.py (EXTENSION)
class ComexMulc(models.Model):
    
    # NEW: Validation against payment timing
    max_days_allowed = fields.Integer(
        compute='_compute_max_days_allowed',
        string="Max Days Allowed (BCRA)",
        help="Maximum days allowed by BCRA for this operation's payment timing",
    )
    
    is_within_bcra_limit = fields.Boolean(
        compute='_compute_is_within_bcra_limit',
        string="Within BCRA Limit",
        help="Indicates if MULC is requested within BCRA allowed timeframe",
    )
    
    @api.depends('operation_id.payment_timing_id.bcra_max_days')
    def _compute_max_days_allowed(self):
        for record in self:
            if record.operation_id.payment_timing_id:
                record.max_days_allowed = record.operation_id.payment_timing_id.bcra_max_days
            else:
                record.max_days_allowed = 0
    
    @api.depends('days_since_shipment', 'max_days_allowed')
    def _compute_is_within_bcra_limit(self):
        for record in self:
            if record.max_days_allowed > 0:
                record.is_within_bcra_limit = record.days_since_shipment <= record.max_days_allowed
            else:
                record.is_within_bcra_limit = False
    
    @api.constrains('date', 'operation_id')
    def _check_bcra_timing_limit(self):
        """Validate MULC timing against BCRA limits from payment timing."""
        for record in self:
            if not record.is_within_bcra_limit and record.state in ('requested', 'approved'):
                raise ValidationError(_(
                    "MULC requested %d days after shipment, but payment timing '%s' "
                    "allows maximum %d days per BCRA regulations.\n\n"
                    "Shipment date: %s\nMULC date: %s\nDays elapsed: %d\nLimit: %d"
                ) % (
                    record.days_since_shipment,
                    record.operation_id.payment_timing_id.name,
                    record.max_days_allowed,
                    record.operation_id.date_etd,
                    record.date,
                    record.days_since_shipment,
                    record.max_days_allowed,
                ))
```

#### Tree View (comex.operation)

```xml
<tree>
    <field name="name"/>
    <field name="partner_id"/>
    <field name="payment_terms_display" optional="show"/>
    <field name="nominated_bank_id" optional="show"/>
    <field name="requires_bank_intervention" optional="hide"/>
    <!-- Other fields -->
</tree>
```

#### Form View (comex.operation)

```xml
<page string="Financial" name="financial">
    <group>
        <group name="amounts">
            <field name="currency_id"/>
            <field name="payment_instrument_id"/>
            <field name="payment_timing_id"/>
            <field name="requires_bank_intervention" invisible="1"/>
            <field name="nominated_bank_id" 
                   required="requires_bank_intervention"
                   widget="res_partner_many2one"/>
            <field name="swift_code" readonly="1"/>
            <field name="amount_fob"/>
            <!-- Other amounts -->
        </group>
    </group>
</page>
```

#### Pros y Contras

**Pros:**
- ✅ Banco se define una vez en la operación (single source of truth)
- ✅ Se propaga automáticamente a MULC (menos errores)
- ✅ Validación automática: L/C requiere banco, TT no necesariamente
- ✅ SWIFT code disponible desde la operación
- ✅ Tracking completo (cambios de banco registrados)
- ✅ Integración BCRA: validación de timing en MULC

**Contras:**
- ⚠️ Asume que banco nominado = banco ejecutor (no siempre cierto)
- ⚠️ Si banco cambia en MULC, queda desincronizado
- ⚠️ Requiere onchange en MULC para propagar

---

### PROPUESTA B ⭐⭐ - Banco Nominado Solo en MULC (Relacionado a Operación)

**Concepto:** Banco se define únicamente en MULC, operación tiene related field para visualización.

#### Implementación

```python
# models/comex_operation.py
class ComexOperation(models.Model):
    _name = 'comex.operation'
    
    # Payment Terms (EXISTING)
    payment_instrument_id = fields.Many2one('comex.payment.instrument')
    payment_timing_id = fields.Many2one('comex.payment.timing')
    
    # Nominated Bank (RELATED from MULC)
    nominated_bank_id = fields.Many2one(
        'res.partner',
        compute='_compute_nominated_bank_id',
        string="Nominated Bank",
        help="Bank from first MULC operation (if any)",
    )
    
    @api.depends('mulc_ids.bank_partner_id')
    def _compute_nominated_bank_id(self):
        for record in self:
            if record.mulc_ids:
                # Take bank from first MULC
                first_mulc = record.mulc_ids.sorted('date')[0]
                record.nominated_bank_id = first_mulc.bank_partner_id
            else:
                record.nominated_bank_id = False
```

```python
# models/comex_mulc.py (NO CHANGES - uses existing bank fields)
class ComexMulc(models.Model):
    _name = 'comex.mulc'
    
    # EXISTING - no changes needed
    bank_id = fields.Many2one('res.bank')
    bank_partner_id = fields.Many2one('res.partner', domain=[('is_company', '=', True)])
```

#### Pros y Contras

**Pros:**
- ✅ Flexibilidad: cada MULC puede tener diferente banco
- ✅ No duplicación de datos
- ✅ Banco se define donde se usa (en MULC)

**Contras:**
- ❌ Operación no tiene control sobre banco nominado
- ❌ Campo computado (no searchable, no writable)
- ❌ Si no hay MULC, no hay banco visible
- ❌ No hay validación temprana (L/C sin banco nominado)
- ❌ Menos intuitivo para el usuario

---

### PROPUESTA C ⭐⭐⭐⭐ - Banco en Operación + Propagación Inteligente

**Concepto:** Banco nominado en operación, se propaga a MULC pero permite override.

#### Implementación

```python
# models/comex_operation.py
class ComexOperation(models.Model):
    _name = 'comex.operation'
    
    # Payment Terms (EXISTING)
    payment_instrument_id = fields.Many2one('comex.payment.instrument')
    payment_timing_id = fields.Many2one('comex.payment.timing')
    
    # Nominated Bank (MAIN)
    nominated_bank_id = fields.Many2one(
        'res.partner',
        string="Nominated Bank",
        domain="[('is_company', '=', True)]",
        tracking=True,
        help="Default bank for this COMEX operation",
    )
    
    # Bank Intervention Required (from payment instrument)
    requires_bank_intervention = fields.Boolean(
        compute='_compute_requires_bank_intervention',
        store=True,
    )
    
    @api.depends('payment_instrument_id.bank_intervention')
    def _compute_requires_bank_intervention(self):
        for record in self:
            record.requires_bank_intervention = bool(
                record.payment_instrument_id and 
                record.payment_instrument_id.bank_intervention
            )
    
    # Optional constraint (can be warning instead)
    @api.onchange('payment_instrument_id', 'nominated_bank_id')
    def _onchange_check_bank_required(self):
        if self.requires_bank_intervention and not self.nominated_bank_id:
            return {
                'warning': {
                    'title': _('Bank Required'),
                    'message': _(
                        'Payment instrument "%s" typically requires bank intervention. '
                        'Consider nominating a bank.'
                    ) % self.payment_instrument_id.name,
                }
            }
```

```python
# models/comex_mulc.py
class ComexMulc(models.Model):
    _name = 'comex.mulc'
    
    # EXISTING FIELDS (no change)
    operation_id = fields.Many2one('comex.operation')
    bank_id = fields.Many2one('res.bank')
    bank_partner_id = fields.Many2one('res.partner', domain=[('is_company', '=', True)])
    
    # NEW: Smart default from operation
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # If creating MULC from operation context
        if self.env.context.get('default_operation_id'):
            operation = self.env['comex.operation'].browse(self.env.context['default_operation_id'])
            if operation.nominated_bank_id:
                res['bank_partner_id'] = operation.nominated_bank_id.id
                if operation.nominated_bank_id.bank_ids:
                    res['bank_id'] = operation.nominated_bank_id.bank_ids[0].id
        return res
    
    # NEW: Indicator if using nominated bank
    uses_nominated_bank = fields.Boolean(
        compute='_compute_uses_nominated_bank',
        string="Using Nominated Bank",
    )
    
    @api.depends('bank_partner_id', 'operation_id.nominated_bank_id')
    def _compute_uses_nominated_bank(self):
        for record in self:
            record.uses_nominated_bank = (
                record.bank_partner_id == record.operation_id.nominated_bank_id
            )
    
    # NEW: BCRA validation from payment timing
    @api.depends('operation_id.payment_timing_id.bcra_max_days', 'days_since_shipment')
    def _compute_is_within_bcra_limit(self):
        for record in self:
            if record.operation_id.payment_timing_id:
                max_days = record.operation_id.payment_timing_id.bcra_max_days
                record.is_within_bcra_limit = (
                    record.days_since_shipment <= max_days if max_days > 0 else False
                )
            else:
                record.is_within_bcra_limit = False
```

#### Views

**comex_operation form view:**
```xml
<page string="Financial" name="financial">
    <group>
        <group name="payment_terms">
            <label for="payment_instrument_id"/>
            <div>
                <field name="payment_instrument_id" class="oe_inline"/>
                <field name="requires_bank_intervention" invisible="1"/>
            </div>
            <field name="payment_timing_id"/>
            <field name="nominated_bank_id" 
                   widget="res_partner_many2one"
                   context="{'default_is_company': True, 'show_vat': True}"/>
        </group>
        <group name="amounts">
            <field name="currency_id"/>
            <field name="amount_fob"/>
            <!-- ... -->
        </group>
    </group>
</page>
```

**comex_mulc form view (modified):**
```xml
<group name="bank_details">
    <field name="bank_partner_id" widget="res_partner_many2one"/>
    <field name="bank_id"/>
    <field name="uses_nominated_bank" widget="boolean_toggle"/>
    <field name="swift_code" readonly="1"/>
</group>
```

**comex_mulc tree view (modified):**
```xml
<tree decoration-warning="not is_within_bcra_limit">
    <field name="name"/>
    <field name="operation_id"/>
    <field name="date"/>
    <field name="bank_partner_id" optional="show"/>
    <field name="amount_foreign"/>
    <field name="is_within_bcra_limit" optional="show" 
           widget="boolean"
           string="BCRA OK"/>
    <field name="state"/>
</tree>
```

#### Pros y Contras

**Pros:**
- ✅ Mejor de ambos mundos: default inteligente + flexibilidad
- ✅ Banco visible en operación (tree view)
- ✅ MULC puede cambiar banco si necesario (edge cases)
- ✅ Validación suave (warning, no constraint hard)
- ✅ Default automático al crear MULC
- ✅ Indicador si se usa banco nominado o no
- ✅ Integración BCRA completa

**Contras:**
- ⚠️ Más complejo que Propuesta A
- ⚠️ Requiere lógica en default_get
- ⚠️ Usuario puede olvidar cambiar banco en MULC si necesario

---

### PROPUESTA D ⭐ - Banco Nominado Separado del Banco MULC

**Concepto:** Dos campos distintos - uno para L/C, otro para MULC.

#### Implementación

```python
# models/comex_operation.py
class ComexOperation(models.Model):
    _name = 'comex.operation'
    
    # Nominated Bank (for L/C, contracts)
    nominated_bank_id = fields.Many2one(
        'res.partner',
        string="Nominated Bank (L/C)",
        domain="[('is_company', '=', True)]",
        help="Bank nominated in contract for L/C or documentary collection",
    )
    
    # Correspondent Bank (for actual payments)
    correspondent_bank_id = fields.Many2one(
        'res.partner',
        string="Correspondent Bank",
        domain="[('is_company', '=', True)]",
        help="Bank used for actual MULC operations (may differ from nominated)",
    )
```

```python
# models/comex_mulc.py (uses correspondent_bank_id)
class ComexMulc(models.Model):
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_operation_id'):
            operation = self.env['comex.operation'].browse(self.env.context['default_operation_id'])
            # Prefer correspondent bank, fallback to nominated
            bank = operation.correspondent_bank_id or operation.nominated_bank_id
            if bank:
                res['bank_partner_id'] = bank.id
        return res
```

#### Pros y Contras

**Pros:**
- ✅ Separación clara de responsabilidades
- ✅ Flexibilidad máxima

**Contras:**
- ❌ Confuso para usuarios (¿cuál es cuál?)
- ❌ Duplicación de datos
- ❌ Over-engineering para caso común

---

## 4. Integración Payment Timing → MULC Due Date

Todas las propuestas incluyen esta lógica:

```python
# models/comex_mulc.py
class ComexMulc(models.Model):
    
    # Suggested due date from payment timing
    suggested_due_date = fields.Date(
        compute='_compute_suggested_due_date',
        string="Suggested Due Date",
        help="Calculated from shipment date + payment timing days",
    )
    
    @api.depends('operation_id.date_etd', 'operation_id.payment_timing_id.days')
    def _compute_suggested_due_date(self):
        for record in self:
            if record.operation_id.date_etd and record.operation_id.payment_timing_id:
                from datetime import timedelta
                days = record.operation_id.payment_timing_id.days
                record.suggested_due_date = record.operation_id.date_etd + timedelta(days=days)
            else:
                record.suggested_due_date = False
    
    # Auto-fill due_date when creating MULC
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_operation_id'):
            operation = self.env['comex.operation'].browse(self.env.context['default_operation_id'])
            if operation.date_etd and operation.payment_timing_id:
                from datetime import timedelta
                days = operation.payment_timing_id.days
                res['due_date'] = operation.date_etd + timedelta(days=days)
        return res
```

---

## 5. Integración Payment Instrument → MULC Concept Code

```python
# models/comex_payment_instrument.py (ADD FIELD)
class ComexPaymentInstrument(models.Model):
    _name = 'comex.payment.instrument'
    
    # EXISTING fields...
    
    # NEW: BCRA concept code mapping
    bcra_concept_code = fields.Char(
        string="BCRA Concept Code",
        help="Default BCRA concept code for this payment instrument",
    )
```

```python
# models/comex_mulc.py (AUTO-FILL)
class ComexMulc(models.Model):
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_operation_id'):
            operation = self.env['comex.operation'].browse(self.env.context['default_operation_id'])
            
            # Auto-fill concept code from payment instrument
            if operation.payment_instrument_id and operation.payment_instrument_id.bcra_concept_code:
                res['concept_code'] = operation.payment_instrument_id.bcra_concept_code
        
        return res
```

---

## 6. Comparación de Propuestas

| Aspecto | Propuesta A | Propuesta B | Propuesta C | Propuesta D |
|---------|-------------|-------------|-------------|-------------|
| **Complejidad** | ⭐⭐ Media | ⭐ Baja | ⭐⭐⭐ Alta | ⭐⭐⭐⭐ Muy Alta |
| **Flexibilidad** | ⭐⭐ Media | ⭐⭐⭐ Alta | ⭐⭐⭐⭐ Muy Alta | ⭐⭐⭐⭐⭐ Máxima |
| **UX Intuitivo** | ⭐⭐⭐⭐ Muy Bueno | ⭐⭐ Regular | ⭐⭐⭐⭐ Muy Bueno | ⭐⭐ Regular |
| **Data Integrity** | ⭐⭐⭐ Buena | ⭐⭐⭐⭐ Muy Buena | ⭐⭐⭐ Buena | ⭐⭐ Regular |
| **Searchable** | ✅ Sí | ❌ No | ✅ Sí | ✅ Sí |
| **Tree View** | ✅ Sí | ❌ No (computed) | ✅ Sí | ✅ Sí |
| **Validación Temprana** | ✅ Sí | ❌ No | ⚠️ Warning | ⚠️ Parcial |
| **Override en MULC** | ❌ No | N/A | ✅ Sí | ✅ Sí |
| **Mantenimiento** | ⭐⭐⭐ Fácil | ⭐⭐⭐⭐ Muy Fácil | ⭐⭐ Regular | ⭐ Difícil |

---

## 7. Recomendación Final

### 🏆 Propuesta C - Banco en Operación + Propagación Inteligente

**Justificación:**

1. **UX Óptimo:**
   - Usuario define banco en operación (contexto correcto)
   - Se propaga automáticamente a MULC (conveniencia)
   - Pero puede cambiar si necesario (flexibilidad)

2. **Validación Inteligente:**
   - Warning (no error) si L/C sin banco → usuario puede proceder si necesario
   - Validación BCRA automática: payment_timing.days vs MULC.days_since_shipment
   - Indicador visual si banco MULC ≠ banco nominado

3. **Integración Completa:**
   - Payment Instrument → requires_bank_intervention (automático)
   - Payment Timing → MULC due_date (auto-fill)
   - Payment Timing → BCRA validation (constraint en MULC.approve)
   - Nominated Bank → MULC bank_partner_id (default)

4. **Tree View:**
   - `payment_terms_display`: "L/C - 180 días"
   - `nominated_bank_id`: "Banco Nación"
   - Ambos campos visibles y ordenables

5. **Casos de Uso Cubiertos:**
   - **Caso Común:** L/C 180d + Banco Nación → todo automático
   - **Edge Case:** TT sin banco → warning pero no bloquea
   - **Override:** MULC puede usar banco diferente si necesario
   - **Validación:** MULC a 190 días con timing 180d → error BCRA

---

## 8. Plan de Implementación

### Fase 1: Banco Nominado en Operación
- [ ] Agregar campo `nominated_bank_id` a `comex.operation`
- [ ] Agregar campo computado `requires_bank_intervention`
- [ ] Agregar onchange warning si L/C sin banco
- [ ] Actualizar form view (Financial page)
- [ ] Actualizar tree view (columna opcional)

### Fase 2: Propagación a MULC
- [ ] Modificar `comex_mulc.default_get()` para bank default
- [ ] Agregar campo `uses_nominated_bank` (indicador)
- [ ] Actualizar form view de MULC
- [ ] Actualizar tree view de MULC

### Fase 3: Validación BCRA
- [ ] Agregar campo `is_within_bcra_limit` a MULC
- [ ] Agregar método `_compute_is_within_bcra_limit()`
- [ ] Agregar constraint en `action_approve()` de MULC
- [ ] Decoration en tree view (rojo si fuera de límite)

### Fase 4: Auto-fill Inteligente
- [ ] MULC due_date desde payment_timing.days
- [ ] MULC concept_code desde payment_instrument.bcra_concept_code
- [ ] Suggested values en form view

### Fase 5: Reportes y Analytics
- [ ] Dashboard: operaciones por payment instrument
- [ ] Alerta: MULC próximos a vencer
- [ ] Reporte: operaciones fuera de límite BCRA

---

## 9. Casos de Uso Ejemplo

### Caso 1: Importación con L/C 180 días

```
Operación:
- Payment Instrument: L/C
- Payment Timing: 180 días
- Nominated Bank: Banco Nación
- requires_bank_intervention: True (automático)

Embarque: 2026-01-15

MULC (creado desde operación):
- bank_partner_id: Banco Nación (default automático)
- due_date: 2026-07-14 (180 días post-embarque, automático)
- max_days_allowed: 180 (desde payment_timing)

Si MULC solicitado 2026-07-20 (185 días):
→ ERROR: "MULC requested 185 days after shipment, but payment timing 
         allows maximum 180 days per BCRA regulations"
```

### Caso 2: TT Vista sin banco

```
Operación:
- Payment Instrument: TT
- Payment Timing: A la Vista
- Nominated Bank: (vacío)
- requires_bank_intervention: False

→ WARNING al save: "TT puede requerir banco. Considere nominar uno."
→ Usuario puede ignorar y continuar

MULC:
- bank_partner_id: (puede seleccionar manualmente)
- due_date: fecha embarque (0 días)
```

### Caso 3: D/A 90 días, banco cambia en MULC

```
Operación:
- Payment Instrument: D/A
- Payment Timing: 90 días
- Nominated Bank: Banco Galicia

MULC:
- bank_partner_id: Banco ICBC (override manual)
- uses_nominated_bank: False (indicador)
→ Form muestra badge: "⚠️ Using different bank"
```

---

## 10. Conclusión

La **Propuesta C** ofrece el mejor balance entre:
- Usabilidad (UX intuitivo)
- Flexibilidad (permite overrides)
- Validación (BCRA compliance)
- Mantenimiento (lógica clara)

La integración completa de Payment Terms + MULC + Banco Nominado proporciona:
1. **Validación automática** (BCRA limits, bank requirements)
2. **Auto-fill inteligente** (due dates, concept codes, banks)
3. **Visibilidad completa** (tree views, indicators, warnings)
4. **Trazabilidad** (tracking de todos los campos críticos)

---

**Próximo Paso:** Implementar Propuesta C en fases secuenciales, comenzando por Fase 1 (banco nominado en operación).
