# Work Center Cost Fields — Odoo 17

## Campos nativos de Odoo

### `costs_hour` — Costo por hora de la máquina
| Atributo | Valor |
|---|---|
| Módulo | `mrp` (Community) |
| Modelo | `mrp.workcenter` |
| Tipo | `Float` |
| UI | Fabricación → Configuración → Centros de trabajo → *Costo por hora* |

Representa el costo de **operar la máquina** (energía, amortización, mantenimiento).
Se aplica directamente en el cálculo del costo de operaciones de la LdM:

```python
# mrp/report/mrp_report_bom_structure.py
def _get_operation_cost(self, duration, operation):
    return (duration / 60.0) * operation.workcenter_id.costs_hour
```

---

### `employee_costs_hour` — Costo por hora del operario
| Atributo | Valor |
|---|---|
| Módulo | `mrp_workorder` (Enterprise) |
| Modelo | `mrp.workcenter` |
| Tipo | `Monetary` (usa moneda de la compañía) |
| UI | Fabricación → Configuración → Centros de trabajo → *Employee Hourly Cost* |

Representa el costo de **un empleado genérico** trabajando en ese centro.
Se multiplica por `employee_ratio` (campo en la operación de la LdM = cuántos operarios
requiere esa operación en simultáneo). El EE **extiende** la fórmula CE sumando este costo:

```python
# mrp_workorder/report/mrp_report_bom_structure.py
def _get_operation_cost(self, duration, operation):
    employee_cost = (
        (duration / 60.0)
        * operation.workcenter_id.employee_costs_hour
        * operation.employee_ratio
    )
    return super()._get_operation_cost(duration, operation) + employee_cost
```

> **Nota**: Si el operario tiene `hourly_cost` propio en su ficha de empleado (`hr.employee`),
> ese valor sobreescribe `employee_costs_hour` al registrar tiempo real en el Shop Floor.
> Solo afecta el registro real, no el cálculo estimado de la LdM.

---

## Fórmula combinada (Odoo 17 Enterprise)

Para una operación de duración `D` minutos con `N` operarios:

$$\text{Costo operación} = \frac{D}{60} \times \text{costs\_hour} + \frac{D}{60} \times \text{employee\_costs\_hour} \times N$$

---

## Ejemplo

**Centro de trabajo**: Soldadura
| Campo | Valor |
|---|---|
| `costs_hour` | $500 ARS/h |
| `employee_costs_hour` | $800 ARS/h |

**Operación**: Soldar chasis — 90 min, `employee_ratio = 2`

| Concepto | Cálculo | Resultado |
|---|---|---|
| Costo máquina | (90/60) × $500 | $750 |
| Costo mano de obra | (90/60) × $800 × 2 | $2.400 |
| **Total operación** | | **$3.150** |

---

## Campos USD agregados por `econovo_mrp_bom_cost_summary_dolarization`

| Campo | Par ARS | Descripción |
|---|---|---|
| `costs_hour_usd` | `costs_hour` | Costo máquina en USD (precio directo) |
| `employee_costs_hour_usd` | `employee_costs_hour` | Costo operario en USD (precio directo) |

Se auto-actualizan al guardar sus pares ARS aplicando el tipo de cambio USD del día,
pero pueden editarse manualmente cuando la tarifa en USD fue negociada independientemente.
