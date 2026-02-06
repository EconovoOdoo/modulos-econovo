# Propuestas de Sincronización: Operation Stage ↔ Shipment Stage

## Decisión General

### ¿Implementar sincronización automática?

- [x] **SÍ** - Implementar sincronización automática (continuar con edge cases)
- [ ] **NO - Opción A** - Solo campo informativo (computed no almacenado)
- [ ] **NO - Opción B** - Botón manual "Sync from Shipments"
- [ ] **NO - Opción C** - Dejar como está (independientes)

---

## EDGE CASE 1: Shipments sin Stage

**Descripción:**  
Si un shipment no tiene `stage_id` asignado (valor `False` o `None`), el código intenta acceder a `None.sequence` causando `AttributeError`.

### Propuestas:

- [x] **Propuesta 1.1 - Filtrar con `.filtered()`**
  - Usar `shipments_with_stage = operation.shipment_ids.filtered('stage_id')`
  - Ignora shipments sin stage en el cálculo
  - Simple y limpio
  - No afecta el stage de la operación si hay otros shipments con stage

- [x] **Propuesta 1.2 - Asignar stage default a shipments**
  - Al crear shipment sin stage, asignar automáticamente el stage de la operación
  - Previene el problema en origen
  - Requiere modificar `comex.shipment.create()`
  - Más invasivo pero más consistente

- [ ] **Propuesta 1.3 - Usar try/except**
  - Envolver `max()` en try/except para manejar AttributeError
  - Menos elegante pero robusto
  - Útil si hay otros casos no previstos

---

## EDGE CASE 2: Operación sin Shipments

**Descripción:**  
Cuando una operación no tiene shipments (o todos fueron borrados), ¿qué debe pasar con `operation.stage_id`?

### Propuestas:

- [x] **Propuesta 2.1 - Mantener stage actual**
  - Si no hay shipments, no modificar `stage_id`
  - El usuario mantiene control del stage de la operación
  - Operación puede tener stage independiente de shipments

- [ ] **Propuesta 2.2 - Resetear a stage default**
  - Usar `operation.stage_id = operation._default_stage()`
  - Vuelve a estado inicial si se borran todos los shipments
  - Más predecible pero puede sobrescribir cambios manuales

- [ ] **Propuesta 2.3 - Resetear solo si stage actual es computed**
  - Resetear solo si `stage_id` no fue modificado manualmente
  - Requiere tracking adicional (flag o log)
  - Balance entre automatización y control

---

## EDGE CASE 3: Retroceso de Stage (Regresión)

**Descripción:**  
Si un shipment retrocede de stage (ej: "Customs Clearance" → "At Port"), ¿la operación debe retroceder automáticamente?

### Propuestas:

- [x] **Propuesta 3.1 - Permitir retroceso automático**
  - El stage de la operación siempre refleja el shipment más avanzado
  - Si el más avanzado retrocede, la operación retrocede
  - Consistente pero puede confundir al usuario

- [ ] **Propuesta 3.2 - Solo avanzar, nunca retroceder**
  - Usar `max(operation.stage_id.sequence, new_stage.sequence)`
  - El stage solo puede avanzar, no retroceder
  - Requiere lógica adicional para comparar secuencias
  - Más intuitivo para usuarios

- [ ] **Propuesta 3.3 - Modo configurable**
  - Agregar checkbox "Allow stage regression" en Settings
  - Usuario decide el comportamiento
  - Más flexible pero agrega complejidad

---

## EDGE CASE 4: Conflict - Usuario vs Sistema

**Descripción:**  
Si el usuario cambia manualmente `operation.stage_id`, pero luego se edita un shipment, el sistema sobrescribe la elección manual.

### Propuestas:

- [x] **Propuesta 4.1 - Campo readonly=False (override manual)**
  - Hacer `stage_id = fields.Many2one(..., compute=..., store=True, readonly=False)`
  - Permite que usuario sobrescriba el valor computed
  - Siguiente edición de shipment lo vuelve a calcular
  - Balance entre auto y manual

- [ ] **Propuesta 4.2 - Flag "Manual Stage"**
  - Agregar campo `stage_manual = fields.Boolean()`
  - Si `stage_manual=True`, no recalcular
  - Usuario activa flag cuando quiere control manual
  - Más control pero requiere UI adicional

- [ ] **Propuesta 4.3 - Solo calcular en create**
  - Compute solo cuando se crea la operación
  - Después, totalmente manual
  - Más simple pero pierde sincronización continua

---

## EDGE CASE 5: Stages con Misma Secuencia

**Descripción:**  
Si dos stages tienen la misma `sequence`, `max()` devuelve uno arbitrario.

### Propuestas:

- [ ] **Propuesta 5.1 - Usar ID como tiebreaker**
  - `max(stages, key=lambda s: (s.sequence, s.id))`
  - Consistente y predecible
  - El stage más reciente (ID mayor) gana

- [ ] **Propuesta 5.2 - Usar nombre alfabético**
  - `max(stages, key=lambda s: (s.sequence, s.name))`
  - Más intuitivo para usuarios
  - Orden alfabético como desempate

- [x] **Propuesta 5.3 - Prevenir duplicados en configuración**
  - Agregar constraint `_sql_constraints` en `comex.operation.stage`
  - Forzar secuencias únicas
  - Previene el problema en origen

---

