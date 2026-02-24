# Implementación: Tipos de Operación de Tránsito BA ↔ CBA

**Fecha**: 2026-02-23  
**Estado**: ✅ Implementado en STAGING — ✅ Implementado en PRODUCCIÓN  
**Responsable**: -  
**Ambiente staging**: https://econovo-pruebas.odoo.com  
**Ambiente producción**: https://econovo.odoo.com

### IDs creados en Staging

| Elemento | ID | Descripción |
|----|----|----|
| `stock.picking.type` | **192** | OSEYS: Envío a Bs.As. (TEBA) |
| `stock.picking.type` | **193** | OSEYS: Llegada desde Bs.As. (TLBA) |
| `stock.picking.type` | **194** | ALSUC: Envío a Cba. (TECO) |
| `stock.picking.type` | **195** | ALSUC: Llegada desde Cba. (TLCO) |
| `stock.picking.type` | **196** | AGROV: Envío a Bs.As. (TEBA) |
| `stock.picking.type` | **197** | AGROV: Llegada desde Bs.As. (TLBA) |
| `stock.picking.type` | **198** | ASAGR: Envío a Cba. (TECO) |
| `stock.picking.type` | **199** | ASAGR: Llegada desde Cba. (TLCO) |
| `stock.rule` **278** → `picking_type_id` | **195** | ALSUC: Llegada desde Cba. (TLCO) |
| `stock.rule` **280** → `picking_type_id` | **193** | OSEYS: Llegada desde Bs.As. (TLBA) |
| `stock.rule` **282** → `picking_type_id` | **199** | ASAGR: Llegada desde Cba. (TLCO) |
| `stock.rule` **285** → `picking_type_id` | **197** | AGROV: Llegada desde Bs.As. (TLBA) |
| `base.automation` | **26** | PASO 3: Asignar grupo único al saliente (on_create TEBA/TECO) |
| `base.automation` | **27** | PASO 4: Propagar remito al origin de la llegada (on_write vouchers) |
| `base.automation` | **28** | PASO 4b: Copiar group_id desde saliente a llegada (on_create TLBA/TLCO) |

### IDs creados en Producción

| Elemento | ID | Descripción |
|----|----|----|
| `stock.picking.type` | **188** | OSEYS: Envíos a Bs.As. (TEBA) |
| `stock.picking.type` | **189** | OSEYS: Llegadas desde Bs.As. (TLBA) |
| `stock.picking.type` | **190** | ALSUC: Envíos a Cba. (TECO) |
| `stock.picking.type` | **191** | ALSUC: Llegadas desde Cba. (TLCO) |
| `stock.picking.type` | **192** | AGROV: Envíos a Bs.As. (TEBA) |
| `stock.picking.type` | **193** | AGROV: Llegadas desde Bs.As. (TLBA) |
| `stock.picking.type` | **194** | ASAGR: Envíos a Cba. (TECO) |
| `stock.picking.type` | **195** | ASAGR: Llegadas desde Cba. (TLCO) |
| `stock.rule` **278** → `picking_type_id` | **191** | ALSUC: Llegadas desde Cba. (TLCO) |
| `stock.rule` **280** → `picking_type_id` | **189** | OSEYS: Llegadas desde Bs.As. (TLBA) |
| `stock.rule` **282** → `picking_type_id` | **195** | ASAGR: Llegadas desde Cba. (TLCO) |
| `stock.rule` **285** → `picking_type_id` | **193** | AGROV: Llegadas desde Bs.As. (TLBA) |
| `base.automation` | **25** | PASO 3: Asignar grupo único al saliente (on_create TEBA/TECO) — `action_server_id`: 1906 |
| `base.automation` | **26** | PASO 4: Copiar remitos a llegada (on_write voucher_ids) — `action_server_id`: 1907 |
| `base.automation` | **27** | PASO 4b: Heredar grupo en llegada (on_create TLBA/TLCO) — `action_server_id`: 1908 |

---

## Contexto y problema

Los traslados entre ciudades (BA ↔ CBA) usan el mismo tipo de operación `INT (Traslados internos)` que los movimientos locales internos de cada almacén. Esto provoca que Odoo fusione (merge) los pickings de llegada desde tránsito cuando múltiples envíos independientes llegan al mismo destino sin un `procurement.group` que los diferencie.

