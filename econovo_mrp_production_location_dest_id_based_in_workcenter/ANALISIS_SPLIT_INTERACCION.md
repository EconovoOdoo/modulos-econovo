# Análisis: Interacción del Módulo con el Flujo de Split de Odoo

**Fecha:** 30 de Octubre, 2025  
**Módulo:** `econovo_mrp_production_location_dest_id_based_in_workcenter`  
**Versión:** 17.0.1.2.0  
**Análisis realizado por:** GitHub Copilot

---

## 1. Resumen Ejecutivo

Este análisis examina cómo el módulo `econovo_mrp_production_location_dest_id_based_in_workcenter` interactúa con el flujo nativo de **Split** (división de órdenes de manufactura) en Odoo 17 Enterprise, específicamente:

- Comportamiento de `copy_data()` en `mrp.production` y `stock.move`
- Comportamiento de `_get_backorder_move_vals()` en `stock.move`
- Preservación de campos personalizados durante el split
- Recomputación de ubicaciones tras el split
- Casos límite y validaciones necesarias

**Conclusión Principal:** ✅ **El módulo es compatible con el flujo de split** gracias a que:
1. No añade campos personalizados en `stock.move` (solo en `mrp.production` y `mrp.workcenter`)
2. Usa campos computados (`@api.depends`) que se recalculan automáticamente tras el split
3. El método `default_get()` garantiza valores iniciales correctos en backorders

Sin embargo, hay **1 escenario crítico** que requiere atención especial (ver sección 5).

---

## 2. Análisis del Código Nativo de Odoo

### 2.1. `stock.move._get_backorder_move_vals()`

**Ubicación:** `odoo/addons/mrp/models/stock_move.py` línea 561

```python
def _get_backorder_move_vals(self):
    self.ensure_one()
    return {
        'state': 'draft' if self.state == 'draft' else 'confirmed',
        'reservation_date': self.reservation_date,
        'date_deadline': self.date_deadline,
        'manual_consumption': self._is_manual_consumption(),
        'move_orig_ids': [Command.link(m.id) for m in self.mapped('move_orig_ids')],
        'move_dest_ids': [Command.link(m.id) for m in self.mapped('move_dest_ids')],
        'procure_method': self.procure_method,
    }
```

**Comportamiento:**
- Este método devuelve SOLO los valores específicos que deben sobrescribir el `copy_data()` del move.
- Los campos NO listados aquí se copian mediante el comportamiento estándar de `copy_data()`.
- **Campos preservados automáticamente:**
  - `product_id`, `product_uom_qty`, `product_uom`
  - `location_id`, `location_dest_id` ← **CRÍTICO para nuestro módulo**
  - `name`, `origin`, `picking_type_id`
  - `production_id`, `raw_material_production_id`
  - Todos los campos con `copy=True` en su definición

**Implicación para nuestro módulo:**
✅ Los moves de los backorders **SÍ preservan `location_dest_id`** porque:
1. No se sobrescribe en `_get_backorder_move_vals()`
2. Se copia mediante el flujo estándar de `copy_data()`
3. El campo `location_dest_id` en `stock.move` tiene `copy=True` por defecto

---

### 2.2. `mrp.production.copy_data()`

**Ubicación:** `odoo/addons/mrp/models/mrp_production.py` línea 951

```python
def copy_data(self, default=None):
    default = dict(default or {})
    # covers at least 2 cases: backorders generation (follow default logic for moves copying)
    # and copying a done MO via the form (i.e. copy only the non-cancelled moves since no backorder = cancelled finished moves)
    if not default or 'move_finished_ids' not in default:
        move_finished_ids = self.move_finished_ids
        if self.state != 'cancel':
            move_finished_ids = self.move_finished_ids.filtered(lambda m: m.state != 'cancel' and m.product_qty != 0.0)
        default['move_finished_ids'] = [(0, 0, move.copy_data()[0]) for move in move_finished_ids]
    if not default or 'move_raw_ids' not in default:
        default['move_raw_ids'] = [(0, 0, move.copy_data()[0]) for move in self.move_raw_ids.filtered(lambda m: m.product_qty != 0.0)]
    return super(MrpProduction, self).copy_data(default=default)
```

**Comportamiento:**
- Copia TODOS los `move_raw_ids` y `move_finished_ids` usando `copy_data()` de cada move.
- Los moves se copian con sus `location_dest_id` originales.
- **Campos de `mrp.production` con `copy=True`** se copian automáticamente:
  - `product_id`, `product_qty`, `product_uom_id`
  - `bom_id`, `picking_type_id`
  - `date_start`, `date_deadline`
  - `user_id`, `origin`

