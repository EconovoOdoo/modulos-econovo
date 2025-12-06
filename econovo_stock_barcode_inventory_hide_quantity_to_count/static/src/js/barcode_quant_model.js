/** @odoo-module **/

import BarcodeQuantModel from "@stock_barcode/models/barcode_quant_model";
import { patch } from "@web/core/utils/patch";

patch(BarcodeQuantModel.prototype, {
    /**
     * Check if we are in blind count mode (quantity to count is hidden).
     *
     * @returns {boolean} True if blind count mode is active
     */
    get hideQuantityToCount() {
        return this.groups && this.groups.show_quantity_to_count === false;
    },

    /**
     * Override displaySetButton to hide the "Set Full Quantity" button in blind count mode.
     * This prevents operators from auto-filling with the real stock quantity,
     * which would break the anonymity of the blind count.
     *
     * @returns {boolean} Whether to display the Set button
     */
    get displaySetButton() {
        if (this.hideQuantityToCount) {
            return false;
        }
        return super.displaySetButton;
    },

    /**
     * Get the real quantity demand for internal use (e.g., completion status).
     * This method always returns the actual value, regardless of blind count mode.
     *
     * @param {Object} line - The inventory line
     * @returns {number} The actual quantity demand
     */
    getRealQtyDemand(line) {
        return super.getQtyDemand(line);
    },

    /**
     * Override getQtyDemand to return false when show_quantity_to_count is disabled.
     * This hides the expected quantity in the barcode app for blind counting.
     * Note: Use getRealQtyDemand() to get the actual value for internal calculations.
     *
     * @param {Object} line - The inventory line
     * @returns {number|false} The quantity demand or false if hidden
     */
    getQtyDemand(line) {
        if (this.hideQuantityToCount) {
            return false;
        }
        return super.getQtyDemand(line);
    },
});
