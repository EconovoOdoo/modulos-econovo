/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { MainMenu } from "@stock_barcode/main_menu";
import { ManualBarcodeScanner } from "@stock_barcode/components/manual_barcode";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

/**
 * Patch the MainMenu component to add manual barcode entry functionality.
 * This approach has low coupling with the original module and is easily
 * maintainable across Odoo version upgrades.
 */
patch(MainMenu.prototype, {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
    },

    /**
     * Opens the manual barcode scanner dialog.
     * Reuses the existing ManualBarcodeScanner component from stock_barcode.
     */
    openManualBarcodeEntry() {
        this.dialogService.add(ManualBarcodeScanner, {
            openMobileScanner: async () => {
                await this.openMobileScanner();
            },
            onApply: (barcode) => {
                if (barcode) {
                    this._onBarcodeScanned(barcode);
                    return barcode;
                }
                return false;
            },
        });
    },
});