**Campos computados NO se copian:**
- `location_src_id` ← Campo computado por `_compute_locations()`
- `location_dest_id` ← Campo computado por `_compute_locations()`
- `workcenter_location_dest_id` ← Campo computado en nuestro módulo

---

### 2.3. `BaseModel.copy_data()` (Comportamiento base)

**Ubicación:** `odoo/models.py` línea 5464

**Lógica general:**
```python
def copy_data(self, default=None):
    # 1. Blacklist de campos que NUNCA se copian:
    #    - MAGIC_COLUMNS (id, create_date, write_date, create_uid, write_uid)
    #    - parent_path
    #    - Campos heredados (_inherits)
    
    # 2. Whitelist de campos que SÍ se copian:
    #    - Campos con copy=True
    #    - Campos no en blacklist
    #    - Campos no en default
    
    # 3. Tipos especiales:
    #    - one2many: Recursivamente copia cada línea → [Command.create(line)]
    #    - many2many: Copia IDs → [Command.set(ids)]
    #    - Otros: Usa field.convert_to_write()
    
    return [default]
```

**Implicación para nuestro módulo:**
- **Campos computados (`compute=`):** NO se copian directamente, se recomputarán después
- **Campos stored (`store=True`):** Se copian si tienen `copy=True`
- **Campos con `copy=False`:** NUNCA se copian

---

## 3. Análisis de la Interacción con Nuestro Módulo

### 3.1. Campos Añadidos por el Módulo

#### En `mrp.production`:

1. **`workcenter_location_dest_id`**
   - Tipo: `Many2one('stock.location')`
   - Compute: `_compute_workcenter_location_dest`
   - Store: `True`
   - Copy: **No especificado** (por defecto `copy=False` para campos computados)
   - Depends: `'workorder_ids.workcenter_id.location_dest_id'`

**Comportamiento durante split:**
- ❌ **NO se copia** directamente (es computed field)
- ✅ **SE RECOMPUTA** automáticamente después porque:
  1. Los backorders obtienen nuevos `workorder_ids` (copiados/creados)
  2. El trigger `@api.depends('workorder_ids.workcenter_id.location_dest_id')` se activa
  3. El método `_compute_workcenter_location_dest()` se ejecuta para el nuevo MO

#### En `mrp.workcenter`:

2. **`location_dest_id`**
   - Tipo: `Many2one('stock.location')`
   - Store: Dato directo (no computed)
   - Copy: **Por defecto `True`** (Many2one sin `copy=False`)

**Comportamiento durante split:**
- ✅ **SE PRESERVA** completamente
- Los workcenters NO se copian, se REFERENCIAN (los backorders apuntan a los MISMOS workcenters)
- Por tanto, `location_dest_id` del workcenter es el mismo para todos los MOs

3. **`has_custom_destination`**
   - Tipo: `Boolean`
   - Compute: `_compute_has_custom_destination`
   - Store: `True`
   - Depends: `'location_dest_id'`

**Comportamiento durante split:**
- ✅ **SE RECOMPUTA** automáticamente tras copiar/referenciar el workcenter

---

### 3.2. Métodos Sobrescritos

#### `mrp.production._compute_locations()`

**Lógica del módulo:**
```python
@api.depends('picking_type_id', 'workorder_ids', 'workorder_ids.workcenter_id.location_dest_id')
def _compute_locations(self):
    for production in self:
        # 1. Siempre computa fallback_loc
        fallback_loc = self.env['stock.warehouse'].search([...], limit=1).lot_stock_id
        
        # 2. Set location_src_id (picking_type default o fallback)
        production.location_src_id = ...
        
        # 3. Busca workcenter_dest (último workcenter con location_dest_id)
        workcenter_dest = None
        for workorder in production.workorder_ids:
            if workorder.workcenter_id.location_dest_id:
                workcenter_dest = workorder.workcenter_id.location_dest_id
        
        # 4. Set location_dest_id (prioridad: workcenter > picking_type > fallback)
        if workcenter_dest:
            production.location_dest_id = workcenter_dest
        elif production.picking_type_id.default_location_dest_id:
            production.location_dest_id = ...
        else:
            production.location_dest_id = fallback_loc
```