**Resultado**: en vez de crear una recepción por cada camión, Odoo suma todos los productos en una sola recepción, mezclando remitos distintos.

**Causa raíz**: los pickings salientes creados manualmente tienen `group_id = False`. Las push rules tienen `group_propagation_option = propagate`, pero propagan `False` → todos los pickings de llegada comparten `group_id = False` → Odoo los fusiona.

**Solución**: crear 8 tipos de operación dedicados para tránsito inter-ciudad + asignar automáticamente un `procurement.group` único en cada picking saliente.

---

## Mapa de infraestructura actual

### Empresas y almacenes en scope

| ID | Código | Nombre | Empresa | Ciudad |
|----|--------|--------|---------|--------|
| 2  | OSEYS  | Oscar Scorza Equipos y Servicios | company id=2 | Córdoba |
| 10 | ALSUC  | Almacén Sucursal Bs. As. (ALSUC) | company id=2 | Buenos Aires |
| 1  | AGROV  | Econovo Agrovial                 | company id=1 | Córdoba |
| 11 | ASAGR  | Almacén Sucursal Bs. As. (Agrovial) | company id=1 | Buenos Aires |

### Ubicaciones de tránsito (ya existen, no crear)

| ID    | Nombre                          | Empresa    | Dirección |
|-------|---------------------------------|------------|-----------|
| 40691 | 02-Transito de Cba. a Bs.As.    | company=2  | CBA → BA  |
| 40692 | 03-Transito de Bs.As a Cba.     | company=2  | BA  → CBA |
| 40693 | 04-Transito de Cba. a Bs. As.   | company=1  | CBA → BA  |
| 40696 | 05-Transito de Bs.As. a Cba.    | company=1  | BA  → CBA |

### Ubicaciones de stock (ya existen, no crear)

| ID    | Nombre              |
|-------|---------------------|
| 26    | OSEYS/Existencias   |
| 38973 | ALSUC/Existencias   |
| 8     | AGROV/Existencias   |
| 40682 | ASAGR/Existencias   |

### Push rules existentes (solo se actualiza el `picking_type_id`)

| ID  | Nombre               | Ruta | Tránsito origen → Stock destino               |
|-----|----------------------|------|-----------------------------------------------|
| 278 | Llegada a Bs. As.    | 170  | loc 40691 → ALSUC/Existencias (38973)         |
| 280 | Llegada a Cba.       | 171  | loc 40692 → OSEYS/Existencias (26)            |
| 282 | Llegada a Bs. As,    | 172  | loc 40693 → ASAGR/Existencias (40682)         |
| 285 | Llegada a Cba.       | 174  | loc 40696 → AGROV/Existencias (8)             |

---

## PASO 1 — Crear 8 tipos de operación

> **Ruta UI**: Inventario → Configuración → Tipos de operaciones → Nuevo  
> **Tipo base a copiar**: cada uno como "Traslado interno" (`internal`)

### 🏢 Oscar Scorza — Envíos salientes

#### Tipo 1 — OSEYS: Envíos a Bs.As. (ID staging: 192)

| Campo | Valor |
|-------|-------|
| Nombre | `Envíos a Bs.As.` |
| Código de secuencia | `TEBA` |
| Almacén | `Oscar Scorza Equipos y Servicios S.R.L. (OSEYS)` |
| Tipo de operación | `Traslado interno` |
| Ubicación de origen por defecto | `OSEYS/Existencias` (ID 26) |
| Ubicación de destino por defecto | `02-Transito de Cba. a Bs.As.` (ID 40691) |
| Reservas | `Manual` |

#### Tipo 2 — ALSUC: Envíos a Cba. (ID staging: 194)

| Campo | Valor |
|-------|-------|
| Nombre | `Envíos a Cba.` |
| Código de secuencia | `TECO` |
| Almacén | `Almacén Sucursal Bs. As. (ALSUC)` |
| Tipo de operación | `Traslado interno` |
| Ubicación de origen por defecto | `ALSUC/Existencias` (ID 38973) |
| Ubicación de destino por defecto | `03-Transito de Bs.As a Cba.` (ID 40692) |
| Reservas | `Manual` |

---

### 🏢 Oscar Scorza — Llegadas (generadas por push rule)

#### Tipo 3 — ALSUC: Llegadas desde Cba. (ID staging: 195)

