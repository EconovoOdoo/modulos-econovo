# Plan de implementación — pie de página configurable en remito digital

## 1. Objetivo

Implementar un pie de texto configurable para el remito digital impreso, sin tocar el campo `observations` del picking ni depender del template preimpreso.

La intención es que el talonario pueda definir un texto de pie y una condición de aplicación; al momento de generar el PDF, el sistema evalúa esa condición sobre el picking concreto y solo entonces imprime el texto en el PDF del remito.

> Requisito de negocio: solo se necesita en el PDF impreso; no es un dato persistente del picking ni una nota visible en el flujo operativo.

---

## 2. Rama objetivo y versionado

### Rama

Se trabaja en una rama dedicada al feature, limpia y aislada del trabajo paralelo:

- 17.0-feat-econovo_remito_digital_footer

### Version bump sugerido

El módulo ya está en:

- 17.0.1.14.1

Como este cambio es una nueva funcionalidad de impresión, la subversión debe incrementarse como feature, no como arreglo puntual:

- 17.0.1.15.0

Esto refleja que hay una mejora funcional visible a usuario/operación, pero sin romper compatibilidad con el reporte actual.

---

## 3. Decisión de arquitectura

Se opta por una solución dentro del mismo módulo `econovo_remito_digital` y no como modificación del flujo general de picking.

### Opción elegida

- Definir la regla en el talonario (`stock.book`), no en el picking.
- Evaluar la condición al imprimir el PDF.
- Imprimir solo en el PDF del remito digital.
- Mantener la lógica en `econovo_remito_digital`, sin tocar `stock_ux` ni el report preimpreso.

Esto preserva el modelo operativo actual y evita efectos colaterales en otras impresiones, stock moves y observaciones generales.

---

## 4. Alcance técnico

### 4.1 Archivos involucrados

- `econovo_remito_digital/models/stock_book.py`
- `econovo_remito_digital/models/stock_picking.py`
- `econovo_remito_digital/views/remito_digital_templates.xml`
- `econovo_remito_digital/__manifest__.py`
- `econovo_remito_digital/security/ir.model.access.csv` (si se agregan nuevos modelos o campos con acceso específico)

### 4.2 Lógica propuesta

Se agrega al modelo heredado `stock.book` una estructura mínima y clara:

- `remito_footer_active` : Boolean
- `remito_footer_text` : Text o Html
- `remito_footer_domain` : Char/Text con dominio evaluable
- `remito_footer_priority` : Integer (opcional, si se quiere soportar más de una regla)

### Regla de evaluación

Al momento de preparar el reporte, se busca la regla activa del talonario asociado al remito y se evalúa la condición sobre el picking actual.

Pseudo-lógica:

```python
footer_text = ''
book = picking.book_id
if book and book.remito_footer_active and book.remito_footer_text:
    domain = book.remito_footer_domain or []
    if not domain or picking.filtered_domain(domain):
        footer_text = book.remito_footer_text
```

En la práctica, la evaluación debe ser robusta y segura:

- Si el dominio está vacío, se toma el texto por defecto del talonario.
- Si hay varios talonarios o varias reglas, se ordenan por prioridad.
- Si no coincide ninguna regla, no se imprime nada.
- Si el texto contiene HTML simple, se renderiza con `t-raw` si hace falta; si es texto plano, se usa `t-esc`.

---

## 5. Cómo se integra con el PDF actual

El remito digital ya tiene una zona de pie destinada al footer del documento. La idea es reutilizar esa zona y reemplazar el contenido dinámicamente según el talonario.

### Cambios esperados en el template

- Mantener la estructura actual del reporte.
- Agregar una variable en el contexto, por ejemplo:
  - `report_footer_text`
- En la sección del footer del PDF, renderizar:
  - `t-raw="report_footer_text"` si el valor incluye HTML
  - `t-esc="report_footer_text"` si es solo texto plano

Esto debe ocurrir solo en la salida del remito digital; no se altera el contenido del picking ni la vista del formulario.

---

## 6. Recomendación de modelado del dominio

La regla más mantenible es usar un dominio típico de Odoo, pero almacenado en texto y parseado con `safe_eval` o `ast.literal_eval` al momento de imprimir.

### Ejemplos de dominios