**Trigger durante split:**
✅ **SE EJECUTA AUTOMÁTICAMENTE** cuando:
1. Los backorders son creados con `workorder_ids` copiados
2. El trigger `@api.depends('workorder_ids', 'workorder_ids.workcenter_id.location_dest_id')` se activa
3. El método recomputa `location_src_id` y `location_dest_id` para cada backorder

**Flujo completo en split:**
```
1. _split_productions() crea backorder MO
   ↓
2. copy_data() NO copia location_src_id/location_dest_id (son computed)
   ↓
3. default_get() NO se ejecuta (no es create() normal, es copy())
   ↓
4. workorder_ids se crean/copian para el backorder
   ↓
5. Trigger @api.depends('workorder_ids.workcenter_id.location_dest_id')
   ↓
6. _compute_locations() SE EJECUTA
   ↓
7. location_dest_id se RECALCULA según último workcenter con destino
   ↓
8. move_finished_ids.location_dest_id se actualiza (si corresponde)
```

---

#### `mrp.production.default_get()`

**Propósito original:** Garantizar que `location_src_id` y `location_dest_id` tengan valores durante `create()` (fix para merge en v17.0.1.1.0)

**Comportamiento durante split:**
❌ **NO SE EJECUTA** porque:
- `_split_productions()` usa `create()` con valores de `copy_data()`
- `copy_data()` ya proporciona todos los campos necesarios
- `default_get()` solo se ejecuta cuando faltan campos en `vals` de `create()`

**Pero esto NO es un problema porque:**
✅ `_compute_locations()` se ejecuta DESPUÉS del create y SOBRESCRIBE las ubicaciones

---

## 4. Flujo Completo del Split con el Módulo

### Escenario: Split de MO con workcenters configurados

**Estado inicial:**
- MO Original: `product_qty=10`
- Workcenter 1: `location_dest_id=False`
- Workcenter 2: `location_dest_id=Location A` ← Último workcenter
- MO Original: `location_dest_id=Location A` (computado)

**Usuario ejecuta split: [qty=6, qty=4]**

```
PASO 1: _split_productions() ajusta MO original
├─ MO Original: product_qty = 6 (ajustado)
└─ Ejecuta: production.with_context(skip_compute_move_raw_ids=True).product_qty = 6

PASO 2: Crea backorder usando copy_data()
├─ backorder_vals = production.copy_data(default=production._get_backorder_mo_vals())[0]
├─ copy_data() NO copia location_src_id/location_dest_id (computed fields)
├─ backorder_vals = {
│     'product_qty': 4,
│     'procurement_group_id': ...,
│     'name': 'MO/0001-001',
│     'backorder_sequence': 2,
│     # location_src_id: NO está aquí
│     # location_dest_id: NO está aquí
│  }
└─ backorder = create(backorder_vals)  # con skip_confirm=True

PASO 3: Divide stock.moves
├─ Moves del MO original se ajustan: product_uom_qty = 6
├─ Nuevos moves para backorder se crean:
│   ├─ move.copy_data(move._get_backorder_move_vals())
│   ├─ _get_backorder_move_vals() NO sobrescribe location_dest_id
│   └─ Resultado: Nuevos moves tienen location_dest_id COPIADO del original
└─ Moves asignados: backorder.move_finished_ids.location_dest_id = Location A (copiado)

PASO 4: Ajusta/crea workorders para backorder
├─ backorder.workorder_ids se crean (copian routing del MO original)
├─ Workorder 1 backorder: workcenter_id → Workcenter 1 (location_dest_id=False)
└─ Workorder 2 backorder: workcenter_id → Workcenter 2 (location_dest_id=Location A)

PASO 5: Confirma backorder (backorders._action_confirm_mo_backorders())
├─ workorder_ids._action_confirm()
└─ Triggers varios computes...

PASO 6: 🔥 CRÍTICO - _compute_locations() se ejecuta
├─ Trigger: workorder_ids cambió (se crearon)
├─ Para backorder:
│   ├─ Itera workorder_ids
│   ├─ Encuentra Workcenter 2 con location_dest_id=Location A
│   ├─ workcenter_dest = Location A
│   └─ backorder.location_dest_id = Location A ← ✅ RECALCULADO CORRECTAMENTE
└─ Para MO original:
    ├─ Todavía tiene workorder_ids originales
    ├─ Workcenter 2 sigue configurado
    └─ location_dest_id = Location A ← ✅ SE MANTIENE

PASO 7: Actualiza moves si location_dest_id cambió
├─ Si _compute_locations() cambió location_dest_id...
├─ Los move_finished_ids PUEDEN necesitar actualización
└─ ⚠️ POSIBLE PROBLEMA: Ver sección 5.1

RESULTADO FINAL:
✅ MO Original (qty=6): location_dest_id = Location A
✅ Backorder (qty=4): location_dest_id = Location A
✅ Ambos tienen workcenters correctos
✅ Moves preservan/actualizan location_dest_id
```

