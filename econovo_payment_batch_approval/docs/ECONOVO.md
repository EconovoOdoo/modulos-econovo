# Econovo — Payment Batch Approval: Configuration Guide

This document covers the environment-specific configuration of the
`econovo_payment_batch_approval` module for Econovo's Odoo instance.
It is not part of the module itself and should not be shipped with it.

---

## Roles and Responsibilities

| Role | Description |
|------|-------------|
| **Treasurer** | Creates vendor payments using "Confirm and New". Payments stay in Draft until approved. |
| **Payment Approver** | Approves individual payments via the Studio Approval widget on each payment form. Must belong to the applicable approval group for the payment's tier. |
| **Batch Approver** | Approves an entire batch in one click via the **Approve Batch** button. Must belong to *Payment Batch Approvers*. In practice this is the same set of users as Payment Approvers. |

---

## Authorisation Tiers

Econovo uses four approval tiers, each implemented as a Studio Approval Rule
on `account.payment.action_post`:

| Tier | Rule name | Scope | Domain |
|------|-----------|-------|--------|
| **High-value (ARS)** | Aprobación Pagos Mayores ≥ $1M | Outbound ARS payments ≥ $1,000,000 from any company except Buenos Aires | `[('is_internal_transfer', '=', False), ('amount', '>=', 1000000), ('journal_id.company_id', '!=', 3), ('currency_id.name', '=', 'ARS'), ('payment_type', '=', 'outbound')]` |
| **Standard (ARS)** | Aprobación Pagos Menores < $1M | Outbound ARS payments < $1,000,000 from any company except Buenos Aires | `[('is_internal_transfer', '=', False), ('amount', '<', 1000000), ('journal_id.company_id', '!=', 3), ('currency_id.name', '=', 'ARS'), ('payment_type', '=', 'outbound')]` |
| **Buenos Aires branch** | Aprobación Pagos Buenos Aires | All outbound payments from company ID 3 (Buenos Aires) | `[('is_internal_transfer', '=', False), ('journal_id.company_id', '=', 3), ('payment_type', '=', 'outbound')]` |
| **Foreign currency (FX)** | Aprobación Pagos Exterior (FX) | All outbound payments in any currency other than ARS | `[('is_internal_transfer', '=', False), ('currency_id.name', '!=', 'ARS'), ('payment_type', '=', 'outbound')]` |

> **Note:** All rules include `('is_internal_transfer', '=', False)` to exclude
> internal transfers (Bank & Cash > Transfers) from the approval flow.
> Transfers are company-to-company movements that do not require third-party
> payment approval.

> **Note:** Branches are not used in the current Econovo setup even though they
> appear in the database. Rules 1 and 2 explicitly exclude `company_id = 3`
> (Buenos Aires) to avoid double-approval overlap with Rule 3.

---

## Authorisation Tiers — Journal Entries

Econovo uses three approval tiers for journal entries
(`account.move.action_post`) that touch specific liability/payable accounts.
Unlike payment rules, these apply to **all companies** (no branch exclusion)
and are **independent of this module** — they are native Studio Approval Rules
that do not require any custom code.

| Tier | Rule name | Scope | Domain summary |
|------|-----------|-------|----------------|
| **High-value (ARS)** | Aprobación Asientos Mayores ≥ $1M | ARS entries ≥ $1,000,000 touching monitored accounts | `move_type=entry`, `currency=ARS`, `amount_total >= 1M`, `line account code in [33 codes]` |
| **Standard (ARS)** | Aprobación Asientos Menores < $1M | ARS entries < $1,000,000 touching monitored accounts | `move_type=entry`, `currency=ARS`, `amount_total < 1M`, `line account code in [33 codes]` |
| **Foreign currency (FX)** | Aprobación Asientos Exterior (FX) | Non-ARS entries touching monitored accounts | `move_type=entry`, `currency != ARS`, `line account code in [33 codes]` |

> **Note:** These rules share the same approval groups as the equivalent
> payment tiers (Pagos Mayores, Pagos Menores, Pagos Exterior). No new groups
> are needed.

> **Note:** The `amount_total` field on `account.move` with `move_type='entry'`
> represents the sum of all debit amounts in the journal entry.

### Full domain pattern

All three rules share the same account code filter. Only the currency and
amount conditions differ:

