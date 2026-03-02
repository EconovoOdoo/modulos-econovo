# COMEX: Cierre del edge case "Factura AFIP tipo 66 sin Customs Clearance"

## 1) Problema observado

En el modelo `comex.operation`, el campo `invoice_ids` permite agregar facturas manualmente.
Actualmente, una factura con tipo AFIP código `66` (Despacho de Importación) puede quedar vinculada a la operación **sin** tener un `comex.customs.clearance` asociado (vía `vendor_bill_id`).

Esto genera inconsistencias funcionales porque:
- El documento se clasifica como "aduanero" en reportes/cómputos.
- Pero no existe el objeto de negocio `comex.customs.clearance` que representa el despacho.

---

## 2) Causa raíz (resumen técnico)

1. La clasificación de "Despacho" está hardcodeada por código de documento AFIP `66`.
2. `invoice_ids` en `comex.operation` preserva líneas agregadas manualmente (`existing | computed`).
3. No hay constraint que obligue a que una factura tipo `66` tenga clearance asociado.
4. La vista de operación permite agregar facturas manualmente desde la pestaña Invoices/Bills.

Resultado: puede existir una "factura 66 huérfana" dentro de la operación.

---

## 3) Objetivo de cierre

Asegurar que toda factura AFIP tipo `66` ligada a `comex.operation` tenga trazabilidad completa:
- O bien está asociada a un `comex.customs.clearance`.
- O se impide/encauza su alta manual para que no quede huérfana.

---

## 4) Alternativas de solución

## Alternativa A — Validación dura (constraint) en `comex.operation`

### Idea
Agregar validación al escribir `invoice_ids` que rechace cualquier factura tipo `66` sin clearance relacionado a la misma operación.

### Cómo operaría
- En `write`/constraint de `comex.operation`, para cada invoice tipo `66` en `invoice_ids`:
  - verificar existencia de `comex.customs.clearance` con:
    - `operation_id = operación actual`
    - `vendor_bill_id = factura`
- Si no existe, lanzar `ValidationError` con mensaje claro.

### Pros
- Garantiza integridad fuerte e inmediata.
- Evita datos inconsistentes en cualquier canal (UI, import, RPC, scripts).

### Contras
- Puede friccionar operación si usuarios estaban acostumbrados a cargar primero factura y luego clearance.
- Requiere mensajes/UX muy claros para no bloquear sin guía.

### Cuándo conviene
- Equipos con disciplina de proceso y prioridad alta en integridad.

---

## Alternativa B — Autocreación de clearance al agregar factura 66

### Idea
Cuando se agregue una factura tipo `66` en `invoice_ids` y no exista clearance, crear automáticamente uno (borrador) y setear `vendor_bill_id`.

### Cómo operaría
- Hook en `write`/inverse de `invoice_ids`:
  - detectar nuevas facturas `66`.
  - si no tienen clearance, crear `comex.customs.clearance` con defaults mínimos.

### Pros
- Excelente UX: no bloquea y resuelve automáticamente.
- Mantiene integridad sin esfuerzo del usuario.

### Contras
- Riesgo de crear clearances "vacíos" o incompletos si faltan datos clave.
- Puede sorprender al usuario si no se comunica claramente.

### Cuándo conviene
- Operación con alto volumen y necesidad de velocidad de carga.

---

## Alternativa C — Soft enforcement (warning + acción guiada)

### Idea
No bloquear, pero detectar y marcar facturas `66` huérfanas con:
- warning visible,
- smart button/acción "Crear clearance desde factura",
- KPI de inconsistencias.

### Cómo operaría
- Campo computado en operación: `orphan_dispatch_invoice_count`.
- Banner en vista cuando count > 0.
- Acción para generar clearances faltantes en lote.

### Pros
- Casi sin fricción.
- Permite transición gradual y limpieza asistida.

### Contras
- No garantiza consistencia en tiempo real (pueden quedar huérfanas temporalmente).
- Requiere disciplina operativa para remediar.

### Cuándo conviene
- Entornos donde no se puede introducir bloqueo inmediato.

---

## Alternativa D — Restricción de UI + validación backend mínima (híbrida)

### Idea
- En la pestaña de `invoice_ids`, impedir agregar manualmente facturas tipo `66` (dominio/UI).
- Mantener validación backend defensiva para cubrir integraciones externas.

### Cómo operaría
- Dominio de vista en `invoice_ids` para excluir doc type `66` en inserción manual.
- Constraint backend que impida persistir 66 huérfana por RPC/import.

### Pros
- Buena UX en interfaz + integridad técnica robusta.
- Reduce errores de usuario y protege por backend.

### Contras
- Un poco más de implementación (vista + modelo).
- Requiere cuidado para no afectar casos legítimos de edición histórica.

### Cuándo conviene
- Opción más equilibrada para producción con múltiples vías de carga.

---

## 5) Recomendación

Recomendada: **Alternativa D (híbrida)** en 2 fases.

### Fase 1 (rápida, bajo riesgo)
1. Agregar validación backend para impedir factura 66 huérfana.
2. Mensaje de error accionable: "Vincule/cree un Customs Clearance para esta factura".

### Fase 2 (mejora UX)
3. Ajustar vista para desalentar/impedir carga manual de 66 desde `invoice_ids`.
4. Exponer acción dedicada: "Crear Customs Clearance" o "Vincular clearance existente".

Con esto se logra integridad fuerte sin degradar experiencia de usuario.

---

## 6) Compatibilidad y migración de datos existentes

Antes de activar la validación dura:
1. Ejecutar script de diagnóstico para detectar facturas 66 huérfanas por operación.
2. Corregir en lote:
   - crear clearance faltante, o
   - desvincular factura 66 de operación si fue carga errónea.
3. Recién después activar constraint en producción.

---

## 7) Criterios de aceptación sugeridos

1. No se puede guardar operación con factura tipo 66 sin `customs_clearance` relacionado.
2. Facturas 66 creadas desde flujo de clearance quedan vinculadas correctamente.
3. Carga de facturas comerciales (no 66) sigue operando sin cambios.
4. KPIs de customs y conciliación no consideran facturas 66 huérfanas.
5. Tests cubren alta manual, importación y edición de operación.

---

## 8) Riesgos a monitorear

- Regresiones en procesos históricos donde existen datos incompletos.
- Integraciones externas que escriben `invoice_ids` directamente.
- Mensajes de error no claros para usuario final.

Mitigación: activación por fases + limpieza previa + tests automáticos.