| Campo | Valor |
|-------|-------|
| Nombre | `Llegadas desde Cba.` |
| Código de secuencia | `TLCO` |
| Almacén | `Almacén Sucursal Bs. As. (ALSUC)` |
| Tipo de operación | `Traslado interno` |
| Ubicación de origen por defecto | `02-Transito de Cba. a Bs.As.` (ID 40691) |
| Ubicación de destino por defecto | `ALSUC/Existencias` (ID 38973) |
| Reservas | `Manual` |

#### Tipo 4 — OSEYS: Llegadas desde Bs.As. (ID staging: 193)

| Campo | Valor |
|-------|-------|
| Nombre | `Llegadas desde Bs.As.` |
| Código de secuencia | `TLBA` |
| Almacén | `Oscar Scorza Equipos y Servicios S.R.L. (OSEYS)` |
| Tipo de operación | `Traslado interno` |
| Ubicación de origen por defecto | `03-Transito de Bs.As a Cba.` (ID 40692) |
| Ubicación de destino por defecto | `OSEYS/Existencias` (ID 26) |
| Reservas | `Manual` |

---

### 🌿 Agrovial — Envíos salientes

#### Tipo 5 — AGROV: Envíos a Bs.As. (ID staging: 196)

| Campo | Valor |
|-------|-------|
| Nombre | `Envíos a Bs.As.` |
| Código de secuencia | `TEBA` |
| Almacén | `Econovo Agrovial` |
| Tipo de operación | `Traslado interno` |
| Ubicación de origen por defecto | `AGROV/Existencias` (ID 8) |
| Ubicación de destino por defecto | `04-Transito de Cba. a Bs. As.` (ID 40693) |
| Reservas | `Manual` |

#### Tipo 6 — ASAGR: Envíos a Cba. (ID staging: 198)

| Campo | Valor |
|-------|-------|
| Nombre | `Envíos a Cba.` |
| Código de secuencia | `TECO` |
| Almacén | `Almacén Sucursal Bs. As. (Agrovial)` |
| Tipo de operación | `Traslado interno` |
| Ubicación de origen por defecto | `ASAGR/Existencias` (ID 40682) |
| Ubicación de destino por defecto | `05-Transito de Bs.As. a Cba.` (ID 40696) |
| Reservas | `Manual` |

---

### 🌿 Agrovial — Llegadas (generadas por push rule)

#### Tipo 7 — ASAGR: Llegadas desde Cba. (ID staging: 199)

| Campo | Valor |
|-------|-------|
| Nombre | `Llegadas desde Cba.` |
| Código de secuencia | `TLCO` |
| Almacén | `Almacén Sucursal Bs. As. (Agrovial)` |
| Tipo de operación | `Traslado interno` |
| Ubicación de origen por defecto | `04-Transito de Cba. a Bs. As.` (ID 40693) |
| Ubicación de destino por defecto | `ASAGR/Existencias` (ID 40682) |
| Reservas | `Manual` |

#### Tipo 8 — AGROV: Llegadas desde Bs.As. (ID staging: 197)

| Campo | Valor |
|-------|-------|
| Nombre | `Llegadas desde Bs.As.` |
| Código de secuencia | `TLBA` |
| Almacén | `Econovo Agrovial` |
| Tipo de operación | `Traslado interno` |
| Ubicación de origen por defecto | `05-Transito de Bs.As. a Cba.` (ID 40696) |
| Ubicación de destino por defecto | `AGROV/Existencias` (ID 8) |
| Reservas | `Manual` |

---

## PASO 2 — Actualizar las 4 Push Rules

> **Ruta UI**: Inventario → Configuración → Rutas → abrir la ruta → pestaña Reglas → editar la regla  
> **Campo a cambiar**: únicamente `Tipo de operación`

| Push Rule ID | Ruta | Cambio `picking_type_id` → nuevo tipo |
|-------------|------|---------------------------------------|
| **278** | 02-Tránsito Cba→BA (Oscar Scorza) | `ALSUC: Llegadas desde Cba.` (TLCO) |
| **280** | 03-Tránsito BA→Cba (Oscar Scorza) | `OSEYS: Llegadas desde Bs.As.` (TLBA) |
| **282** | 04-Tránsito Cba→BA (Agrovial)     | `ASAGR: Llegadas desde Cba.` (TLCO) |
| **285** | 05-Tránsito BA→Cba (Agrovial)     | `AGROV: Llegadas desde Bs.As.` (TLBA) |

