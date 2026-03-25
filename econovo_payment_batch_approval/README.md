# Payment Batch Approval

**Version:** 17.0.1.1.0 | **License:** AGPL-3 | **Odoo:** 17.0

Bridges **Odoo Studio Approval Rules** on `account.payment.action_post` with
the **Sumitec payment batch module** (`account_payment_batch_st`), and adds a
one-click bulk-approval action to batch payment forms.

---

## Table of Contents

- [Features](#features)
- [Dependencies](#dependencies)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Known Issues](#known-issues)
- [Credits](#credits)

---

## Features

- **Batch persistence fix:** Overrides `action_post_and_new` to pre-assign the
  batch payment record before Studio intercepts `action_post`. This ensures the
  batch is preserved in context even when the payment is blocked by an approval
  rule, keeping the "Confirm and New" chaining flow intact.

- **Bulk approval:** Adds an **Approve Batch** button to the batch payment form.
  When clicked by an authorised approver, it creates `studio.approval.entry`
  records for every applicable Studio Approval Rule on each draft payment in the
  batch, then calls `action_post()` on all of them in one transaction.
  Pending *Grant Approval* activities on each payment are automatically marked
  as done, attributed to the batch approver, with the batch name as feedback.
  The form soft-refreshes automatically after approval.

- **Approval group:** Installs the `Payment Batch Approvers` security group that
  controls visibility of the Approve Batch button.

---

## Dependencies

| Module | Source | Notes |
|--------|--------|-------|
| `account` | Odoo core | Vendor payments |
| `account_payment_batch_st` | Sumitec (`sumitec-odoo/account-payment-batch`) | Batch payment model |
| `web_studio` | Odoo Enterprise | Studio Approval Rules engine |

---

## Installation

1. Copy the module to your Odoo addons path.
2. Update the addons list (`Apps → Update Apps List`).
3. Search for **Payment Batch Approval** and click **Install**.

The module installs the following automatically:

| Record | Type | XML ID |
|--------|------|--------|
| Payment Batch Approvers | `res.groups` | `econovo_payment_batch_approval.grp_aprobadores_lote_pago` |

---

## Configuration

After installation, two steps are required **per environment**. They are not
automated because Studio stores approval rules directly in the database and
cannot export them as XML data files.

### Step 1 — Create Studio Approval Rules

Go to **Studio → Approval Rules** and create one rule for each authorisation
tier required. Each rule must target:

- **Model:** `account.payment`
- **Method:** `action_post`
- **Group:** a `res.groups` whose members are the approvers for that tier
- **Domain:** *(optional)* filter to restrict which payments trigger the rule

Example domain patterns:

```python
# Payments above a threshold (local currency, outbound)
[('amount', '>=', 1000000), ('currency_id.name', '=', 'ARS'), ('payment_type', '=', 'outbound')]

# Payments below a threshold (local currency, outbound)
[('amount', '<', 1000000), ('currency_id.name', '=', 'ARS'), ('payment_type', '=', 'outbound')]

# Payments in foreign currency
[('currency_id.name', '!=', 'ARS'), ('payment_type', '=', 'outbound')]

# Payments belonging to a specific company (multi-company setup)
[('journal_id.company_id', '=', <company_id>), ('payment_type', '=', 'outbound')]
```

> **Important:** Domains are evaluated per payment. If a payment matches
> multiple rules, the approver must satisfy **all** of them. Design domains so
> that each payment is covered by exactly the rules intended for its tier.

### Step 2 — Assign users to groups

Add the appropriate users to:

- The groups linked to each Studio Approval Rule (controls who can approve
  individual payments via the Studio Approval widget on each payment form).
- The **Payment Batch Approvers** group installed by this module (controls who
  sees the **Approve Batch** button on the batch form).

Go to **Settings → Users & Companies → Groups**, search for each group, and
add users from the **Users** tab.

> In a typical setup, the members of *Payment Batch Approvers* are the same
> users who belong to the Studio Approval groups. They are managed separately
> because they serve different purposes: Studio groups gate individual payment
> posting; the batch group gates the bulk-approval shortcut.

---

## Usage

### Treasurer flow — creating payments

1. Open a vendor payment and click **Confirm and New**.
2. Studio blocks posting (payment stays Draft). The batch is already assigned
   thanks to the pre-assignment fix in this module.
3. The next payment form opens pre-linked to the same batch.
4. Repeat until all payments are entered. The batch now holds N Draft payments.

### Approver flow — approving a batch

1. Open the batch payment form.
2. If any payment is in Draft state, the **Approve Batch** button is visible
   (requires membership in *Payment Batch Approvers*).
3. Click **Approve Batch**. The module:
   - Finds all active Studio Approval Rules whose domain matches each payment.
   - Creates a `studio.approval.entry` (approved=True) for each rule × payment.
   - Marks each pending *Grant Approval* activity as done (attributed to the
     batch approver, feedback includes the batch name).
   - Calls `action_post()` on all draft payments. Studio finds the pre-created
     entries and allows posting to proceed.
4. The form soft-refreshes in place. The button disappears and all payments
   show **Posted** status. No pending approval activities remain.

---

## Known Issues

- Studio Approval Rules are stored in the database via the Studio UI and cannot
  be packaged as XML data files. Each environment requires manual setup after
  installation (see [Configuration](#configuration)).

- `action_post_and_new` is provided by the `account_payment_pro` module
  (ingadhoc/account-payment). If that module is not installed the batch-chaining
  fix in this module has no effect, but it is harmless.

- The bulk approval bypasses the individual per-payment approval UI confirmation
  dialogs. This is intentional: the **Approve Batch** button is itself the
  confirmation step, restricted to users in *Payment Batch Approvers*.

---

## Credits

### Authors

- Jose D. Leonett (<https://github.com/josedleonett>)

### Maintainers

This module is maintained by [Econovo](https://github.com/EconovoOdoo).