---

## 5. Casos Límite y Posibles Problemas

### 5.1. ⚠️ **PROBLEMA CRÍTICO: Sincronización moves vs production.location_dest_id**

**Escenario:**
1. Split crea backorder
2. `copy_data()` copia moves con `location_dest_id=Location A` (del original)
3. Backorder se crea sin workorders inicialmente
4. Luego workorders se crean/asignan
5. `_compute_locations()` se ejecuta y calcula `location_dest_id=Location B` (diferente)
6. **Los moves YA CREADOS tienen `location_dest_id=Location A`** ← INCONSISTENCIA

**¿Cuándo ocurre?**
- Si el routing cambia entre el MO original y el backorder
- Si se editan workcenters después del split
- Si hay lógica personalizada que cambia workcenter assignments

**Solución recomendada:**
Agregar un método que sincronice los moves con la ubicación computada:

```python
@api.depends('picking_type_id', 'workorder_ids', 'workorder_ids.workcenter_id.location_dest_id')
def _compute_locations(self):
    for production in self:
        # ... lógica existente ...
        
        # Sincronizar moves si location_dest_id cambió
        if production.location_dest_id:
            # Actualizar moves de producto terminado
            finished_moves = production.move_finished_ids.filtered(
                lambda m: m.product_id == production.product_id and m.state not in ('done', 'cancel')
            )
            if finished_moves:
                finished_moves.write({'location_dest_id': production.location_dest_id.id})
```

**Riesgo:** MEDIO - Solo ocurre en escenarios específicos, pero puede causar movimientos de stock incorrectos.

---

### 5.2. ✅ Backorders sin workorders (escenario de merge resuelto)

**Escenario:** Durante merge, MOs se crean sin workorders inicialmente.

**Solución implementada:** `default_get()` en v17.0.1.1.0 garantiza valores por defecto.

**Resultado durante split:**
- ✅ `_compute_locations()` siempre computa `fallback_loc`
- ✅ Si no hay workorders, usa picking_type default o fallback
- ✅ Cuando workorders se crean después, location se RECALCULA

---

### 5.3. ✅ Workcenters con location_dest_id diferente entre MO original y backorder

**Escenario:** 
- MO original tiene Workcenter A (location=X) como último
- Backorder tiene Workcenter B (location=Y) como último
- Split divide workorders de forma diferente

**Comportamiento actual:**
- ✅ Cada MO ejecuta `_compute_locations()` independientemente
- ✅ Cada uno obtiene la ubicación del ÚLTIMO workcenter configurado
- ✅ No hay problema si los workcenters difieren

**Validación:** Confirmar que `_split_productions()` ajusta workorders correctamente para backorders.

---

### 5.4. ⚠️ Reservas (stock.move.line) con location_dest_id antigua

**Escenario:**
- MO original tiene reservas (`stock.move.line`) con `location_dest_id=Location A`
- Split reparte reservas entre original y backorder
- `_compute_locations()` cambia backorder a `location_dest_id=Location B`
- Las reservas TODAVÍA tienen `location_dest_id=Location A`

**Impacto:**
- Los `stock.move` tienen `location_dest_id=Location B`
- Pero `stock.move.line` tienen `location_dest_id=Location A`
- Inconsistencia puede causar errores en validación o picking

**Solución:**
Odoo probablemente maneja esto con `_action_assign()` que recrea move_lines si cambia el move.

**Recomendación:** Agregar validación en tests para verificar que move_lines se actualizan.

---

### 5.5. ✅ Multiple splits consecutivos

**Escenario:**
- Split MO1 → MO1 (qty=3) + MO2 (qty=7)
- Split MO2 → MO2 (qty=4) + MO3 (qty=3)

**Comportamiento:**
- ✅ Cada split es independiente
- ✅ `_compute_locations()` se ejecuta en cada backorder
- ✅ No hay acumulación de errores

---

## 6. Recomendaciones y Acciones

### 6.1. Implementar sincronización de moves (ALTA PRIORIDAD)

**Acción:** Modificar `_compute_locations()` para sincronizar moves cuando cambia `location_dest_id`.