---

## PASO 3 — Acción Automática: asignar grupo único

> **Ruta UI**: Ajustes → Técnico → Acciones → Acciones automáticas → Nuevo

| Campo | Valor |
|-------|-------|
| Nombre | `Stock: Asignar grupo único a picking de tránsito saliente` |
| Modelo | `Picking de inventario (stock.picking)` |
| Cuándo ejecutar | `Creando registros` |
| Antes/Después | `Después` |
| Filtro del registro | `[["picking_type_id.sequence_code", "in", ["TEBA", "TECO"]], ["backorder_id", "=", False]]` |
| Tipo de acción | `Ejecutar código Python` |

**Código Python:**
```python
for record in records:
    if not record.group_id:
        group = env['procurement.group'].create({'name': record.name})
        record.write({'group_id': group.id})
```

> **Por qué funciona**: cada picking saliente recibe un `procurement.group` cuyo nombre coincide con el nombre del picking (ej: `ALSUC/TECO/00001`). La push rule tiene `group_propagation_option = propagate`, así que el picking de llegada hereda ese mismo `group_id`. Cuando Odoo busca si puede fusionar el nuevo picking de llegada con uno existente, compara `group_id` — como cada llegada tiene un grupo distinto, **nunca se fusionan**.

---

## PASO 4 — Acción automática: propagar remito a la llegada

> Propaga el remito (`voucher_ids`) al picking de llegada cuando el operativo lo asigna en el picking saliente (normalmente después de validarlo).
>
> **Campo `origin`**: Odoo setea `origin` automáticamente con el nombre del picking saliente (ej: `ALSUC/TECO/00005`) al crear la llegada vía push rule. Esta acción **no lo modifica** — ese valor es el correcto y permite trazar la llegada a su picking de origen.

| Campo | Valor |
|-------|-------|
| Nombre | `Stock: Propagar remito de tránsito al picking de llegada` |
| Modelo | `Picking de inventario (stock.picking)` |
| Cuándo ejecutar | `Cuando se actualiza un registro` |
| Campos a observar | `vouchers` |
| Filtro del registro | `[["picking_type_id.sequence_code", "in", ["TEBA", "TECO"]], ["voucher_ids", "!=", False]]` |
| Tipo de acción | `Ejecutar código Python` |

**Código Python:**
```python
for record in records:
    if not record.voucher_ids or not record.group_id:
        continue
    arrivals = env['stock.picking'].search([
        ('group_id', '=', record.group_id.id),
        ('id', '!=', record.id),
    ])
    if arrivals:
        arrivals.write({
            'voucher_ids': [(6, 0, record.voucher_ids.ids)],
        })
```

> **Nota**: `vouchers` (Char) es un campo computado de `voucher_ids` (Many2many). Al copiar `voucher_ids` a la llegada, el campo `vouchers` se actualiza automáticamente.
>
> El campo `origin` **no se modifica** aquí — Odoo lo setea automáticamente con el nombre del picking saliente (ej: `ALSUC/TECO/00005`) al crear la llegada vía push rule. Ese valor no debe sobreescribirse.

---

## PASO 4b — Acción automática: copiar group_id en la llegada

> **Causa raíz**: la push rule propaga `stock.move.group_id`, no `stock.picking.group_id`. Como PASO 3 setea el grupo en el picking pero no en los moves (que no existen al momento del `on_create`), la push rule propaga `False` al picking de llegada.
>
> **Solución**: acción que dispara `on_create` de los pickings de llegada (TLBA/TLCO). Odoo setea automáticamente el campo `origin` con el nombre del picking saliente, lo que permite localizar la fuente y copiar su `group_id`.

| Campo | Valor |
|-------|-------|
| Nombre | `Stock: Copiar grupo del picking saliente a la llegada de tránsito` |
| Modelo | `Picking de inventario (stock.picking)` |
| Cuándo ejecutar | `Creando registros` |
| Antes/Después | `Después` |
| Filtro del registro | `[["picking_type_id.sequence_code", "in", ["TLBA", "TLCO"]], ["backorder_id", "=", False]]` |
| Tipo de acción | `Ejecutar código Python` |

