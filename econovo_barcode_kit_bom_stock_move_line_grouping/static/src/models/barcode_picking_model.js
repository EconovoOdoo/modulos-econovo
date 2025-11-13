/** @odoo-module **/

import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';
import { patch } from "@web/core/utils/patch";

/**
 * Barcode Kit/BOM Grouping Extension
 * Groups kit/BOM components together in the barcode app for cleaner UX.
 */

patch(BarcodePickingModel.prototype, {
    
    /**
     * Override groupKey to group kit components together regardless of source location.
     * @param {Object} line - stock.move.line record
     * @returns {string} - grouping key
     */
    groupKey(line) {
        const moveId = Array.isArray(line.move_id) ? line.move_id[0] : line.move_id;
        const move = moveId ? this.cache.getRecord('stock.move', moveId) : null;
        
        if (move && move.description_bom_line && move.description_bom_line !== 'EMPTY') {
            const kitName = move.description_bom_line.replace(/\s*-\s*\d+\/\d+\s*$/, '');
            return `kit_${kitName}_${line.location_dest_id.id}`;
        }
        
        return super.groupKey(...arguments);
    },

    /**
     * Override get groupedLines to force grouping of kit components.
     * @returns {Array} - Array of lines/groups
     */
    get groupedLines() {
        const baseLines = super.groupedLines;
        const kitComponents = [];
        const nonKitLines = [];
        
        for (const line of baseLines) {
            if (line.lines && line.lines.length > 0) {
                const firstSubline = line.lines[0];
                const moveId = Array.isArray(firstSubline.move_id) ? firstSubline.move_id[0] : firstSubline.move_id;
                const move = moveId ? this.cache.getRecord('stock.move', moveId) : null;
                
                if (move && move.description_bom_line && move.description_bom_line !== 'EMPTY') {
                    for (const subline of line.lines) {
                        kitComponents.push(subline);
                    }
                    continue;
                }
                
                nonKitLines.push(line);
                continue;
            }
            
            const moveId = Array.isArray(line.move_id) ? line.move_id[0] : line.move_id;
            const move = moveId ? this.cache.getRecord('stock.move', moveId) : null;
            
            if (move && move.description_bom_line && move.description_bom_line !== 'EMPTY') {
                kitComponents.push(line);
            } else {
                nonKitLines.push(line);
            }
        }
        
        const kitGroups = {};
        for (const component of kitComponents) {
            const key = this.groupKey(component);
            if (!kitGroups[key]) {
                kitGroups[key] = [];
            }
            kitGroups[key].push(component);
        }
        
        for (const [key, components] of Object.entries(kitGroups)) {
            if (components.length === 0) continue;
            
            const firstMoveId = Array.isArray(components[0].move_id) ? components[0].move_id[0] : components[0].move_id;
            const firstMove = this.cache.getRecord('stock.move', firstMoveId);
            const kitName = firstMove.description_bom_line.replace(/\s*-\s*\d+\/\d+\s*$/, '');
            
            const uniqueSourceLocs = new Set(components.map(l => l.location_id.id));
            const uniqueDestLocs = new Set(components.map(l => l.location_dest_id.id));
            
            const ids = components.map(c => c.id);
            const virtual_ids = components.map(c => c.virtual_id);
            
            let qtyDemand = 0;
            let qtyDone = 0;
            for (const component of components) {
                qtyDemand += this.getQtyDemand(component);
                qtyDone += this.getQtyDone(component);
            }

            const groupedLine = this._groupSublines(components, ids, virtual_ids, qtyDemand, qtyDone);
            
            groupedLine.is_kit_group = true;
            groupedLine.kit_name = kitName;
            groupedLine.component_count = components.length;
            groupedLine.has_multiple_source_locations = uniqueSourceLocs.size > 1;
            groupedLine.source_location_count = uniqueSourceLocs.size;
            groupedLine.has_multiple_dest_locations = uniqueDestLocs.size > 1;
            groupedLine.dest_location_count = uniqueDestLocs.size;
            
            nonKitLines.push(groupedLine);
        }
        
        return this._sortLine(nonKitLines);
    },
});
