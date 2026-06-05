# econovo_payment_approval

Activity-based approval workflow for outbound payments (`account.payment`) and manual journal entries (`account.move`).

Replaces Studio Approval Rules with a lightweight, dependency-free solution using `mail.activity`.

---

## Features

- **Unified routing rules** (`econovo.approval.rule`) covering payments and journal entries
- **Batch-aware amount routing** — evaluates rules against the Sumitec batch total, not individual amounts
- **Priority stars** (Normal / Alta / Muy Alta / Urgente) on both models
- **Approve / Reject buttons** in the form header and list-view header
- **"Aprobado por"** read-only field, auto-cleared on draft reset
- **Rejection wizard** with mandatory reason; posts a chatter note and creates a corrective activity for the document creator

---

## Routing rules — payments

Rules are evaluated in `sequence` order. **Every matching rule** creates an activity (multiple approvers possible per document).

| Seq | Name | Approver | Domain key |
|-----|------|----------|------------|
| 10 | Pagos Mayores >1M ARS | Fabricio Filoni | `effective_approval_amount > 1 000 000` |
| 20 | Pagos Menores ≤1M ARS | Nacho Massola | `effective_approval_amount ≤ 1 000 000` |
| 30 | Buenos Aires / Lourdes | Nacho Massola | journal company = BA or `create_uid = 482` |
| 40 | Exterior FX | Fabricio Filoni | `currency_id.name != 'ARS'` |
| 50 | Agrovial Comex | Fabricio Filoni | `create_uid in [370, 470]` |

### Batch-aware routing (`effective_approval_amount`)

`account.payment` exposes a computed (non-stored) field `effective_approval_amount`:

- **Payment belongs to a Sumitec batch** → returns `sum(batch.payment_ids.filtered(state != 'cancel').amount)`
- **Payment has no batch** → returns `payment.amount`

**Why this matters:** Sumitec's "Confirmar y Nuevo" flow assigns every payment to a batch even for single-payment sessions. When the user creates P1=4M and P2=1M in the same batch:

- P1 evaluated at `effective_approval_amount=4M` → Rule 10 → Fabricio ✓
- P2 evaluated at `effective_approval_amount=5M` (batch total) → Rule 10 → Fabricio ✓

Without this field, P2 would be evaluated at `amount=1M` → Rule 20 → Nacho (wrong).

Rules 10 and 20 are marked `noupdate="0"` in the data file so domain changes apply on every `--update`.

---

## Routing rules — journal entries

Applies only to `move_type='entry'` moves that touch one of 33 monitored account codes (loans, municipal taxes, IIBB, VAT, payroll, union dues, installment plans).

| Seq | Name | Approver | Condition |
|-----|------|----------|-----------|
| 60 | Asientos Mayores ≥1M ARS | Fabricio | `amount_total >= 1 000 000` |
| 70 | Asientos Menores <1M ARS | Nacho | `amount_total < 1 000 000` |
| 80 | Asientos Exterior FX | Fabricio | `currency_id.name != 'ARS'` |

---

## User flow — payments

### Happy path

```
Tesorera                    Sistema                          Aprobador (Fabricio/Nacho)
────────────────────────────────────────────────────────────────────────────────────────
Crea pago P1 = 4M ARS
"Confirmar y Nuevo"
                            Sumitec crea batch B1
                            P1 posted
                            effective_amount = 4M (solo P1)
                            Rule 10 → activity "Revisar Pago"
                            asignada a Fabricio en P1
                                                             Ve ⚠ "Revisar Pago"
                                                             Abre P1
                                                             Clic "Aprobar Pago"
                            approved_by_id = Fabricio
                            chatter: "✅ Pago aprobado por Fabricio"
```

### Rechazo

```
Aprobador                   Sistema                          Tesorera
────────────────────────────────────────────────────────────────────────────────────────
Abre P1
"Rechazar Pago"
                            Abre wizard con textarea
Escribe motivo
"Confirmar Rechazo"
                            1. Cancela activity "Revisar Pago"
                            2. chatter: "⛔ Rechazado por X\n<motivo>"
                            3. Crea activity "Pago Rechazado" 🔴
                               asignada a P1.create_uid
                                                             Ve 🔴 "Pago Rechazado"
                                                             Lee motivo en chatter
```

### Vuelta a borrador y re-confirmación

