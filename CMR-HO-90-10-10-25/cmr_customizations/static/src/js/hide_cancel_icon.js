/** @odoo-module **/

import { registry } from "@web/core/registry";

const fieldRegistry = registry.category("fields");

// Get the existing many2many field
const OriginalMany2Many = fieldRegistry.get("many2many");

// Only patch if component and Renderer exist
if (OriginalMany2Many && OriginalMany2Many.components?.Renderer) {
    const PatchedRenderer = {
        isRemovable(record) {
            if (this.props?.field?.name === "picking_ids") {
                return false; // ✅ Hide the ✖️ icon only for picking_ids
            }
            return super.isRemovable(record);
        },
    };

    const CustomMany2Many = {
        ...OriginalMany2Many,
        components: {
            ...OriginalMany2Many.components,
            Renderer: {
                ...OriginalMany2Many.components.Renderer,
                ...PatchedRenderer,
            },
        },
    };

    registry.category("fields").add("many2many_no_remove", CustomMany2Many);
}