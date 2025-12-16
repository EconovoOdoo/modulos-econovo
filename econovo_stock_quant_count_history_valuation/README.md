# Stock Quant Count History - Valuation

## Description

This module extends `econovo_stock_quant_count_history` to add cost valuation capabilities, 
allowing users to see the financial impact of inventory counts in both company currency (ARS) 
and USD.

## Features

### Inventory Adjustments View (Preview)
- **Unit Cost columns** - Shows current product cost in company currency and USD
- **Difference Value columns** - Shows projected value impact before applying adjustment
- Visual indicators: red for losses, green for gains
- All columns are optional and can be shown/hidden via column selector

### Cost Snapshot (Count History)
- Captures unit cost at the moment of count
- Records cost method (Standard, FIFO, Average)
- Stores exchange rate at count time

### Dual Currency Support
- Values displayed in company currency (ARS)
- Values also displayed in USD
- Compatible with `gg_cost_dolarization` module (optional)

### SVL Integration
- Links to Stock Valuation Layers when counts are applied
- Provides actual valuation from SVL when available
- Falls back to snapshot valuation for saved counts

### Visual Indicators
- Loss/Gain highlighting in list view
- Color-coded difference values
- Filter by losses/gains

## Dependencies

**Required:**
- `econovo_stock_quant_count_history`
- `stock_account`

**Optional:**
- `gg_cost_dolarization` - For enhanced USD cost tracking

## Usage

### Inventory Adjustments View

1. Go to **Inventory > Operations > Inventory Adjustments**
2. Use the column selector (⚙️) to show valuation columns:
   - **Unit Cost** - Product cost in company currency
   - **Cost USD** - Product cost in USD
   - **Diff. Value** - Projected difference value in company currency
   - **Diff. USD** - Projected difference value in USD
3. Values update automatically when you enter counted quantities
4. Red = Loss, Green = Gain

### Count History

1. Install the module after `econovo_stock_quant_count_history`
2. Existing count histories will automatically get valuation records
3. New count histories will create valuations automatically
4. View valuation details in the "Valuation" tab of count history form
5. Filter by losses/gains in the list view

## Technical Notes

### Hybrid Valuation Model

The module uses a hybrid approach:
1. **Snapshot values** - Captured at count moment, always available
2. **SVL values** - Linked when count is applied, provides actual valuation

Final values use SVL when available, otherwise snapshot.

### Exchange Rate Lookup

- Uses `res.currency.rate` to find rate on or before count date
- Falls back to most recent rate if no rate exists for date
- Returns 1.0 if no USD rate configured

### Edge Cases Handled

- Products without cost (standard_price = 0)
- Different cost methods (Standard, FIFO, AVCO)
- Multi-company scenarios
- Missing currency rates
- Saved vs Applied counts
- Consumable products (no SVL)

## Author

- **Author:** Jose D. Leonett
- **Website:** https://github.com/josedleonett
- **License:** AGPL-3
