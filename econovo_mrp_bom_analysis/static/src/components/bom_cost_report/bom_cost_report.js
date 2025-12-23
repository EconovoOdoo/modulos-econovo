/** @odoo-module */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { View } from "@web/views/view";
import { Component, onWillStart, useState } from "@odoo/owl";

export class BomCostReport extends Component {
    static template = "econovo_mrp_bom_analysis.BomCostReport";
    static components = { Layout, View };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        
        this.state = useState({
            bomId: null,
            treeData: [],  // Hierarchical tree data for left panel
            loading: true,
            selectedNodeId: null,
            bomName: '',
            bomProduct: '',
            totalCost: 0,
            currencySymbol: '$',
            allExpanded: true,
        });

        // Reactive view props for the embedded tree view
        this.viewProps = useState({
            domain: [],
            context: {},
        });

        onWillStart(async () => {
            await this.loadTreeData();
        });
    }

    async loadTreeData() {
        const bomId = this.props.action?.context?.active_id || 
                      this.props.action?.context?.bom_id;
        
        if (!bomId) {
            this.state.loading = false;
            return;
        }

        this.state.bomId = bomId;

        try {
            // Load BOM info
            const bom = await this.orm.read("mrp.bom", [bomId], ["display_name", "product_id", "product_tmpl_id"]);
            if (bom.length) {
                this.state.bomName = bom[0].display_name;
                this.state.bomProduct = bom[0].product_id ? bom[0].product_id[1] : '';
            }

            // Load all analysis records with parent info
            const analysisRecords = await this.orm.searchRead(
                "bom.component.analysis",
                [["root_bom_id", "=", bomId]],
                ["id", "name", "product_id", "source_bom_id", "level", "total_cost", 
                 "is_subassembly", "parent_component_id", "child_bom_id"],
                { order: "level, sequence, id" }
            );

            // Build hierarchical tree structure
            this.state.treeData = this.buildHierarchicalTree(analysisRecords);
            
            // Calculate total cost from level 0
            const level0Records = analysisRecords.filter(r => r.level === 0);
            this.state.totalCost = level0Records.reduce((sum, r) => sum + (r.total_cost || 0), 0);

            // Set initial domain to show all
            this.viewProps.domain = [["root_bom_id", "=", bomId]];
            this.viewProps.context = {
                search_default_group_by_category: 1,
                search_default_group_by_product: 1,
                search_default_group_by_source_bom: 1,
            };

        } catch (error) {
            console.error("Error loading BOM tree data:", error);
        }
        
        this.state.loading = false;
    }

    buildHierarchicalTree(records) {
        // Create a map of records by ID
        const recordMap = {};
        const rootNodes = [];

        // First pass: create node objects
        for (const record of records) {
            recordMap[record.id] = {
                id: record.id,
                name: record.name,
                modelLevel: record.level, // Original level from model
                depth: 0, // Will be calculated based on tree structure
                totalCost: record.total_cost || 0,
                isSubassembly: record.is_subassembly,
                hasChildBom: !!record.child_bom_id,
                parentId: record.parent_component_id ? record.parent_component_id[0] : null,
                sourceBomId: record.source_bom_id ? record.source_bom_id[0] : null,
                sourceBomName: record.source_bom_id ? record.source_bom_id[1] : null,
                children: [],
                expanded: true,
                visible: true,
            };
        }

        // Second pass: build hierarchy
        for (const record of records) {
            const node = recordMap[record.id];
            if (node.parentId && recordMap[node.parentId]) {
                recordMap[node.parentId].children.push(node);
            } else {
                // Root level node
                rootNodes.push(node);
            }
        }

        // Third pass: calculate depth based on tree structure
        this.calculateDepth(rootNodes, 0);

        return rootNodes;
    }

    calculateDepth(nodes, depth) {
        for (const node of nodes) {
            node.depth = depth;
            if (node.children && node.children.length > 0) {
                this.calculateDepth(node.children, depth + 1);
            }
        }
    }

    // -------------------------------------------------------------------------
    // Getters
    // -------------------------------------------------------------------------
    get hasData() {
        return this.state.treeData && this.state.treeData.length > 0;
    }

    get displayConfig() {
        return {
            controlPanel: {},
        };
    }

    get embeddedViewProps() {
        return {
            type: "list",
            resModel: "bom.component.analysis",
            domain: this.viewProps.domain,
            context: this.viewProps.context,
            searchViewId: false,
            display: { controlPanel: true },
            allowSelectors: false,
        };
    }

    get viewKey() {
        // Generate a unique key based on domain to force re-render
        return JSON.stringify(this.viewProps.domain);
    }

    // -------------------------------------------------------------------------
    // Tree traversal helpers
    // -------------------------------------------------------------------------
    flattenTree(nodes, result = []) {
        for (const node of nodes) {
            result.push(node);
            if (node.children && node.children.length > 0) {
                this.flattenTree(node.children, result);
            }
        }
        return result;
    }

    getAllNodeIds(nodes, ids = []) {
        for (const node of nodes) {
            ids.push(node.id);
            if (node.children && node.children.length > 0) {
                this.getAllNodeIds(node.children, ids);
            }
        }
        return ids;
    }

    getChildrenIds(node) {
        // Get only direct children IDs, not the node itself
        if (!node.children || node.children.length === 0) {
            return [];
        }
        // Get all descendant IDs (children, grandchildren, etc.) but NOT the node itself
        return this.getAllNodeIds(node.children);
    }

    // -------------------------------------------------------------------------
    // Handlers
    // -------------------------------------------------------------------------
    onNodeClick(node) {
        this.state.selectedNodeId = node.id;
        
        // Get only children IDs (not including the clicked node itself)
        const childrenIds = this.getChildrenIds(node);
        
        if (childrenIds.length > 0) {
            // Node has children, show only children
            this.viewProps.domain = [["id", "in", childrenIds]];
        } else {
            // Node has no children (leaf node), show just itself
            this.viewProps.domain = [["id", "=", node.id]];
        }
    }

    onShowAll() {
        this.state.selectedNodeId = null;
        this.viewProps.domain = [["root_bom_id", "=", this.state.bomId]];
    }

    toggleNode(ev, node) {
        ev.stopPropagation();
        node.expanded = !node.expanded;
        this.updateChildVisibility(node);
    }

    updateChildVisibility(node) {
        for (const child of node.children) {
            child.visible = node.expanded;
            if (!node.expanded) {
                child.expanded = false;
            }
            this.updateChildVisibility(child);
        }
    }

    expandAll() {
        this.state.allExpanded = true;
        this.setAllExpanded(this.state.treeData, true);
    }

    collapseAll() {
        this.state.allExpanded = false;
        this.setAllExpanded(this.state.treeData, false);
    }

    setAllExpanded(nodes, expanded) {
        for (const node of nodes) {
            node.expanded = expanded;
            node.visible = true;
            if (node.children && node.children.length > 0) {
                this.setAllExpanded(node.children, expanded);
                // If collapsing, hide children
                if (!expanded) {
                    for (const child of node.children) {
                        child.visible = false;
                    }
                }
            }
        }
    }

    getNodeClasses(node) {
        let classes = 'o_bom_tree_node py-1 px-2 rounded mb-1 cursor-pointer d-flex align-items-center';
        if (node.id === this.state.selectedNodeId) {
            classes += ' bg-primary text-white';
        } else if (node.hasChildBom || node.isSubassembly) {
            classes += ' bg-light';
        }
        return classes;
    }

    formatCost(value) {
        if (!value) return '0.00';
        return value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }
}

registry.category("actions").add("bom_cost_report", BomCostReport);