```python
# High-value ARS (Rule 44 on staging2)
[('move_type', '=', 'entry'),
 ('currency_id.name', '=', 'ARS'),
 ('amount_total', '>=', 1000000),
 ('line_ids.account_id.code', 'in', [<33 account codes>])]

# Standard ARS (Rule 45 on staging2)
[('move_type', '=', 'entry'),
 ('currency_id.name', '=', 'ARS'),
 ('amount_total', '<', 1000000),
 ('line_ids.account_id.code', 'in', [<33 account codes>])]

# Foreign currency (Rule 46 on staging2)
[('move_type', '=', 'entry'),
 ('currency_id.name', '!=', 'ARS'),
 ('line_ids.account_id.code', 'in', [<33 account codes>])]
```

### Monitored Account Codes (33 accounts)

These accounts trigger approval when used in `move_type='entry'` journal entries:

| Code | Name | Category |
|------|------|----------|
| `2.1.1.01.025` | Pagaré Bursátiles a pagar | Pagarés |
| `2.1.2.02.001` | Préstamo Banco Nación | Préstamos bancarios |
| `2.1.2.02.002` | Préstamo Banco Macro | Préstamos bancarios |
| `2.1.2.02.003` | Préstamo Banco Córdoba | Préstamos bancarios |
| `2.1.2.02.004` | Préstamo Banco ICBC | Préstamos bancarios |
| `2.1.2.02.005` | Préstamo Banco Supervielle | Préstamos bancarios |
| `2.1.2.02.006` | Préstamo Banco Nación no Corriente | Préstamos bancarios |
| `2.1.2.02.017` | Préstamo Banco Santa Fe | Préstamos bancarios |
| `2.1.2.02.018` | Préstamo Banco Comafi | Préstamos bancarios |
| `2.1.2.02.019` | Préstamo Banco Santander | Préstamos bancarios |
| `2.1.3.01.001` | Tasa Comercio e Industria Oncativo | Tasas municipales |
| `2.1.3.01.002` | Tasa Comercio e Industria Córdoba | Tasas municipales |
| `2.1.3.01.003` | Tasa Municipal de Berazategui | Tasas municipales |
| `2.1.3.01.010` | Tasa Municipal a pagar | Tasas municipales |
| `2.1.3.01.020` | Plan Tasa Municipal a pagar | Tasas municipales |
| `2.1.3.02.010` | IIBB a pagar | Impuestos provinciales |
| `2.1.3.02.020` | SICORE a pagar | Retenciones |
| `2.1.3.02.021` | Ret. Gan. Sueldos a Dep. | Retenciones |
| `2.1.3.02.520` | Plan de IIBB a pagar | Impuestos provinciales |
| `2.1.3.03.020` | IVA saldo a pagar | IVA |
| `2.1.3.04.010` | Impuesto a las ganancias a pagar | Impuesto a las ganancias |
| `2.1.4.01.010` | Sueldos a pagar | Sueldos y cargas sociales |
| `2.1.4.01.020` | Leyes Sociales a pagar | Sueldos y cargas sociales |
| `2.1.4.01.030` | Seguro de Vida a Pagar | Sueldos y cargas sociales |
| `2.1.4.01.040` | ART a Pagar | Sueldos y cargas sociales |
| `2.1.4.01.051` | ADIMRA a pagar | Sindicatos |
| `2.1.4.01.052` | FAECYS a pagar | Sindicatos |
| `2.1.4.01.053` | INACAP a pagar | Sindicatos |
| `2.1.4.01.054` | UOM a pagar | Sindicatos |
| `2.1.4.01.056` | SEC Berazategui a pagar | Sindicatos |
| `2.1.4.01.057` | Obra Social Conv. Empresa a pagar | Sueldos y cargas sociales |
| `2.1.4.01.060` | Embargos a depositar | Sueldos y cargas sociales |
| `2.1.5.01.001` | Planes de pago | Planes de pago |

---

## Security Groups

### Groups installed by this module

| Group | XML ID | Purpose |
|-------|--------|---------|
| Payment Batch Approvers | `econovo_payment_batch_approval.grp_aprobadores_lote_pago` | Grants visibility of the **Approve Batch** button on the batch form. |

### Groups for approval tiers

These groups can be created automatically by Studio when rules are saved,
or pre-created via XML-RPC (recommended for repeatable staging setup).
They are not shipped by this module's data files.

| Group | Associated tier |
|-------|----------------|
| Aprobadores — Pagos Mayores | High-value (ARS) |
| Aprobadores — Pagos Menores | Standard (ARS) |
| Aprobadores — Buenos Aires | Buenos Aires branch |
| Aprobadores — Pagos Exterior | Foreign currency (FX) |

---

## Group Membership by Role

Assign users to groups based on their role. Branches are not considered;
membership decisions are based on seniority and operational scope.

