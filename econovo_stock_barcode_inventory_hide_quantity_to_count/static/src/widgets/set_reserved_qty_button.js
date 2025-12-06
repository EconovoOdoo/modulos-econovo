/** @odoo-module **/

import { SetReservedQuantityButton } from "@stock_barcode/widgets/set_reserved_qty_button";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

patch(SetReservedQuantityButton.prototype, {
    setup() {
        super.setup();
        const user = useService("user");
        const orm = useService("orm");
        this.hideQuantityToCount = false;

        onWillStart(async () => {
            const companyId = user.context.allowed_company_ids?.[0];
            if (companyId) {
                const result = await orm.read("res.company", [companyId], ["show_quantity_to_count"]);
                this.hideQuantityToCount = result[0]?.show_quantity_to_count === false;
            }
        });
    },

    /**
     * Override _setQuantity to prevent auto-filling in blind count mode.
     * This button would reveal the real stock quantity if clicked.
     */
    _setQuantity(ev) {
        if (this.hideQuantityToCount) {
            ev.stopPropagation();
            return;
        }
        super._setQuantity(ev);
    },
});
