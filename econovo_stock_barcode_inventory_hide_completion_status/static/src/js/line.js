/** @odoo-module **/

import LineComponent from "@stock_barcode/components/line";
import { patch } from "@web/core/utils/patch";

patch(LineComponent.prototype, {
    get hideCompletionStatus() {
        const isInventoryAdjustment = this.env.model.resModel === 'stock.quant';
        return isInventoryAdjustment &&
               this.env.model.groups &&
               this.env.model.groups.show_completion_status === false;
    },

    get componentClasses() {
        if (this.hideCompletionStatus) {
            const isCounted = this.quantityIsSet;
            return [
                'o_line_neutral',
                isCounted ? 'o_line_counted' : '',
                this.isSelected ? 'o_selected o_highlight' : ''
            ].join(' ');
        }
        return [
            this.isComplete ? 'o_line_completed' : 'o_line_not_completed',
            this.env.model.lineIsFaulty(this.line) ? 'o_faulty' : '',
            this.isSelected ? 'o_selected o_highlight' : ''
        ].join(' ');
    },
});