| Group | Roles that should be members |
|-------|------------------------------|
| Aprobadores — Pagos Mayores | Senior management, Finance manager, System admin |
| Aprobadores — Pagos Menores | All payment approvers, Finance manager, System admin |
| Aprobadores — Buenos Aires | Buenos Aires approvers, Finance manager, System admin |
| Aprobadores — Pagos Exterior | FX-authorised approvers, Finance manager, System admin |
| **Payment Batch Approvers** | All payment approvers, Finance manager, System admin |

---

## Studio Activity Assignment (Critical)

For Studio approval rules, there are two different notification mechanisms:

1. `users_to_notify`: posts an internal note/chatter mention.
2. `responsible_id`: creates the pending Activity (`mail.activity`) assigned to a user.

If `responsible_id` is not configured correctly, the chatter may show
"approval requested" but the approver will not get a pending activity.

### Required values in Staging1

| Rule | `users_to_notify` | `responsible_id` |
|------|-------------------|------------------|
| Aprobación Pagos Mayores ≥ $1M (49) | Filoni (9) | Filoni (9) |
| Aprobación Pagos Menores < $1M (50) | Massola (372) | Massola (372) |
| Aprobación Pagos Buenos Aires (51) | Filoni (9), Massola (372) | Define according to operational owner |
| Aprobación Pagos Exterior (52) | Filoni (9), Massola (372) | Define according to operational owner |

> Recommendation: Always set `responsible_id` explicitly on every rule.
> Do not rely only on `users_to_notify` if Activities are part of the process.

---

## Environment Record IDs

These IDs are database-specific and are provided for reference when using
direct database tools (MCP, psql, scripts).

### Staging1 (`econovo-pruebas.odoo.com`)

DB: `econovo-180326-29905628`

**Payment rules (`account.payment.action_post`):**

| Record | Model | ID |
|--------|-------|----|
| Aprobación Pagos Mayores ≥ $1M | `studio.approval.rule` | 49 |
| Aprobación Pagos Menores < $1M | `studio.approval.rule` | 50 |
| Aprobación Pagos Buenos Aires | `studio.approval.rule` | 51 |
| Aprobación Pagos Exterior (FX) | `studio.approval.rule` | 52 |

**Journal entry rules (`account.move.action_post`):**

| Record | Model | ID |
|--------|-------|----|
| Aprobación Asientos Mayores ≥ $1M | `studio.approval.rule` | 53 |
| Aprobación Asientos Menores < $1M | `studio.approval.rule` | 54 |
| Aprobación Asientos Exterior (FX) | `studio.approval.rule` | 55 |

**Groups (shared by both payment and journal entry rules):**

| Record | Model | ID |
|--------|-------|----|
| Aprobadores — Pagos Mayores | `res.groups` | 263 |
| Aprobadores — Pagos Menores | `res.groups` | 264 |
| Aprobadores — Buenos Aires | `res.groups` | 265 |
| Aprobadores — Pagos Exterior | `res.groups` | 266 |
| Payment Batch Approvers | `res.groups` | 262 |

**Group XML IDs (`ir.model.data`, module = `econovo_payment_batch_approval`):**

| XML name | Points to group ID |
|----------|--------------------|
| `approval_payments_major` | 263 |
| `approval_payments_minor` | 264 |
| `approval_payments_bsas` | 265 |
| `approval_payments_fx` | 266 |

### Staging2 (`econovo-pruebas2.odoo.com`)

**Payment rules (`account.payment.action_post`):**

| Record | Model | ID |
|--------|-------|----|
| Aprobación Pagos Mayores ≥ $1M | `studio.approval.rule` | 40 |
| Aprobación Pagos Menores < $1M | `studio.approval.rule` | 41 |
| Aprobación Pagos Buenos Aires | `studio.approval.rule` | 42 |
| Aprobación Pagos Exterior (FX) | `studio.approval.rule` | 43 |

**Journal entry rules (`account.move.action_post`):**

| Record | Model | ID |
|--------|-------|----|
| Aprobación Asientos Mayores ≥ $1M | `studio.approval.rule` | 44 |
| Aprobación Asientos Menores < $1M | `studio.approval.rule` | 45 |
| Aprobación Asientos Exterior (FX) | `studio.approval.rule` | 46 |

**Groups (shared by both payment and journal entry rules):**

| Record | Model | ID |
|--------|-------|----|
| Aprobadores — Pagos Mayores | `res.groups` | 271 |
| Aprobadores — Pagos Menores | `res.groups` | 272 |
| Aprobadores — Buenos Aires | `res.groups` | 273 |
| Aprobadores — Pagos Exterior | `res.groups` | 274 |
| Payment Batch Approvers | `res.groups` | 276 |

### Production (`econovo.odoo.com`)