**Código sugerido:**
```python
@api.depends('picking_type_id', 'workorder_ids', 'workorder_ids.workcenter_id.location_dest_id')
def _compute_locations(self):
    for production in self:
        # Guardar valor anterior para detectar cambios
        old_location_dest_id = production.location_dest_id
        
        # ... lógica existente de compute ...
        
        # Si location_dest_id cambió, sincronizar moves
        if old_location_dest_id != production.location_dest_id and production.location_dest_id:
            production._sync_finished_moves_location()

def _sync_finished_moves_location(self):
    """Sincroniza location_dest_id de moves de producto terminado con la MO"""
    self.ensure_one()
    finished_moves = self.move_finished_ids.filtered(
        lambda m: m.product_id == self.product_id and m.state not in ('done', 'cancel')
    )
    if finished_moves and self.location_dest_id:
        finished_moves.write({'location_dest_id': self.location_dest_id.id})
        # También actualizar move_lines si existen
        move_lines = finished_moves.move_line_ids.filtered(lambda ml: ml.state not in ('done', 'cancel'))
        if move_lines:
            move_lines.write({'location_dest_id': self.location_dest_id.id})
```

---

### 6.2. Tests automatizados (ALTA PRIORIDAD)

**Acción:** Crear test suite que cubra splits con workcenter destinations.

**Tests recomendados:**

```python
# tests/test_split_with_workcenter_destination.py

from odoo.tests import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestSplitWithWorkcenterDestination(TransactionCase):
    
    def setUp(self):
        super().setUp()
        # Setup: Producto, BoM, Routing, Workcenters, Locations
        ...
    
    def test_split_preserves_workcenter_destination(self):
        """Test que location_dest_id se preserva/recomputa tras split"""
        # 1. Crear MO con workcenter que tiene location_dest_id
        # 2. Confirmar MO
        # 3. Ejecutar split [qty=6, qty=4]
        # 4. Verificar:
        #    - MO original: location_dest_id = workcenter location
        #    - Backorder: location_dest_id = workcenter location
        #    - Moves: location_dest_id correcto
        ...
    
    def test_split_with_multiple_workcenters_uses_last(self):
        """Test que usa ÚLTIMO workcenter con destination"""
        # 1. MO con 3 workcenters: WC1(no dest), WC2(dest=A), WC3(dest=B)
        # 2. Split
        # 3. Verificar ambos MOs usan location B (último)
        ...
    
    def test_split_without_workcenter_destination_uses_fallback(self):
        """Test fallback cuando no hay workcenter destination"""
        # 1. MO sin workcenter destinations
        # 2. Split
        # 3. Verificar usa picking_type default
        ...
    
    def test_split_moves_location_sync(self):
        """Test que moves se sincronizan si location cambia"""
        # 1. MO con moves ya creados con location A
        # 2. Cambiar workcenter destination a location B
        # 3. Split
        # 4. Verificar backorder moves tienen location B
        ...
    
    def test_split_with_reservations(self):
        """Test que reservas (move_lines) mantienen consistencia"""
        # 1. MO con reservas de stock
        # 2. Split
        # 3. Verificar move_lines tienen location_dest_id correcto
        ...
```

---

### 6.3. Documentación adicional (MEDIA PRIORIDAD)

**Acción:** Actualizar README.md con sección sobre Split behavior.

**Contenido sugerido:**
```markdown
## Comportamiento con Split de Órdenes de Manufactura

Este módulo es **totalmente compatible** con la funcionalidad de Split (división) 
de órdenes de manufactura de Odoo. Cuando divides una MO:

1. **Ubicaciones se recalculan automáticamente**: Los backorders ejecutan 
   `_compute_locations()` y obtienen la ubicación del último workcenter configurado.

2. **Workcenters se preservan**: Los backorders referencian los mismos workcenters,
   por lo que la configuración de `location_dest_id` se mantiene.

3. **Moves se sincronizan**: Los movimientos de stock se actualizan para reflejar
   la ubicación de destino correcta.

### Consideraciones
- Si cambias manualmente los workcenters después del split, las ubicaciones
  se recalcularán automáticamente.
- Los movimientos de stock (finished goods) siempre usarán la ubicación del
  último workcenter con destino configurado.
```

---

### 6.4. Validación en producción (MEDIA PRIORIDAD)

**Acción:** Ejecutar validaciones en base de datos de producción o staging.