```python
[('picking_type_id.code', '=', 'outgoing')]
[('partner_id.commercial_partner_id.country_id.code', '=', 'AR')]
[('company_id', '=', 1)]
```

### Ventajas

- Es editable y configurable sin tocar código.
- Se puede reutilizar por categoría, tipo de movimiento o cliente.
- Sigue el patrón de dominio de Odoo y encaja con la UX operativa.

### Recomendación concreta

Usar el campo `remito_footer_domain` como `Text` con un valor Python-literal de dominio y parsear con `safe_eval` para evitar errores de sintaxis en la configuración.

---

## 7. Manejo de múltiples reglas

Si en el futuro se quiere soportar más de una regla por talonario, la implementación debe ser escalonada y no sobrecargada.

### Opción recomendada para la entrega inicial

- 1 talonario = 1 texto activo
- 1 registro = 1 regla
- 1 dominio = 1 condición

Eso basta para el caso de negocio actual y evita complejidad innecesaria.

Si luego se requiriera más, se puede evolucionar a un modelo dedicado `stock.book.remito.footer.rule` con:

- `book_id`
- `name`
- `condition_domain`
- `text`
- `sequence`

pero eso es un feature posterior, no una necesidad inicial.

---

## 8. Propuesta del helper en Python

La lógica central debería vivir en un método del picking o del libro, por ejemplo:

- `_get_remito_footer_text()`
- `_get_active_remito_footer()`

Ejemplo de comportamiento:

```python
@api.model
def _get_active_remito_footer(self, picking):
    book = picking.book_id
    if not book or not book.remito_footer_active:
        return ''
    if not book.remito_footer_text:
        return ''
    domain = book.remito_footer_domain or '[]'
    try:
        parsed_domain = safe_eval(domain, {'context': self.env.context})
    except Exception:
        return ''
    if picking.filtered_domain(parsed_domain):
        return book.remito_footer_text
    return ''
```

Esto centraliza la lógica y evita desorden en el template.

---

## 9. Casos de borde y riesgo

### 9.1 Dominio no válido

- La configuración debe tolerar error sin romper todo el PDF.
- Si la expresión no se puede evaluar, devolver texto vacío y registrar warning en logs.

### 9.2 Texto HTML muy largo

- Debe cortarse o pre-renderizarse para que no empuje el footer fuera del espacio reservad.
- Conservar formato simple y short text, no incluir HTML complejo.

### 9.3 Múltiples libros por envío

- La lógica debe usar el libro realmente vinculado al picking/report, no un libro por defecto global.

### 9.4 Compatibilidad con remitos existentes

- Si el talonario no tiene texto definido, no hace nada.
- No debe afectar PDFs generados previamente.

---

## 10. Criterios de aceptación

### CA 1
Se puede definir un texto de pie en un talonario del remito digital.

### CA 2
Ese texto se imprime solo cuando el dominio evaluado sobre el picking coincide.

### CA 3
Si la configuración no existe o el dominio no coincide, el PDF no muestra pie adicional.

### CA 4
El campo `observations` del picking no se modifica al imprimir.

### CA 5
La funcionalidad queda encapsulada en el módulo `econovo_remito_digital`.

### CA 6
La versión del módulo queda marcada con un bump de feature para la entrega.

---

## 11. Secuencia recomendada de implementación

1. Crear la rama limpia del feature.
2. Bump de versión del módulo a `17.0.1.15.0`.
3. Añadir campos en `stock.book`.
4. Crear helper de evaluación de footer.
5. Inyectar el valor en el contexto del reporte.
6. Ajustar el template del remito digital para renderizar el pie dinámico.
7. Agregar pruebas mínimas (casos: sin dominio, dominio coincidente, dominio no coincidente, texto vacío).
8. Validar la impresión en local con un picking de prueba y revisar que el PDF no rompa layout.

---

## 12. Recomendación final

La solución propuesta es la más segura y mantenible para el caso pedido:

- El texto vive en el talonario.
- La regla se evalúa al imprimir.
- El resultado solo aparece en el PDF del remito digital.
- No se alteran datos de negocio ni se pisa `observations`.

Esto cumple el requerimiento operativo y evita efectos colaterales no deseados en otros documentos o reportes.
