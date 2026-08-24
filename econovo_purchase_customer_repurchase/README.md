# Purchase - Repurchase from Customer

Lets a receipt buy back goods **from the customer location** instead of the vendor
location, so repurchasing an item that was previously sold clears the balance left
behind by the original delivery.

## Problem

When an item sold to a dealer is later bought back from that same dealer as a regular
purchase, Odoo moves it in from `Partners/Vendors` while the original delivery left a
balance in `Partners/Customers`. Those two virtual locations are never netted against
each other, so the item stays recorded as delivered to a customer *and* available in
stock at the same time.

For serial-tracked products this is not just cosmetic. The next delivery of that serial
number is rejected by `stock.quant.check_quantity()`:

> The serial number has already been assigned

because validating it would leave 2 units of the same serial in the customer location.

## Why the operation type alone is not enough

`purchase.order._prepare_picking()` and `purchase.order.line._prepare_stock_move_vals()`
both hardcode the source location to `res.partner.property_stock_supplier`. That value is
passed explicitly to `create()`, which bypasses `stock.picking._compute_location_id()` —
so the `default_location_src_id` of the operation type is ignored for any receipt
generated from a purchase order. The destination is honoured, the source is not.

## Solution

Adds a **Repurchase from Customer** flag on incoming operation types. When a purchase
order uses such an operation type, its receipt and the underlying stock moves are sourced
from the partner's customer location (`property_stock_customer`, falling back to the
warehouse partner location) instead of the vendor location.

Nothing else about the purchase flow changes: the order, the vendor bill and the
valuation stay exactly as they are. The flag is opt-in per operation type, so regular
purchases from the same contact are unaffected.

## Usage

1. Go to **Inventory > Configuration > Operation Types** and create (or open) a receipt
   type, for example *"Repurchase from Dealer"*.
2. Tick **Repurchase from Customer**.
3. On the purchase order, select that operation type in **Deliver To**.

The generated receipt will source from the customer location, and validating it will
bring the serial number back to stock while clearing its customer balance.

## Technical

- `stock.picking.type.is_customer_repurchase` — new boolean, constrained to `code == 'incoming'`.
- `purchase.order._get_customer_repurchase_location()` — resolves the source location.
- `purchase.order._prepare_picking()` and `purchase.order.line._prepare_stock_move_vals()`
  are overridden to apply it.

## Author

Jose D. Leonett — AGPL-3