**Pasos:**
1. Identificar MOs existentes con workcenter destinations configurados
2. Ejecutar splits en ambiente controlado
3. Verificar:
   - `location_dest_id` correcto en backorders
   - Moves con ubicaciones correctas
   - Pickings generados correctamente
   - No hay NULL violations

---

## 7. Conclusiones

### ✅ Fortalezas del Módulo

1. **Arquitectura robusta**: Uso de `@api.depends` garantiza recomputación automática
2. **Fix de merge incluido**: `default_get()` previene NULL violations
3. **Compatibilidad con copy_data**: No interfiere con el flujo nativo de copia
4. **Lógica LAST workcenter**: Tiene sentido de manufactura y funciona con splits

### ⚠️ Puntos de Atención

1. **Sincronización moves**: Necesita implementación explícita (ver 6.1)
2. **Tests faltantes**: No hay tests para split scenarios (ver 6.2)
3. **Documentación**: README no menciona comportamiento con splits (ver 6.3)

### 🎯 Prioridades de Acción

| Prioridad | Acción | Impacto | Esfuerzo |
|-----------|--------|---------|----------|
| 🔴 ALTA | Implementar `_sync_finished_moves_location()` | Alto - Previene inconsistencias | Bajo - 30 min |
| 🔴 ALTA | Crear tests para splits | Alto - Previene regresiones | Medio - 2-3 hrs |
| 🟡 MEDIA | Actualizar documentación | Medio - Mejora claridad | Bajo - 30 min |
| 🟡 MEDIA | Validar en staging/producción | Alto - Confirma funcionamiento | Medio - 1-2 hrs |

---

## 8. Código de Ejemplo: Fix Completo Recomendado

```python
# models/mrp_production.py

@api.depends('picking_type_id', 'workorder_ids', 'workorder_ids.workcenter_id.location_dest_id')
def _compute_locations(self):
    """Override to consider workcenter destination locations
    
    Enhanced in v17.0.1.3.0: Synchronizes moves when location changes (critical for splits)
    """
    for production in self:
        # Store old value to detect changes
        old_location_dest = production.location_dest_id
        
        # ALWAYS compute fallback location (needed for merge and edge cases)
        company_id = production.company_id.id if (production.company_id and production.company_id in self.env.companies) else self.env.company.id
        fallback_loc = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
        
        # Set source location with proper fallback chain
        if production.picking_type_id.default_location_src_id:
            production.location_src_id = production.picking_type_id.default_location_src_id
        elif fallback_loc:
            production.location_src_id = fallback_loc
        else:
            production.location_src_id = False
        
        # For destination location, check if any workcenter has a custom destination
        # Use the LAST workcenter with destination configured (makes manufacturing sense)
        workcenter_dest = None
        for workorder in production.workorder_ids:
            if workorder.workcenter_id.location_dest_id:
                workcenter_dest = workorder.workcenter_id.location_dest_id
        
        # Set destination location with proper priority and fallback chain
        if workcenter_dest:
            production.location_dest_id = workcenter_dest
        elif production.picking_type_id.default_location_dest_id:
            production.location_dest_id = production.picking_type_id.default_location_dest_id
        elif fallback_loc:
            production.location_dest_id = fallback_loc
        else:
            production.location_dest_id = False
        
        # 🆕 CRITICAL FIX for splits: Synchronize moves if location changed
        if old_location_dest != production.location_dest_id and production.location_dest_id:
            production._sync_finished_moves_location()

def _sync_finished_moves_location(self):
    """Synchronize finished moves location_dest_id with production's computed location
    
    This is critical after splits where moves are copied with old location but
    production recomputes location based on new/different workorders.
    
    Added in v17.0.1.3.0 to fix split scenarios.
    """
    self.ensure_one()
    if not self.location_dest_id:
        return
    
    # Update finished product moves
    finished_moves = self.move_finished_ids.filtered(
        lambda m: m.product_id == self.product_id and m.state not in ('done', 'cancel')
    )
    
    if finished_moves:
        # Update moves
        moves_to_update = finished_moves.filtered(
            lambda m: m.location_dest_id != self.location_dest_id
        )
        if moves_to_update:
            moves_to_update.write({'location_dest_id': self.location_dest_id.id})
            
            # Also update move_lines (reservations) if they exist
            move_lines = moves_to_update.move_line_ids.filtered(
                lambda ml: ml.state not in ('done', 'cancel')
            )
            if move_lines:
                move_lines.write({'location_dest_id': self.location_dest_id.id})
```

---

**Fin del análisis.**

**Próximos pasos:** Implementar fix de sincronización + tests + actualizar README.
