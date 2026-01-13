# Implementación de Términos de Pago para COMEX

## Resumen de Cambios

Se ha implementado exitosamente la **Propuesta B con modelos extensibles** para los términos de pago en operaciones COMEX, reemplazando el uso inadecuado de `account.payment.term`.

## Arquitectura Implementada

### Modelos Creados

1. **`comex.payment.instrument`** (Instrumento de Pago)
   - Catálogo maestro de métodos de pago internacional
   - Campos: name, code, sequence, active, description
   - Análisis de riesgo: risk_level, bank_intervention, typical_cost_pct
   - Constraint: código único

2. **`comex.payment.timing`** (Plazo de Pago)
   - Catálogo maestro de plazos de pago
   - Campos: name, code, sequence, active, description, days
   - Tipo: timing_type (advance/sight/days)
   - Cumplimiento BCRA: bcra_max_days
   - Constraints: código único, días >= 0

### Campos en comex.operation

- **payment_instrument_id** (Many2one a comex.payment.instrument)
  - Método de pago (TT, L/C, D/P, D/A, OA, CIA)
  
- **payment_timing_id** (Many2one a comex.payment.timing)
  - Cuándo se paga (Anticipado, Vista, 15-360 días)
  
- **payment_terms_display** (Char computado, almacenado)
  - Formato: "CÓDIGO - Timing" (ej: "L/C - 180 días")
  - Se muestra en vista de árbol para visión rápida

## Datos Maestros Cargados

### Instrumentos de Pago (6 registros)

| Código | Nombre | Riesgo | Intervención Bancaria | Costo Típico |
|--------|--------|--------|----------------------|--------------|
| TT | Telegraphic Transfer | Alto | No | 0% |
| L/C | Letter of Credit | Bajo | Sí | 0.15% |
| D/P | Documents against Payment | Medio | Sí | 0.05% |
| D/A | Documents against Acceptance | Medio | Sí | 0.05% |
| OA | Open Account | Alto | No | 0% |
| CIA | Cash in Advance | Bajo | No | 0% |

### Plazos de Pago (9 registros)

| Código | Nombre | Tipo | Días | BCRA Max |
|--------|--------|------|------|----------|
| ADV | Anticipado | advance | 0 | 0 |
| SIGHT | A la Vista | sight | 0 | 0 |
| 15D | 15 días | days | 15 | 15 |
| 30D | 30 días | days | 30 | 30 |
| 60D | 60 días | days | 60 | 60 |
| 90D | 90 días | days | 90 | 90 |
| 120D | 120 días | days | 120 | 120 |
| 180D | 180 días | days | 180 | 180 |
| 360D | 360 días | days | 360 | 360 |

## Vistas Implementadas

### Vista de Árbol (comex.operation)
- Muestra **payment_terms_display** (ej: "TT - Vista", "L/C - 180 días")
- Campo opcional visible por defecto

### Vista de Formulario (comex.operation)
- Página "Financial" tiene dos campos separados:
  - **Payment Instrument**: Lista desplegable con TT, L/C, etc.
  - **Payment Timing**: Lista desplegable con Anticipado, Vista, 180 días, etc.

### Vistas de Configuración
- **COMEX > Configuration > Payment Instruments**: Gestionar instrumentos
- **COMEX > Configuration > Payment Timings**: Gestionar plazos
- Ambas con vistas tree/form editables
- Solo accesibles para COMEX Manager

## Ejemplo de Uso

```python
# Crear operación con términos de pago
operation = env['comex.operation'].create({
    'name': 'IMP/2024/00100',
    'operation_type': 'import',
    'partner_id': partner.id,
    'payment_instrument_id': env.ref('econovo_l10n_ar_comex.comex_payment_instrument_lc').id,
    'payment_timing_id': env.ref('econovo_l10n_ar_comex.comex_payment_timing_180d').id,
})

# El campo computado mostrará: "L/C - 180 días"
print(operation.payment_terms_display)  # "L/C - 180 días"
```