**Código Python:**
```python
for record in records:
    if not record.group_id and record.origin:
        source = env['stock.picking'].search([('name', '=', record.origin)], limit=1)
        if source and source.group_id:
            record.write({'group_id': source.group_id.id})
```

---

## PASO 5 — Secuencias generadas automáticamente

Odoo crea la secuencia automáticamente al guardar cada tipo de operación nuevo. Los nombres de secuencia serán:

| Warehouse | Seq code | Formato picking | Significado |
|-----------|----------|----------------|-------------|
| OSEYS     | TEBA     | `OSEYS/TEBA/00001` | Tránsito Envío a Buenos Aires |
| OSEYS     | TLBA     | `OSEYS/TLBA/00001` | Tránsito Llegada desde Buenos Aires |
| ALSUC     | TECO     | `ALSUC/TECO/00001` | Tránsito Envío a Córdoba |
| ALSUC     | TLCO     | `ALSUC/TLCO/00001` | Tránsito Llegada desde Córdoba |
| AGROV     | TEBA     | `AGROV/TEBA/00001` | Tránsito Envío a Buenos Aires |
| AGROV     | TLBA     | `AGROV/TLBA/00001` | Tránsito Llegada desde Buenos Aires |
| ASAGR     | TECO     | `ASAGR/TECO/00001` | Tránsito Envío a Córdoba |
| ASAGR     | TLCO     | `ASAGR/TLCO/00001` | Tránsito Llegada desde Córdoba |

---

## ✅ Checklist de implementación

### Tipos de operación — Oscar Scorza (company 2)
- [x] **1.1** Crear `OSEYS: Envíos a Bs.As.` (`TEBA`, src=26, dest=40691) — ID 192
- [x] **1.2** Crear `OSEYS: Llegadas desde Bs.As.` (`TLBA`, src=40692, dest=26) — ID 193
- [x] **1.3** Crear `ALSUC: Envíos a Cba.` (`TECO`, src=38973, dest=40692) — ID 194
- [x] **1.4** Crear `ALSUC: Llegadas desde Cba.` (`TLCO`, src=40691, dest=38973) — ID 195

### Tipos de operación — Agrovial (company 1)
- [x] **1.5** Crear `AGROV: Envíos a Bs.As.` (`TEBA`, src=8, dest=40693) — ID 196
- [x] **1.6** Crear `AGROV: Llegadas desde Bs.As.` (`TLBA`, src=40696, dest=8) — ID 197
- [x] **1.7** Crear `ASAGR: Envíos a Cba.` (`TECO`, src=40682, dest=40696) — ID 198
- [x] **1.8** Crear `ASAGR: Llegadas desde Cba.` (`TLCO`, src=40693, dest=40682) — ID 199

### Push rules
- [x] **2.1** Push rule **278** → `ALSUC: Llegadas desde Cba.` (TLCO, ID 195)
- [x] **2.2** Push rule **280** → `OSEYS: Llegadas desde Bs.As.` (TLBA, ID 193)
- [x] **2.3** Push rule **282** → `ASAGR: Llegadas desde Cba.` (TLCO, ID 199)
- [x] **2.4** Push rule **285** → `AGROV: Llegadas desde Bs.As.` (TLBA, ID 197)

### Acciones automáticas
- [x] **3.1** Crear acción `ON CREATE` para asignar `procurement.group` único (PASO 3) — base.automation ID 26
- [x] **4.1** Crear acción `ON WRITE vouchers` para propagar remito al picking de llegada (PASO 4) — base.automation ID 27
- [x] **4b.1** Crear acción `ON CREATE TLBA/TLCO` para copiar `group_id` desde el picking saliente (PASO 4b) — base.automation ID 28

### Tests de validación (Staging — 2026-02-24)
- [x] **TEST 1** `OSEYS/TEBA/00001` creado → `group_id=[10210,"OSEYS/TEBA/00001"]` asignado automáticamente ✅
- [x] **TEST 2** `OSEYS/TEBA/00002` creado → `group_id=[10211,"OSEYS/TEBA/00002"]` distinto al anterior ✅ (no merge)
- [x] **TEST 3** `vouchers="REM-TEST-0001-V2"` en saliente → `origin="REM-TEST-0001-V2"` propagado a la llegada ✅
- [x] **TEST 4** `ALSUC/TECO/00005` validado → push rule generó `OSEYS/TLBA/00003` con `origin="ALSUC/TECO/00005"` (Odoo nativo) → action 28 copió `group_id` ✅ → al asignar `voucher_ids`, action 27 copió `voucher_ids=[3]` a la llegada (sin tocar `origin`) ✅
- [x] **Prueba usuario** Oscar Scorza → "funcionando perfectamente" ✅

