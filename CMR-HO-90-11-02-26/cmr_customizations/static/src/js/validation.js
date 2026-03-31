/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { odooExceptionTitleMap } from "@web/core/errors/error_dialogs";



let currentValue = odooExceptionTitleMap.get("odoo.exceptions.ValidationError");

odooExceptionTitleMap.set("odoo.exceptions.ValidationError", _t(""));