```
Tesorera                    Sistema                          Aprobador
────────────────────────────────────────────────────────────────────────────────────────
"Restablecer a borrador"
                            _cancel_all_approval_activities()
                              → cancela "Revisar Pago" (vacío)
                              → cancela "Pago Rechazado" 🔴
                            approved_by_id = False
                            P1.state = "draft"

Corrige monto/proveedor
"Confirmar"
                            P1.state = "posted"
                            Recalcula effective_amount
                              (B1 tiene P1 + cualquier otro)
                            Evalúa reglas de nuevo
                            Crea NUEVA activity
                                                             Ve nueva ⚠ "Revisar Pago"
                                                             Aprueba
```

### Lote con varios pagos (batch)

```
Tesorera crea P1=4M → "Confirmar y Nuevo"
  → B1 creado, P1 posted, effective_amount(P1)=4M → Fabricio

Crea P2=1M en el mismo form (B1 en contexto) → "Confirmar"
  → P2.batch=B1 ya asignado al guardar
  → P2 posted, effective_amount(P2) = sum([4M, 1M]) = 5M → Fabricio

Resultado: Fabricio tiene 2 activities (una por P1, una por P2)
Fabricio puede:
  a) Abrir el batch → "Aprobar Lote" → aprueba ambos en 1 click
  b) Lista de pagos → seleccionar 2 → [Aprobar Pago] en header
```

---

## UI — dónde se ven los botones

### Formulario de pago / asiento

Botones visibles cuando:
- `state == 'posted'`
- `has_pending_approval_activity == True`
- Usuario en grupo `grp_aprobadores_pago`

```
[Aprobar Pago]  [Rechazar Pago]  |  Confirmado  Cancelado  (statusbar)
```

### Lista de pagos (selección múltiple)

```
[Confirmar]  [Aprobar Pago]  [Rechazar Pago]   ← header del tree
              (verde)         (rojo)
```

`Rechazar Pago` en lista solo acepta 1 registro (UserError si >1).

### Campo `Aprobado por`

Visible en form view (readonly). Limpiado automáticamente en `action_draft()`.

---

## Campos en `account.payment`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `priority` | Selection (0-3) | Stars widget — Normal / Alta / Muy Alta / Urgente |
| `approved_by_id` | Many2one res.users | Último usuario que aprobó, readonly |
| `has_pending_approval_activity` | Boolean (computed) | True si hay activity "Revisar Pago" activa |
| `effective_approval_amount` | Float (computed) | Monto efectivo: total del batch o monto individual |

---

## Actividades creadas por el módulo

| XML ID | Nombre | Icono | Asignada a |
|--------|--------|-------|-----------|
| `mail_activity_type_revisar_pago` | Revisar Pago | ⚠ warning | Aprobador (Fabricio/Nacho) |
| `mail_activity_type_pago_rechazado` | Pago Rechazado | 🔴 danger | Creador del pago (tesorera) |
| `mail_activity_type_aprobar_asiento` | Aprobar Asiento | ⚠ warning | Aprobador |
| `mail_activity_type_asiento_rechazado` | Asiento Rechazado | 🔴 danger | Creador del asiento |

---

## Módulos relacionados

| Módulo | Relación |
|--------|----------|
| `econovo_payment_batch_approval` | Módulo separado — maneja aprobaciones vía Studio Approval Rules para el mismo flujo de batches. Corre en paralelo. |
| `account_payment_batch_st` | Módulo Sumitec — provee `account.payment.batch.st` y el flujo "Confirmar y Nuevo". |

---

## Archivos principales

```
econovo_payment_approval/
├── models/
│   ├── account_payment.py          # effective_approval_amount, approve/reject
│   ├── account_move.py             # approve/reject para asientos manuales
│   ├── account_payment_batch.py    # delegación batch → payment_ids
│   └── econovo_approval_rule.py    # modelo de reglas de ruteo
├── wizard/
│   ├── econovo_payment_reject_wizard.py
│   ├── econovo_move_reject_wizard.py
│   └── econovo_batch_reject_wizard.py
├── data/
│   ├── mail_activity_data.xml      # 4 tipos de actividad
│   └── approval_rules.xml         # 8 reglas (Rules 10/20: noupdate=0)
├── views/
│   ├── account_payment_views.xml
│   ├── account_move_views.xml
│   └── account_payment_batch_views.xml
└── security/
    ├── econovo_payment_approval_groups.xml
    └── ir.model.access.csv
```

---

## Historial de versiones

| Versión | Cambios |
|---------|---------|
| 17.0.1.0.0 | Versión inicial — reglas, actividades, approve/reject básico |
| 17.0.2.0.0 | R1-R4: Markup en chatter, full-width wizard, botones en tree header, priority stars |
| 17.0.3.0.0 | R5: Campo `effective_approval_amount` — routing basado en total del batch Sumitec |