## EDGE CASE 6: Stages de Operation Type Diferente

**Descripción:**  
Si el stage más avanzado no es compatible con el `operation_type` de la operación (ej: stage de export en operation de import).

### Propuestas:

- [x] **Propuesta 6.1 - Filtrar por operation_type**
  - Usar `.filtered(lambda s: s.operation_type in ('all', operation.operation_type))`
  - Solo considera stages compatibles
  - Más seguro y correcto
  - CADA SHIPMENT debe tener stage compatible SEGÚN SU OPERATION TYPE. DEBE HABER UN DOMINIO EN EL CAMPO stage_id DE comex.shipment QUE LO GARANTICE BASADO EN operation_type DE LA OPERACIÓN ASOCIADA DE ORIGEN.

- [ ] **Propuesta 6.2 - Asumir 'all' stages siempre aplican**
  - No filtrar, confiar en que stages están bien configurados
  - Más simple pero menos robusto
  - Requiere buena configuración inicial

- [ ] **Propuesta 6.3 - Warning si hay incompatibilidad**
  - Si no hay stages compatibles, mostrar warning al usuario
  - Loggear el problema para debugging
  - Mantener stage actual

---

## EDGE CASE 7: Borrado de Shipment

**Descripción:**  
Cuando se borra un shipment (especialmente el que tenía el stage más avanzado), ¿se recalcula correctamente?

### Propuestas:

- [x] **Propuesta 7.1 - Depends funciona automáticamente**
  - Confiar en `@api.depends('shipment_ids.stage_id')`
  - Odoo recalcula automáticamente en borrado
  - No requiere código adicional
  - **Opción recomendada** (funciona out-of-the-box)

- [ ] **Propuesta 7.2 - Override unlink en shipment**
  - Sobrescribir `comex.shipment.unlink()` para forzar recálculo
  - Más explícito pero redundante
  - Útil si depends no funciona (caso raro)

---

## EDGE CASE 8: Ciclo Infinito Potencial

**Descripción:**  
Si implementas sincronización bidireccional (operation → shipments y shipments → operation), puedes causar loop infinito.

### Propuestas:

- [x] **Propuesta 8.1 - Usar contexto para prevenir loops**
  - Usar `if not self.env.context.get('skip_stage_sync')`
  - Llamar `.with_context(skip_stage_sync=True).write()`
  - Estándar en Odoo para prevenir recursión

- [ ] **Propuesta 8.2 - Solo sincronizar unidireccional**
  - Shipments → Operation (sí)
  - Operation → Shipments (no)
  - Más simple, sin riesgo de loops

- [ ] **Propuesta 8.3 - Flag global de sincronización activa**
  - Usar variable de instancia `_stage_sync_active`
  - Prevenir múltiples sincronizaciones simultáneas
  - Más complejo pero más seguro en escenarios edge

---

## EDGE CASE 9: Performance con Muchos Shipments

**Descripción:**  
Con 100+ shipments por operación, `mapped()` + `max()` puede ser costoso y se dispara en cada cambio individual.

### Propuestas:

- [ ] **Propuesta 9.1 - Optimización SQL directa**
  - Usar query SQL: `SELECT MAX(sequence) FROM comex_operation_stage ...`
  - Más rápido para grandes volúmenes
  - Más complejo de mantener

- [ ] **Propuesta 9.2 - Batch updates con contexto**
  - Agregar contexto `skip_stage_sync` durante operaciones masivas
  - Recalcular al final con método manual
  - Usuario controla cuándo sincronizar

- [x] **Propuesta 9.3 - Aceptar el overhead**
  - Para la mayoría de casos (<50 shipments), el overhead es aceptable
  - Odoo optimiza `mapped()` internamente
  - **Opción recomendada** para empezar

---

## EDGE CASE 10: Estado Inicial

**Descripción:**  
Nueva operación creada sin shipments. ¿Debe tener un stage o quedar vacío?

### Propuestas:

- [x] **Propuesta 10.1 - Mantener default= en el campo**
  - Usar `default=_default_stage` en la definición del campo
  - Odoo asigna stage inicial automáticamente
  - Compute no sobrescribe el default en create
  - **Opción recomendada**

- [ ] **Propuesta 10.2 - Compute asigna default**
  - El método compute detecta "primera vez" y asigna default
  - Más control pero más complejo
  - Útil si default varía según contexto

- [ ] **Propuesta 10.3 - Stage obligatorio en create**
  - Agregar validación en create() que requiera stage
  - Usuario debe elegir stage inicial manualmente
  - Más explícito pero menos user-friendly

---

## Implementación Final

Una vez marcadas todas las propuestas preferidas, genera el código con:
- Todas las propuestas marcadas con `[X]`
- Código robusto que maneja todos los edge cases seleccionados
- Tests unitarios para cada edge case
- Documentación inline explicando las decisiones

**Archivo a modificar:**  
`d:\Odoo\GITHUB-SRC\econovo\EconovoOdoo\modulos-econovo\econovo_l10n_ar_comex\models\comex_operation.py`

---

## Notas Adicionales

- Si no marcas nada, asumiré "NO implementar sincronización"
- Si marcas decisión general = SÍ, revisa todos los edge cases
- Puedes marcar múltiples propuestas si quieres combinar estrategias
- Propuestas recomendadas están indicadas con ✅ en comentarios
