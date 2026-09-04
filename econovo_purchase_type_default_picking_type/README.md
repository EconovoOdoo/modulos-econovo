# Purchase Order Type - Default Operation Type

Lets each **Purchase Order Type** carry its own default receipt **Operation Type**
("Deliver To"), so choosing a type on a purchase order also applies the operation type
it was configured with.

## Problem

`purchase_order_type` (OCA) already lets a Purchase Order Type preset the **Payment
Terms** and the **Incoterm** onto the order, but has no way to preset the receipt
**Operation Type**. Companies that route different kinds of purchases (for example
regular purchases vs. COMEX/import) through dedicated warehouses/operation types have
to remember to pick the right one by hand on every single order.

## Solution

Adds an optional **Deliver To** field on Purchase Order Type, restricted to receipt
(`incoming`) operation types of the *same company* as the type (a Purchase Order Type
shared across companies - blank `Company` - cannot preset one, since an operation type
always belongs to a single company).

When the order's **Type** is set (manually, or automatically from the partner's default
type), the existing `onchange` that already copies Payment Terms/Incoterm from the type
now also copies this Operation Type onto the order, exactly the same way.

The preset is only applied interactively (`onchange`), like the pre-existing Payment
Terms/Incoterm preset - it never overrides an Operation Type already computed by
automated flows (reordering rules, MRP, etc.).

## Usage

1. Go to **Purchase > Configuration > Purchase Order Types** and open (or create) a
   type.
2. Set its **Company** to a single company (required to unlock the next field).
3. Set **Deliver To** to the receipt operation type this type should default to.
4. On a purchase order, selecting that **Type** now also sets **Deliver To**.

## Technical

- `purchase.order.type.picking_type_id` - new optional Many2one, domain restricted to
  `code = 'incoming'` operation types of the same `company_id` as the type; constrained
  so it can only be set together with a single-company type, and only to an operation
  type of that exact company.
- `purchase.order.onchange_order_type()` - extended (calls `super()` first) to also
  copy `picking_type_id` from the type onto the order, guarded so it is skipped if the
  type's preset Operation Type belongs to a different company than the order.

## Author

Jose D. Leonett - AGPL-3