### Implementación Producción (2026-02-24)
- [x] **P-1.1** `OSEYS: Envíos a Bs.As.` (`TEBA`, src=26, dest=40691) — ID **188**
- [x] **P-1.2** `OSEYS: Llegadas desde Bs.As.` (`TLBA`, src=40692, dest=26) — ID **189**
- [x] **P-1.3** `ALSUC: Envíos a Cba.` (`TECO`, src=38973, dest=40692) — ID **190**
- [x] **P-1.4** `ALSUC: Llegadas desde Cba.` (`TLCO`, src=40691, dest=38973) — ID **191**
- [x] **P-1.5** `AGROV: Envíos a Bs.As.` (`TEBA`, src=8, dest=40693) — ID **192**
- [x] **P-1.6** `AGROV: Llegadas desde Bs.As.` (`TLBA`, src=40696, dest=8) — ID **193**
- [x] **P-1.7** `ASAGR: Envíos a Cba.` (`TECO`, src=40682, dest=40696) — ID **194**
- [x] **P-1.8** `ASAGR: Llegadas desde Cba.` (`TLCO`, src=40693, dest=40682) — ID **195**
- [x] **P-2.1** Push rule **278** → `ALSUC: Llegadas desde Cba.` (TLCO, ID 191) ✅
- [x] **P-2.2** Push rule **280** → `OSEYS: Llegadas desde Bs.As.` (TLBA, ID 189) ✅
- [x] **P-2.3** Push rule **282** → `ASAGR: Llegadas desde Cba.` (TLCO, ID 195) ✅
- [x] **P-2.4** Push rule **285** → `AGROV: Llegadas desde Bs.As.` (TLBA, ID 193) ✅
- [x] **P-3.1** `base.automation` ID **25** — `on_create` TEBA/TECO → asigna `procurement.group` único (`ir.actions.server` ID 1906)
- [x] **P-3.2** `base.automation` ID **26** — `on_write voucher_ids` TEBA/TECO → copia `voucher_ids` a llegada (`ir.actions.server` ID 1907)
- [x] **P-3.3** `base.automation` ID **27** — `on_create` TLBA/TLCO → hereda `group_id` desde saliente via `origin` (`ir.actions.server` ID 1908)

### Comunicación operativa
- [ ] Informar a operativos de **ALSUC** y **ASAGR**: usar `Envío a Cba.` para envíos inter-ciudad (no `Traslados internos`)
- [ ] Informar a operativos de **OSEYS** y **AGROV**: las recepciones aparecerán en `Llegada desde Bs.As.` (no en `Traslados internos`)

### Cierre de transición
- [ ] Esperar que los **24 pickings abiertos** actuales en tipos INT con ubic. de tránsito se cierren naturalmente
- [ ] Una vez cerrados: los tipos `INT` quedan exclusivamente para movimientos locales (sin ubicaciones de tránsito)

---

## Notas sobre edge cases importantes

### Backorders
La acción automática del PASO 3 tiene el filtro `backorder_id = false` deliberadamente. Los backorders heredan el `group_id` del picking padre — esto es el comportamiento correcto. **No asignar un group_id nuevo al backorder**.

### Operativo usa INT por error
Si alguien crea un `INT` manual con destino a una ubicación de tránsito, la push rule se dispara igual (escucha la ubicación destino, no el tipo). El picking de llegada se creará con el nuevo tipo `TLBA` o `TLCO`, pero el saliente INT no tendrá `group_id` → el merge puede volver. Solución a largo plazo: implementar en módulo una `@api.constrains` que impida usar ubicaciones de tránsito como destino en pickings de tipo `INT`.

### Pickings históricos
Los pickings históricos con tipo INT no se migran y no es necesario hacerlo. Quedan en el historial con su tipo original.

### Productos con rutas explícitas
Hay 10+ `product.template` con las rutas 170-174 en `route_ids`. No requieren cambio. Las rutas siguen siendo las mismas; solo cambia el tipo de picking que genera la push rule.
