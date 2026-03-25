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
| **High-value (ARS)** | Aprobación Pagos Mayores ≥ $1M | Outbound ARS payments ≥ $1,000,000 from any company except Buenos Aires | `[('amount', '>=', 1000000), ('journal_id.company_id', '!=', 3), ('currency_id.name', '=', 'ARS'), ('payment_type', '=', 'outbound')]` |
| **Standard (ARS)** | Aprobación Pagos Menores < $1M | Outbound ARS payments < $1,000,000 from any company except Buenos Aires | `[('amount', '<', 1000000), ('journal_id.company_id', '!=', 3), ('currency_id.name', '=', 'ARS'), ('payment_type', '=', 'outbound')]` |
| **Buenos Aires branch** | Aprobación Pagos Buenos Aires | All outbound payments from company ID 3 (Buenos Aires) | `[('journal_id.company_id', '=', 3), ('payment_type', '=', 'outbound')]` |
| **Foreign currency (FX)** | Aprobación Pagos Exterior (FX) | All outbound payments in any currency other than ARS | `[('currency_id.name', '!=', 'ARS'), ('payment_type', '=', 'outbound')]` |

> **Note:** Branches are not used in the current Econovo setup even though they
> appear in the database. Rules 1 and 2 explicitly exclude `company_id = 3`
> (Buenos Aires) to avoid double-approval overlap with Rule 3.

---

## Security Groups

### Groups installed by this module

| Group | XML ID | Purpose |
|-------|--------|---------|
| Payment Batch Approvers | `econovo_payment_batch_approval.grp_aprobadores_lote_pago` | Grants visibility of the **Approve Batch** button on the batch form. |

### Groups created by Studio (one per approval tier)

These groups are created automatically by Studio when the rules are saved.
They are not part of this module and cannot be managed via XML.

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

## Environment Record IDs

These IDs are database-specific and are provided for reference when using
direct database tools (MCP, psql, scripts).

### Staging (`econovo-pruebas2.odoo.com`)

| Record | Model | ID |
|--------|-------|----|
| Aprobación Pagos Mayores ≥ $1M | `studio.approval.rule` | 40 |
| Aprobación Pagos Menores < $1M | `studio.approval.rule` | 41 |
| Aprobación Pagos Buenos Aires | `studio.approval.rule` | 42 |
| Aprobación Pagos Exterior (FX) | `studio.approval.rule` | 43 |
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

- [ ] Create the 4 Studio Approval Rules (see domains in the Tiers table above)
- [ ] Verify the 4 approval groups were created by Studio
- [ ] Add users to each Studio approval group according to their role
- [ ] Find the `Payment Batch Approvers` group ID (`res.groups` where name = 'Payment Batch Approvers')
- [ ] Add users to `Payment Batch Approvers`
- [ ] Create a test batch with at least one Draft payment
- [ ] Log in as a batch approver and verify the **Approve Batch** button is visible
- [ ] Click **Approve Batch** and verify payments transition to Posted
- [ ] Verify the accounting entries are correct (debit/credit accounts, amounts, date)
- [ ] Record environment IDs in the table above

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
