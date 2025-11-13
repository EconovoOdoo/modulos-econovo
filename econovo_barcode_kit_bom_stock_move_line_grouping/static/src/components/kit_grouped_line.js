/** @odoo-module **/

import GroupedLineComponent from "@stock_barcode/components/grouped_line";
import { patch } from "@web/core/utils/patch";

patch(GroupedLineComponent.prototype, {
    
    get componentClasses() {
        let classes = super.componentClasses || '';
        
        if (this.line.is_kit_group) {
            classes += ' o_barcode_kit_group';
            
            if (this.line.has_multiple_source_locations) {
                classes += ' o_barcode_kit_multi_source';
            }
            
            if (this.line.has_multiple_dest_locations) {
                classes += ' o_barcode_kit_multi_dest';
            }
        }
        
        return classes;
    },
    
});