## Extensibilidad

Los administradores pueden agregar nuevos instrumentos o plazos sin modificar código:

1. Ir a **COMEX > Configuration > Payment Instruments**
2. Crear nuevo registro (ej: "SBLC - Standby Letter of Credit")
3. El nuevo instrumento estará disponible inmediatamente en todas las operaciones

Lo mismo aplica para **Payment Timings** (ej: agregar "240 días" para casos especiales).

## Cumplimiento Normativo

### ICC Standards (UCP 600)
- Instrumentos basados en prácticas comerciales internacionales
- Códigos estándar reconocidos globalmente

### BCRA (Argentina)
- Campo `bcra_max_days` para validar acceso al MULC
- Preparado para futuras validaciones automáticas (ej: L/C 180d OK, TT 360d requiere aprobación especial)

## Archivos Modificados/Creados

### Modelos
- ✅ `models/comex_payment_instrument.py` (NUEVO)
- ✅ `models/comex_payment_timing.py` (NUEVO)
- ✅ `models/__init__.py` (modificado)
- ✅ `models/comex_operation.py` (modificado)

### Datos
- ✅ `data/comex_payment_instrument_data.xml` (NUEVO)
- ✅ `data/comex_payment_timing_data.xml` (NUEVO)

### Vistas
- ✅ `views/comex_operation_views.xml` (modificado)
- ✅ `views/comex_payment_instrument_views.xml` (NUEVO)
- ✅ `views/comex_payment_timing_views.xml` (NUEVO)
- ✅ `views/econovo_l10n_ar_comex_menus.xml` (modificado)

### Seguridad
- ✅ `security/ir.model.access.csv` (modificado)

### Configuración
- ✅ `__manifest__.py` (modificado)

## Estado de Implementación

✅ **COMPLETADO** - 2024-01-13

- Modelos creados y cargados correctamente
- Datos maestros inicializados (6 instrumentos + 9 plazos)
- Vistas actualizadas (tree + form)
- Menús de configuración creados
- Permisos de seguridad configurados
- Módulo actualizado sin errores

## Verificación

```powershell
# Logs confirman carga exitosa:
# - loading econovo_l10n_ar_comex/data/comex_payment_instrument_data.xml
# - loading econovo_l10n_ar_comex/data/comex_payment_timing_data.xml
# - loading econovo_l10n_ar_comex/views/comex_payment_instrument_views.xml
# - loading econovo_l10n_ar_comex/views/comex_payment_timing_views.xml

# Actualización completada sin errores
```

## Próximos Pasos Sugeridos

1. **Validación BCRA**: Implementar validación automática de payment_timing vs BCRA limits
2. **Integración MULC**: Usar payment_timing.days en cálculos de MULC
3. **Reportes**: Agregar análisis de términos de pago en reportes financieros
4. **Workflows**: Considerar aprobaciones especiales para términos > 180 días

## Comparación con Implementación Original

| Aspecto | Original (account.payment.term) | Nueva Implementación |
|---------|--------------------------------|---------------------|
| Propósito | Crédito doméstico (30/60/90 días) | COMEX internacional |
| Dimensiones | 1 (solo plazo) | 2 (instrumento + timing) |
| Ejemplos | "30 días", "60 días" | "TT Vista", "L/C 180 días" |
| Riesgo | No considerado | risk_level, bank_intervention |
| Costos | No incluidos | typical_cost_pct |
| BCRA | Sin soporte | bcra_max_days |
| Extensible | Sí, pero inapropiado | Sí, específico para COMEX |
| Standards | Ninguno | ICC UCP 600 |

---

**Autor**: Jose D. Leonett  
**Fecha**: 2024-01-13  
**Módulo**: econovo_l10n_ar_comex v17.0.1.0.0  
**Licencia**: AGPL-3
