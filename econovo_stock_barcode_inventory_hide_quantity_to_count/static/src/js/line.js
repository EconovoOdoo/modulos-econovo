/** @odoo-module **/

import LineComponent from "@stock_barcode/components/line";
import { patch } from "@web/core/utils/patch";

patch(LineComponent.prototype, {
    /**
     * Get the real quantity demand for completion status calculation.
     * Uses getRealQtyDemand if available (when blind count module is active),
     * otherwise falls back to the standard getQtyDemand.
     *
     * @returns {number} The real quantity demand
     */
    get realQtyDemand() {
        if (this.env.model.getRealQtyDemand) {
            return this.applyRounding(this.env.model.getRealQtyDemand(this.line));
        }
        return this.qtyDemand;
    },

    /**
     * Override isComplete to use the real quantity demand for completion status.
     * This ensures the visual feedback (green/red) works correctly even when
     * the displayed quantity is hidden in blind count mode.
     *
     * @returns {boolean} Whether the line is complete
     */
    get isComplete() {
        const realDemand = this.realQtyDemand;
        if (!realDemand || realDemand != this.qtyDone) {
            return false;
        } else if (this.isTracked && !this.lotName) {
            return false;
        }
        return true;
    },
});
