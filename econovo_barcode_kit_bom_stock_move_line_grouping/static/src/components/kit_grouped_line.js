/** @odoo-module **/

import GroupedLineComponent from "@stock_barcode/components/grouped_line";
import { KitSublineComponent } from "./kit_subline";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";

patch(GroupedLineComponent, {
    components: {
        ...GroupedLineComponent.components,
        KitSublineComponent,
    },
});

patch(GroupedLineComponent.prototype, {
    
    setup() {
        super.setup(...arguments);
        // Local state for nested groups inside kits
        if (this.line.is_nested_in_kit) {
            this.nestedState = useState({ opened: false });
        }
    },
    
    get opened() {
        // If this is a nested group inside a kit, use local state
        if (this.line.is_nested_in_kit && this.nestedState) {
            return this.nestedState.opened;
        }
        
        // Otherwise use model state (for kits and regular groups)
        const lineKey = this.env.model.groupKey(this.line);
        return this.env.model.unfoldedLineKeys 
            ? this.env.model.unfoldedLineKeys.has(lineKey)
            : this.env.model.unfoldLineKey === lineKey;
    },
    
    toggleSublines(ev) {
        ev.stopPropagation();
        
        // If this is a nested group inside a kit, toggle local state only
        if (this.line.is_nested_in_kit && this.nestedState) {
            this.nestedState.opened = !this.nestedState.opened;
            return;
        }
        
        // For kit groups or regular groups, use model
        this.env.model.toggleSublines(this.line);
    },
    
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
