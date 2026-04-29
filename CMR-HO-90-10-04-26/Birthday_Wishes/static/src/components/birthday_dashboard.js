/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class BirthdayDashboard extends Component {
    setup() {
        this.orm = useService("orm");

        this.state = useState({
            birthdays: [],
            anniversaries: [],
        });

        onMounted(async () => {
            // Load birthdays
            const birthdayData = await this.orm.call(
                "hr.employee",
                "get_today_birthdays",
                []
            );
            this.state.birthdays = birthdayData;

            // Load anniversaries
            const anniversaryData = await this.orm.call(
                "hr.employee",
                "get_today_anniversaries",
                []
            );
            this.state.anniversaries = anniversaryData;
        });
    }
}

BirthdayDashboard.template = "owl.birthdayDashboard";
registry.category("actions").add("birthdayDashboardOWL", BirthdayDashboard);
