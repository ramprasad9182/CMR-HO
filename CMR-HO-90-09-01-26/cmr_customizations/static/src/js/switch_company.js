/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SwitchCompanyMenu } from "@web/webclient/switch_company_menu/switch_company_menu";
import { useState } from "@odoo/owl";

patch(SwitchCompanyMenu.prototype, {
    setup() {
        super.setup();
        this.originalCompanyIds = this.companyService.activeCompanyIds.slice();
        this.state = useState({
            hasChanges: false,
            pendingSelection: this.companyService.activeCompanyIds.slice()
        });

        this._patchCompanySelector();
    },

    _patchCompanySelector() {
        this.companySelector._debouncedApply = () => {};

        this.companySelector.switchCompany = (mode, companyId) => {
            if (mode === "toggle") {
                if (this.companySelector.selectedCompaniesIds.includes(companyId)) {
                    this.companySelector._deselectCompany(companyId);
                } else {
                    this.companySelector._selectCompany(companyId);
                }
            } else if (mode === "loginto") {
                if (this.companySelector._isSingleCompanyMode()) {
                    this.companySelector.selectedCompaniesIds.splice(0, this.companySelector.selectedCompaniesIds.length);
                }
                this.companySelector._selectCompany(companyId, true);
            }

            this.state.pendingSelection = this.companySelector.selectedCompaniesIds.slice();
            this.state.hasChanges = true;
        };

        this.companySelector.applyChanges = () => {
            this.companySelector._apply();
            this.originalCompanyIds = this.state.pendingSelection.slice();
            this.state.hasChanges = false;
            this.closeDropdown();
        };

        this.companySelector.cancelChanges = () => {
            this.companySelector.selectedCompaniesIds = this.originalCompanyIds.slice();
            this.state.pendingSelection = this.originalCompanyIds.slice();
            this.state.hasChanges = false;
            this.closeDropdown();
        };

        this.companySelector._selectCompany = (companyId, unshift = false) => {
            if (!this.companySelector.selectedCompaniesIds.includes(companyId)) {
                if (unshift) {
                    this.companySelector.selectedCompaniesIds.unshift(companyId);
                } else {
                    this.companySelector.selectedCompaniesIds.push(companyId);
                }
            } else if (unshift) {
                const index = this.companySelector.selectedCompaniesIds.findIndex(c => c === companyId);
                this.companySelector.selectedCompaniesIds.splice(index, 1);
                this.companySelector.selectedCompaniesIds.unshift(companyId);
            }
            this.companySelector._getBranches(companyId).forEach(companyId => this.companySelector._selectCompany(companyId));
        };

        this.companySelector._deselectCompany = (companyId) => {
            if (this.companySelector.selectedCompaniesIds.includes(companyId)) {
                this.companySelector.selectedCompaniesIds.splice(
                    this.companySelector.selectedCompaniesIds.indexOf(companyId),
                    1
                );
                this.companySelector._getBranches(companyId).forEach(companyId => this.companySelector._deselectCompany(companyId));
            }
        };

        this.companySelector._getBranches = (companyId) => {
            return this.companyService.getCompany(companyId).child_ids;
        };
    },

    closeDropdown() {
        if (this.__owl__.dropdownRef) {
            this.__owl__.dropdownRef.close();
        }
    }
});