> To be completed after production deployment.

---

## Post-Install Checklist

Run after installing the module on any environment:

### Payment rules
- [ ] Create the 4 Studio Approval Rules for payments (see Payment Tiers table above)
- [ ] Verify the 4 approval groups were created by Studio
- [ ] Add users to each Studio approval group according to their role
- [ ] Find the `Payment Batch Approvers` group ID (`res.groups` where name = 'Payment Batch Approvers')
- [ ] Add users to `Payment Batch Approvers`
- [ ] Create a test batch with at least one Draft payment
- [ ] Log in as a batch approver and verify the **Approve Batch** button is visible
- [ ] Click **Approve Batch** and verify payments transition to Posted
- [ ] Verify the accounting entries are correct (debit/credit accounts, amounts, date)

### Journal entry rules
- [ ] Create the 3 Studio Approval Rules for journal entries (see Journal Entry Tiers table above)
- [ ] Verify the rules share the same groups as the payment rules (no new groups needed)
- [ ] Create a test journal entry touching one of the 33 monitored accounts
- [ ] Verify approval is requested when trying to post the entry
- [ ] Approve and verify the entry transitions to Posted

### Record IDs
- [ ] Record all environment-specific IDs in the tables above

### MCP snippet — add users to Payment Batch Approvers

```python
# 1. Find the group ID
result = env['res.groups'].search([('name', '=', 'Payment Batch Approvers')])
group_id = result[0].id

# 2. Add users (Command 4 = link existing record)
#    Replace user IDs with the actual IDs for this environment.
env['res.groups'].browse(group_id).write({
    'users': [[4, <user_id_1>], [4, <user_id_2>], ...]
})
```

---

## Production Replication Runbook (For AI Agents)

Use this runbook when another AI agent must replicate the same approval setup
in production without changing module code.

### Scope

This process configures only database data:

1. Approval groups (`res.groups`)
2. XML IDs for groups (`ir.model.data`)
3. Studio approval rules (`studio.approval.rule`)
4. User assignments to groups (`res.users.groups_id`)
5. Rule notification and activity assignment (`users_to_notify`, `responsible_id`)
6. Optional backfill of pending activities for existing draft payments

### Safety Rules

1. Do not modify Python code in the module.
2. Use idempotent operations: search first, then create/update.
3. Validate target URL and DB before writing.
4. Apply in this order: groups -> XML IDs -> rules -> users -> verification.
5. Keep a plain-text execution log with created/updated IDs.

### Required Inputs

Prepare these values before running scripts:

1. `url`: production Odoo URL
2. `db`: production database name
3. `api_key`: API key of an admin-capable technical user
4. User IDs for:
    - Filoni
    - Massola
    - Beltramo
    - Villarreal
5. Confirm company ID for Buenos Aires logic (currently `3`)

### Execution Steps

1. Clone staging setup into production with:
    - [../../../../../scripts/_setup_studio_approvals_xmlrpc.py](../../../../../scripts/_setup_studio_approvals_xmlrpc.py)
2. Adjust connection variables (`url`, `db`, `api_key`) to production.
3. Run script and capture output IDs.
4. Enforce Studio activity behavior with:
    - [../../../../../scripts/_fix_studio_responsible_and_backfill_filoni.py](../../../../../scripts/_fix_studio_responsible_and_backfill_filoni.py)
5. Adjust connection variables to production.
6. Run script to ensure:
    - Rule 49 responsible = Filoni
    - Rule 50 responsible = Massola
    - Missing activities are backfilled on matching draft payments

### Mandatory Verifications

After execution, verify all points below:

1. Rules 49-55 equivalent records exist in production (IDs may differ).
2. Payment rules have correct domains and groups.
3. `users_to_notify` and `responsible_id` are both configured.
4. Beltramo and Villarreal belong to `Payment Batch Approvers`.
5. Filoni and Massola belong to the expected approval groups.
6. Test one draft payment >= 1M ARS and one < 1M ARS:
    - Chatter note is posted
    - Activity is assigned to the correct responsible user
7. Batch approval button remains visible only for `Payment Batch Approvers`.

### Troubleshooting Note (Known Behavior)

If chatter shows approval requested but no pending activity is created:

1. Check `studio.approval.rule.responsible_id`.
2. Do not rely only on `users_to_notify`.
3. Re-run the responsible/activity fix script.

### Evidence to Store

Keep this evidence in the rollout ticket:

1. Script outputs (created/updated IDs)
2. Screenshots of one high-value and one low-value payment approval request
3. Screenshot of assigned activity inbox for responsible users
4. Final mapping table: rule name -> group -> responsible -> users_to_notify
