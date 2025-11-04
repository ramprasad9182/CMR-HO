from odoo import models, fields, api


class CheckList(models.Model):
    _name = "check.lists"
    _description = "Check List"
    _rec_name = "name"

    name = fields.Char(string='sequence', required=True, copy=False, readonly=True, default='New')

    designated_opening_manager = fields.Many2one("hr.employee", string="Designated Opening Manager")
    designated_closing_manager = fields.Many2one("hr.employee", string="Designated closing Manager")
    security_on_duty_opening = fields.Many2one("hr.employee", string="Security On Duty Opening")
    security_on_duty_closing = fields.Many2one("hr.employee", string="Security On Duty Closing")
    date_opening = fields.Date(string="Date")
    date_closing = fields.Date(string="Date")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('check.lists') or 'New'
        return super().create(vals)

    two_wheeler_four_wheeler_opening = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No")
        ],
        string="Two wheeler / four wheeler at alloted space"
    )

    two_wheeler_four_wheeler_text_opening = fields.Text(string="Two wheeler / four wheeler at alloted space")
    two_wheeler_four_wheeler_closing = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No")
        ], string="Two wheeler / four wheeler at alloted space")
    two_wheeler_four_wheeler_text_closing = fields.Text(string="Two wheeler / four wheeler at alloted space")
    parking_area = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No")
        ], string=" Parking area cleanliness")
    parking_area_text_opening = fields.Text(string=" Parking area cleanliness")
    parking_area_closing = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No")
        ], string=" Parking area cleanliness")
    parking_area_text_closing = fields.Text(string=" Parking area cleanliness")

    main_sign_board = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No")
        ],
        string="Main sign board cleanliness / lighting"
    )
    main_sign_board_text_opening = fields.Text(
        string="Main sign board cleanliness / lighting (Opening Remarks)"
    )
    main_sign_board_closing = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No")
        ],
        string="Main sign board cleanliness / lighting (Closing)"
    )
    main_sign_board_text_closing = fields.Text(
        string="Main sign board cleanliness / lighting (Closing Remarks)"
    )

    display_boards = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No")
        ],
        string="Display boards/kiosks/banners / posters"
    )
    display_boards_text_opening = fields.Text(
        string="Display boards/kiosks/banners / posters (Opening Remarks)"
    )
    display_boards_closing = fields.Selection(
        [
            ("yes", "Yes"),
            ("no", "No")
        ],
        string="Display boards/kiosks/banners / posters (Closing)"
    )
    display_boards_text_closing = fields.Text(
        string="Display boards/kiosks/banners / posters (Closing Remarks)"
    )

    # Entrance security attendance
    entrance_security_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Entrance security attendance"
    )
    entrance_security_text_opening = fields.Text(string="Entrance security attendance")
    entrance_security_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Entrance security attendance"
    )
    entrance_security_text_closing = fields.Text(string="Entrance security attendance")

    # Grooming
    grooming_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Grooming"
    )
    grooming_text_opening = fields.Text(string="Grooming")
    grooming_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Grooming"
    )
    grooming_text_closing = fields.Text(string="Grooming")

    # Security desk registers/communications
    security_desk_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Security desk registers/communications"
    )
    security_desk_text_opening = fields.Text(string="Security desk registers/communications")
    security_desk_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Security desk registers/communications"
    )
    security_desk_text_closing = fields.Text(string="Security desk registers/communications")

    # Shutter Lock Seal (main & staff entry)
    shutter_lock_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Shutter Lock Seal (main & staff entry)"
    )
    shutter_lock_text_opening = fields.Text(string="Shutter Lock Seal (main & staff entry)")
    shutter_lock_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Shutter Lock Seal (main & staff entry)"
    )
    shutter_lock_text_closing = fields.Text(string="Shutter Lock Seal (main & staff entry)")

    # Staff Entrance/Exit Door Seal
    staff_entrance_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Staff Entrance/Exit Door Seal"
    )
    staff_entrance_text_opening = fields.Text(string="Staff Entrance/Exit Door Seal")
    staff_entrance_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Staff Entrance/Exit Door Seal"
    )
    staff_entrance_text_closing = fields.Text(string="Staff Entrance/Exit Door Seal")

    # Back Office Main Door Seal
    back_office_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Back Office Main Door Seal"
    )
    back_office_text_opening = fields.Text(string="Back Office Main Door Seal")
    back_office_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Back Office Main Door Seal"
    )
    back_office_text_closing = fields.Text(string="Back Office Main Door Seal")

    # Seal of the IT room
    it_room_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Seal of the IT room"
    )
    it_room_text_opening = fields.Text(string="Seal of the IT room")
    it_room_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Seal of the IT room"
    )
    it_room_text_closing = fields.Text(string="Seal of the IT room")

    # Seal of all counters/shelves/drawers (high value items)
    counters_shelves_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Seal of all counters/shelves/drawers (high value items)"
    )
    counters_shelves_text_opening = fields.Text(string="Seal of all counters/shelves/drawers (high value items)")
    counters_shelves_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Seal of all counters/shelves/drawers (high value items)"
    )
    counters_shelves_text_closing = fields.Text(string="Seal of all counters/shelves/drawers (high value items)")

    # Seal of the Customer Entry shutter/Seals on the Glass Gates
    customer_entry_seal_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Seal of the Customer Entry shutter/Seals on the Glass Gates"
    )
    customer_entry_seal_text_opening = fields.Text(string="Seal of the Customer Entry shutter/Seals on the Glass Gates")
    customer_entry_seal_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Seal of the Customer Entry shutter/Seals on the Glass Gates"
    )
    customer_entry_seal_text_closing = fields.Text(string="Seal of the Customer Entry shutter/Seals on the Glass Gates")

    # Are the Computers switched ON/OFF in the back office
    computers_back_office_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are the Computers switched ON/OFF in the back office"
    )
    computers_back_office_text_opening = fields.Text(string="Are the Computers switched ON/OFF in the back office")
    computers_back_office_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are the Computers switched ON/OFF in the back office"
    )
    computers_back_office_text_closing = fields.Text(string="Are the Computers switched ON/OFF in the back office")

    # Are the trial rooms clear of merchandise
    trial_rooms_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are the trial rooms clear of merchandise"
    )
    trial_rooms_text_opening = fields.Text(string="Are the trial rooms clear of merchandise")
    trial_rooms_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are the trial rooms clear of merchandise"
    )
    trial_rooms_text_closing = fields.Text(string="Are the trial rooms clear of merchandise")

    # Are the Unclaimed baggage recorded and stored
    unclaimed_baggage_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are the Unclaimed baggage recorded and stored"
    )
    unclaimed_baggage_text_opening = fields.Text(string="Are the Unclaimed baggage recorded and stored")
    unclaimed_baggage_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are the Unclaimed baggage recorded and stored"
    )
    unclaimed_baggage_text_closing = fields.Text(string="Are the Unclaimed baggage recorded and stored")

    # Staff in uniform & shoes
    staff_uniform_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Staff in uniform & shoes"
    )
    staff_uniform_text_opening = fields.Text(string="Staff in uniform & shoes")
    staff_uniform_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Staff in uniform & shoes"
    )
    staff_uniform_text_closing = fields.Text(string="Staff in uniform & shoes")

    # Staff are well groomed as per norms
    staff_groomed_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Staff are well groomed as per norms"
    )
    staff_groomed_text_opening = fields.Text(string="Staff are well groomed as per norms")
    staff_groomed_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Staff are well groomed as per norms"
    )
    staff_groomed_text_closing = fields.Text(string="Staff are well groomed as per norms")

    # House keeping, brand promoters uniforms & grooming are as per norms
    housekeeping_uniform_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="House keeping, brand promoters uniforms & grooming are as per norms"
    )
    housekeeping_uniform_text_opening = fields.Text(
        string="House keeping, brand promoters uniforms & grooming are as per norms")
    housekeeping_uniform_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="House keeping, brand promoters uniforms & grooming are as per norms"
    )
    housekeeping_uniform_text_closing = fields.Text(
        string="House keeping, brand promoters uniforms & grooming are as per norms")

    # All staff on floor as per the roster
    staff_on_floor_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All staff on floor as per the roster"
    )
    staff_on_floor_text_opening = fields.Text(string="All staff on floor as per the roster")
    staff_on_floor_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All staff on floor as per the roster"
    )
    staff_on_floor_text_closing = fields.Text(string="All staff on floor as per the roster")

    # Store briefing as per norms
    store_briefing_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Store briefing as per norms"
    )
    store_briefing_text_opening = fields.Text(string="Store briefing as per norms")
    store_briefing_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Store briefing as per norms"
    )
    store_briefing_text_closing = fields.Text(string="Store briefing as per norms")

    # Is the Floor Clear of unauthorized persons
    floor_clear_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is the Floor Clear of unauthorized persons"
    )
    floor_clear_text_opening = fields.Text(string="Is the Floor Clear of unauthorized persons")
    floor_clear_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is the Floor Clear of unauthorized persons"
    )
    floor_clear_text_closing = fields.Text(string="Is the Floor Clear of unauthorized persons")
    # 1 All category signages
    all_category_signages_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All category signages"
    )
    all_category_signages_text_opening = fields.Text(string="All category signages")
    all_category_signages_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All category signages"
    )
    all_category_signages_text_closing = fields.Text(string="All category signages")

    # 2 All shelves / under shelves are clean
    shelves_clean_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All shelves / under shelves are clean"
    )
    shelves_clean_text_opening = fields.Text(string="All shelves / under shelves are clean")
    shelves_clean_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All shelves / under shelves are clean"
    )
    shelves_clean_text_closing = fields.Text(string="All shelves / under shelves are clean")

    # 3 All products dusting happened
    products_dusting_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All products dusting happened"
    )
    products_dusting_text_opening = fields.Text(string="All products dusting happened")
    products_dusting_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All products dusting happened"
    )
    products_dusting_text_closing = fields.Text(string="All products dusting happened")

    # 4 Shelf talkers
    shelf_talkers_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Shelf talkers"
    )
    shelf_talkers_text_opening = fields.Text(string="Shelf talkers")
    shelf_talkers_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Shelf talkers"
    )
    shelf_talkers_text_closing = fields.Text(string="Shelf talkers")

    # 5 Display tables / Standees / Bins / vendor
    display_tables_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Display tables / Standees / Bins / vendor"
    )
    display_tables_text_opening = fields.Text(string="Display tables / Standees / Bins / vendor")
    display_tables_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Display tables / Standees / Bins / vendor"
    )
    display_tables_text_closing = fields.Text(string="Display tables / Standees / Bins / vendor")

    # 6 Free from pests / insects / cobwebs
    pests_free_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Free from pests / insects / cobwebs"
    )
    pests_free_text_opening = fields.Text(string="Free from pests / insects / cobwebs")
    pests_free_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Free from pests / insects / cobwebs"
    )
    pests_free_text_closing = fields.Text(string="Free from pests / insects / cobwebs")

    # 7 Posters not to be stuck on wall or pillars
    posters_not_stuck_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Posters not to be stuck on wall or pillars"
    )
    posters_not_stuck_text_opening = fields.Text(string="Posters not to be stuck on wall or pillars")
    posters_not_stuck_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Posters not to be stuck on wall or pillars"
    )
    posters_not_stuck_text_closing = fields.Text(string="Posters not to be stuck on wall or pillars")

    # 8 No mark or impressions of cello tape
    cello_tape_marks_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="No mark or impressions of cello tape"
    )
    cello_tape_marks_text_opening = fields.Text(string="No mark or impressions of cello tape")
    cello_tape_marks_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="No mark or impressions of cello tape"
    )
    cello_tape_marks_text_closing = fields.Text(string="No mark or impressions of cello tape")

    # 9 Own fixtures / Vendor fixtures are in tack
    fixtures_intact_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Own fixtures / Vendor fixtures are in tack"
    )
    fixtures_intact_text_opening = fields.Text(string="Own fixtures / Vendor fixtures are in tack")
    fixtures_intact_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Own fixtures / Vendor fixtures are in tack"
    )
    fixtures_intact_text_closing = fields.Text(string="Own fixtures / Vendor fixtures are in tack")

    # 10 Trail rooms are to cleaned
    trial_rooms_clean_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Trail rooms are to cleaned"
    )
    trial_rooms_clean_text_opening = fields.Text(string="Trail rooms are to cleaned")
    trial_rooms_clean_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Trail rooms are to cleaned"
    )
    trial_rooms_clean_text_closing = fields.Text(string="Trail rooms are to cleaned")

    # 11 Tailor rooms are to cleaned
    tailor_rooms_clean_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Tailor rooms are to cleaned"
    )
    tailor_rooms_clean_text_opening = fields.Text(string="Tailor rooms are to cleaned")
    tailor_rooms_clean_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Tailor rooms are to cleaned"
    )
    tailor_rooms_clean_text_closing = fields.Text(string="Tailor rooms are to cleaned")

    # 12 Availability of Customer feedback forms
    customer_feedback_forms_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Availability of Customer feedback forms"
    )
    customer_feedback_forms_text_opening = fields.Text(string="Availability of Customer feedback forms")
    customer_feedback_forms_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Availability of Customer feedback forms"
    )
    customer_feedback_forms_text_closing = fields.Text(string="Availability of Customer feedback forms")

    # 13 Availability of exchange passes / alteration forms
    exchange_passes_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Availability of exchange passes / alteration forms"
    )
    exchange_passes_text_opening = fields.Text(string="Availability of exchange passes / alteration forms")
    exchange_passes_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Availability of exchange passes / alteration forms"
    )
    exchange_passes_text_closing = fields.Text(string="Availability of exchange passes / alteration forms")
    # 1 Dust bins/Door mats / Broken tiles
    dust_bins_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Dust bins/Door mats / Broken tiles"
    )
    dust_bins_text_opening = fields.Text(string="Dust bins/Door mats / Broken tiles")
    dust_bins_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Dust bins/Door mats / Broken tiles"
    )
    dust_bins_text_closing = fields.Text(string="Dust bins/Door mats / Broken tiles")

    # 2 Promo Materials
    promo_materials_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Promo Materials"
    )
    promo_materials_text_opening = fields.Text(string="Promo Materials")
    promo_materials_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Promo Materials"
    )
    promo_materials_text_closing = fields.Text(string="Promo Materials")

    # 3 Glass panes / doors Cleanliness & 50% of space to be free
    glass_panes_clean_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Glass panes / doors Cleanliness & 50% of space to be free"
    )
    glass_panes_clean_text_opening = fields.Text(string="Glass panes / doors Cleanliness & 50% of space to be free")
    glass_panes_clean_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Glass panes / doors Cleanliness & 50% of space to be free"
    )
    glass_panes_clean_text_closing = fields.Text(string="Glass panes / doors Cleanliness & 50% of space to be free")

    # 4 Washrooms are dry , clean and odor free
    washrooms_clean_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Washrooms are dry , clean and odor free"
    )
    washrooms_clean_text_opening = fields.Text(string="Washrooms are dry , clean and odor free")
    washrooms_clean_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Washrooms are dry , clean and odor free"
    )
    washrooms_clean_text_closing = fields.Text(string="Washrooms are dry , clean and odor free")

    # 5 Warehouse receiving area
    warehouse_receiving_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Warehouse receiving area"
    )
    warehouse_receiving_text_opening = fields.Text(string="Warehouse receiving area")
    warehouse_receiving_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Warehouse receiving area"
    )
    warehouse_receiving_text_closing = fields.Text(string="Warehouse receiving area")

    # 6 CSD
    csd_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="CSD"
    )
    csd_text_opening = fields.Text(string="CSD")
    csd_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="CSD"
    )
    csd_text_closing = fields.Text(string="CSD")

    # 1 Aisles without cartons / gunny bags
    aisles_cartons_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Aisles without cartons / gunny bags"
    )
    aisles_cartons_text_opening = fields.Text(string="Aisles without cartons / gunny bags")
    aisles_cartons_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Aisles without cartons / gunny bags"
    )
    aisles_cartons_text_closing = fields.Text(string="Aisles without cartons / gunny bags")

    # 2 Shopping bags / baskets availability at entrance
    shopping_bags_availability_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Shopping bags / baskets availability at entrance"
    )
    shopping_bags_availability_text_opening = fields.Text(string="Shopping bags / baskets availability at entrance")
    shopping_bags_availability_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Shopping bags / baskets availability at entrance"
    )
    shopping_bags_availability_text_closing = fields.Text(string="Shopping bags / baskets availability at entrance")

    # 3 Lifts/ Escalators/ Lights / fans / Acs are clean and in working
    lifts_clean_working_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Lifts/ Escalators/ Lights / fans / Acs are clean and in working"
    )
    lifts_clean_working_text_opening = fields.Text(
        string="Lifts/ Escalators/ Lights / fans / Acs are clean and in working")
    lifts_clean_working_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Lifts/ Escalators/ Lights / fans / Acs are clean and in working"
    )
    lifts_clean_working_text_closing = fields.Text(
        string="Lifts/ Escalators/ Lights / fans / Acs are clean and in working")

    # 4 Fire extinguisers & emergency equipments are clean & in working
    fire_extinguishers_working_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Fire extinguishers & emergency equipments are clean & in working"
    )
    fire_extinguishers_working_text_opening = fields.Text(
        string="Fire extinguishers & emergency equipments are clean & in working")
    fire_extinguishers_working_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Fire extinguishers & emergency equipments are clean & in working"
    )
    fire_extinguishers_working_text_closing = fields.Text(
        string="Fire extinguishers & emergency equipments are clean & in working")

    # 5 Sponsered fixtures based on HO approvals
    sponsored_fixtures_ho_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Sponsored fixtures based on HO approvals"
    )
    sponsored_fixtures_ho_text_opening = fields.Text(string="Sponsored fixtures based on HO approvals")
    sponsored_fixtures_ho_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Sponsored fixtures based on HO approvals"
    )
    sponsored_fixtures_ho_text_closing = fields.Text(string="Sponsored fixtures based on HO approvals")

    # 6 Hassle free check out area for " Customer Q "
    checkout_area_customer_q_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string='Hassle free check out area for "Customer Q"'
    )
    checkout_area_customer_q_text_opening = fields.Text(string='Hassle free check out area for "Customer Q"')
    checkout_area_customer_q_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string='Hassle free check out area for "Customer Q"'
    )
    checkout_area_customer_q_text_closing = fields.Text(string='Hassle free check out area for "Customer Q"')
    # 1 Store directory standees are at place
    store_directory_standees_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Store directory standees are at place"
    )
    store_directory_standees_text_opening = fields.Text(string="Store directory standees are at place")
    store_directory_standees_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Store directory standees are at place"
    )
    store_directory_standees_text_closing = fields.Text(string="Store directory standees are at place")

    # 2 Display must be neat and order and in tidy rows
    display_neat_order_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Display must be neat and order and in tidy rows"
    )
    display_neat_order_text_opening = fields.Text(string="Display must be neat and order and in tidy rows")
    display_neat_order_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Display must be neat and order and in tidy rows"
    )
    display_neat_order_text_closing = fields.Text(string="Display must be neat and order and in tidy rows")

    # 3 All articles are must touch the front edge of the shelves
    articles_front_edge_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All articles are must touch the front edge of the shelves"
    )
    articles_front_edge_text_opening = fields.Text(string="All articles are must touch the front edge of the shelves")
    articles_front_edge_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All articles are must touch the front edge of the shelves"
    )
    articles_front_edge_text_closing = fields.Text(string="All articles are must touch the front edge of the shelves")

    # 4 Private lables are displayed as per giudelines
    private_labels_guidelines_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Private labels are displayed as per guidelines"
    )
    private_labels_guidelines_text_opening = fields.Text(string="Private labels are displayed as per guidelines")
    private_labels_guidelines_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Private labels are displayed as per guidelines"
    )
    private_labels_guidelines_text_closing = fields.Text(string="Private labels are displayed as per guidelines")

    # 5 All TV’s & Screens are on
    tvs_screens_on_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All TV’s & Screens are on"
    )
    tvs_screens_on_text_opening = fields.Text(string="All TV’s & Screens are on")
    tvs_screens_on_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All TV’s & Screens are on"
    )
    tvs_screens_on_text_closing = fields.Text(string="All TV’s & Screens are on")

    # 6 Offer stocks display with POP
    offer_stocks_pop_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Offer stocks display with POP"
    )
    offer_stocks_pop_text_opening = fields.Text(string="Offer stocks display with POP")
    offer_stocks_pop_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Offer stocks display with POP"
    )
    offer_stocks_pop_text_closing = fields.Text(string="Offer stocks display with POP")

    # 7 Mannequins are well dressed and maintained well
    mannequins_well_dressed_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Mannequins are well dressed and maintained well"
    )
    mannequins_well_dressed_text_opening = fields.Text(string="Mannequins are well dressed and maintained well")
    mannequins_well_dressed_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Mannequins are well dressed and maintained well"
    )
    mannequins_well_dressed_text_closing = fields.Text(string="Mannequins are well dressed and maintained well")

    # 8 Highlighting of price of the products on mannequins
    highlight_price_mannequins_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Highlighting of price of the products on mannequins"
    )
    highlight_price_mannequins_text_opening = fields.Text(string="Highlighting of price of the products on mannequins")
    highlight_price_mannequins_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Highlighting of price of the products on mannequins"
    )
    highlight_price_mannequins_text_closing = fields.Text(string="Highlighting of price of the products on mannequins")

    # 9 Standees / Gondolas are placed as per planogram
    standees_gondolas_planogram_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Standees / Gondolas are placed as per planogram"
    )
    standees_gondolas_planogram_text_opening = fields.Text(string="Standees / Gondolas are placed as per planogram")
    standees_gondolas_planogram_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Standees / Gondolas are placed as per planogram"
    )
    standees_gondolas_planogram_text_closing = fields.Text(string="Standees / Gondolas are placed as per planogram")

    # 10 Availability of Promo stock
    promo_stock_availability_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Availability of Promo stock"
    )
    promo_stock_availability_text_opening = fields.Text(string="Availability of Promo stock")
    promo_stock_availability_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Availability of Promo stock"
    )
    promo_stock_availability_text_closing = fields.Text(string="Availability of Promo stock")

    # 11 Identifing gaps between MBQ vs SOH
    gaps_mbq_soh_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Identifying gaps between MBQ vs SOH"
    )
    gaps_mbq_soh_text_opening = fields.Text(string="Identifying gaps between MBQ vs SOH")
    gaps_mbq_soh_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Identifying gaps between MBQ vs SOH"
    )
    gaps_mbq_soh_text_closing = fields.Text(string="Identifying gaps between MBQ vs SOH")

    # 12 Indenting to warehouse
    indenting_warehouse_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Indenting to warehouse"
    )
    indenting_warehouse_text_opening = fields.Text(string="Indenting to warehouse")
    indenting_warehouse_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Indenting to warehouse"
    )
    indenting_warehouse_text_closing = fields.Text(string="Indenting to warehouse")

    # 13 Check FIFO ( Display and selling of Old and aged stock )
    check_fifo_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Check FIFO (Display and selling of Old and aged stock)"
    )
    check_fifo_text_opening = fields.Text(string="Check FIFO (Display and selling of Old and aged stock)")
    check_fifo_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Check FIFO (Display and selling of Old and aged stock)"
    )
    check_fifo_text_closing = fields.Text(string="Check FIFO (Display and selling of Old and aged stock)")

    # 14 Check any expiry stocks are there on floor
    expiry_stocks_floor_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Check any expiry stocks are there on floor"
    )
    expiry_stocks_floor_text_opening = fields.Text(string="Check any expiry stocks are there on floor")
    expiry_stocks_floor_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Check any expiry stocks are there on floor"
    )
    expiry_stocks_floor_text_closing = fields.Text(string="Check any expiry stocks are there on floor")

    # 15 Alteration products are at designated place
    alteration_products_place_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Alteration products are at designated place"
    )
    alteration_products_place_text_opening = fields.Text(string="Alteration products are at designated place")
    alteration_products_place_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Alteration products are at designated place"
    )
    alteration_products_place_text_closing = fields.Text(string="Alteration products are at designated place")


    # 1 Are billing counters clean and tidy
    billing_counters_clean_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are billing counters clean and tidy"
    )
    billing_counters_clean_text_opening = fields.Text(string="Are billing counters clean and tidy")
    billing_counters_clean_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are billing counters clean and tidy"
    )
    billing_counters_clean_text_closing = fields.Text(string="Are billing counters clean and tidy")

    # 2 Billing rolls & EDC rolls are in enough qty
    billing_rolls_qty_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Billing rolls & EDC rolls are in enough qty"
    )
    billing_rolls_qty_text_opening = fields.Text(string="Billing rolls & EDC rolls are in enough qty")
    billing_rolls_qty_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Billing rolls & EDC rolls are in enough qty"
    )
    billing_rolls_qty_text_closing = fields.Text(string="Billing rolls & EDC rolls are in enough qty")

    # 3 EDC machines are in working condition
    edc_working_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="EDC machines are in working condition"
    )
    edc_working_text_opening = fields.Text(string="EDC machines are in working condition")
    edc_working_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="EDC machines are in working condition"
    )
    edc_working_text_closing = fields.Text(string="EDC machines are in working condition")

    # 4 Wallet QR codes are clearly visible
    wallet_qr_visible_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Wallet QR codes are clearly visible"
    )
    wallet_qr_visible_text_opening = fields.Text(string="Wallet QR codes are clearly visible")
    wallet_qr_visible_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Wallet QR codes are clearly visible"
    )
    wallet_qr_visible_text_closing = fields.Text(string="Wallet QR codes are clearly visible")

    # 5 Is float cash available
    float_cash_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is float cash available"
    )
    float_cash_text_opening = fields.Text(string="Is float cash available")
    float_cash_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is float cash available"
    )
    float_cash_text_closing = fields.Text(string="Is float cash available")

    # 6 Manpower availability as per staff rooster
    manpower_rooster_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Manpower availability as per staff rooster"
    )
    manpower_rooster_text_opening = fields.Text(string="Manpower availability as per staff rooster")
    manpower_rooster_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Manpower availability as per staff rooster"
    )
    manpower_rooster_text_closing = fields.Text(string="Manpower availability as per staff rooster")

    # 7 Carry bags of all sizes in enough qty
    carry_bags_qty_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Carry bags of all sizes in enough qty"
    )
    carry_bags_qty_text_opening = fields.Text(string="Carry bags of all sizes in enough qty")
    carry_bags_qty_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Carry bags of all sizes in enough qty"
    )
    carry_bags_qty_text_closing = fields.Text(string="Carry bags of all sizes in enough qty")

    # 8 Manual bill books are available
    manual_bill_books_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Manual bill books are available"
    )
    manual_bill_books_text_opening = fields.Text(string="Manual bill books are available")
    manual_bill_books_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Manual bill books are available"
    )
    manual_bill_books_text_closing = fields.Text(string="Manual bill books are available")

    # 1 Is stock arranged category wise
    stock_category_arranged_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is stock arranged category wise"
    )
    stock_category_arranged_text_opening = fields.Text(string="Is stock arranged category wise")
    stock_category_arranged_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is stock arranged category wise"
    )
    stock_category_arranged_text_closing = fields.Text(string="Is stock arranged category wise")

    # 2 Foot wear size chart is sticked on wall
    footwear_size_chart_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Foot wear size chart is sticked on wall"
    )
    footwear_size_chart_text_opening = fields.Text(string="Foot wear size chart is sticked on wall")
    footwear_size_chart_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Foot wear size chart is sticked on wall"
    )
    footwear_size_chart_text_closing = fields.Text(string="Foot wear size chart is sticked on wall")

    # 3 Are there any no barcode items
    no_barcode_items_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are there any no barcode items"
    )
    no_barcode_items_text_opening = fields.Text(string="Are there any no barcode items")
    no_barcode_items_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are there any no barcode items"
    )
    no_barcode_items_text_closing = fields.Text(string="Are there any no barcode items")

    # 4 Are there any damaged items
    damaged_items_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are there any damaged items"
    )
    damaged_items_text_opening = fields.Text(string="Are there any damaged items")
    damaged_items_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are there any damaged items"
    )
    damaged_items_text_closing = fields.Text(string="Are there any damaged items")

    # 5 Are the stock placed size wise & pattern wise
    stock_size_pattern_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are the stock placed size wise & pattern wise"
    )
    stock_size_pattern_text_opening = fields.Text(string="Are the stock placed size wise & pattern wise")
    stock_size_pattern_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are the stock placed size wise & pattern wise"
    )
    stock_size_pattern_text_closing = fields.Text(string="Are the stock placed size wise & pattern wise")

    # 6 Are the stock placed easily accessible
    stock_accessible_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are the stock placed easily accessible"
    )
    stock_accessible_text_opening = fields.Text(string="Are the stock placed easily accessible")
    stock_accessible_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Are the stock placed easily accessible"
    )
    stock_accessible_text_closing = fields.Text(string="Are the stock placed easily accessible")

    # 1 Staff rooster is fixed
    staff_rooster_fixed_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Staff rooster is fixed"
    )
    staff_rooster_fixed_text_opening = fields.Text(string="Staff rooster is fixed")
    staff_rooster_fixed_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Staff rooster is fixed"
    )
    staff_rooster_fixed_text_closing = fields.Text(string="Staff rooster is fixed")

    # 2 All licenses are displayed
    all_licenses_displayed_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All licenses are displayed"
    )
    all_licenses_displayed_text_opening = fields.Text(string="All licenses are displayed")
    all_licenses_displayed_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All licenses are displayed"
    )
    all_licenses_displayed_text_closing = fields.Text(string="All licenses are displayed")

    # 3 AC & Lighting schedule
    ac_lighting_schedule_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="AC & Lighting schedule"
    )
    ac_lighting_schedule_text_opening = fields.Text(string="AC & Lighting schedule")
    ac_lighting_schedule_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="AC & Lighting schedule"
    )
    ac_lighting_schedule_text_closing = fields.Text(string="AC & Lighting schedule")
    # 1 Is PIHV carried out
    pihv_carried_out_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is PIHV carried out"
    )
    pihv_carried_out_text_opening = fields.Text(string="Is PIHV carried out")
    pihv_carried_out_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is PIHV carried out"
    )
    pihv_carried_out_text_closing = fields.Text(string="Is PIHV carried out")

    # 2 Is GRC done on the same day where direct purchase happens
    grc_same_day_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is GRC done on the same day where direct purchase happens"
    )
    grc_same_day_text_opening = fields.Text(string="Is GRC done on the same day where direct purchase happens")
    grc_same_day_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is GRC done on the same day where direct purchase happens"
    )
    grc_same_day_text_closing = fields.Text(string="Is GRC done on the same day where direct purchase happens")

    # 3 Is TI done for all the TOs received
    ti_done_all_tos_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is TI done for all the TOs received"
    )
    ti_done_all_tos_text_opening = fields.Text(string="Is TI done for all the TOs received")
    ti_done_all_tos_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is TI done for all the TOs received"
    )
    ti_done_all_tos_text_closing = fields.Text(string="Is TI done for all the TOs received")

    # 4 Is the TO & TI reconciliation done
    to_ti_reconciliation_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is the TO & TI reconciliation done"
    )
    to_ti_reconciliation_text_opening = fields.Text(string="Is the TO & TI reconciliation done")
    to_ti_reconciliation_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Is the TO & TI reconciliation done"
    )
    to_ti_reconciliation_text_closing = fields.Text(string="Is the TO & TI reconciliation done")

    # 5 All GRTs are prepared & sent to WH within same day
    grt_sent_same_day_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All GRTs are prepared & sent to WH within same day"
    )
    grt_sent_same_day_text_opening = fields.Text(string="All GRTs are prepared & sent to WH within same day")
    grt_sent_same_day_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="All GRTs are prepared & sent to WH within same day"
    )
    grt_sent_same_day_text_closing = fields.Text(string="All GRTs are prepared & sent to WH within same day")
    # 1 Cleanliness / Hygiene are as per norms
    cleanliness_hygiene_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Cleanliness / Hygiene are as per norms"
    )
    cleanliness_hygiene_text_opening = fields.Text(string="Cleanliness / Hygiene are as per norms")
    cleanliness_hygiene_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Cleanliness / Hygiene are as per norms"
    )
    cleanliness_hygiene_text_closing = fields.Text(string="Cleanliness / Hygiene are as per norms")

    # 2 Staff Grooming
    staff_grooming_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Staff Grooming"
    )
    staff_grooming_text_opening = fields.Text(string="Staff Grooming")
    staff_grooming_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Staff Grooming"
    )
    staff_grooming_text_closing = fields.Text(string="Staff Grooming")

    # 3 Scrap/waste are placed at designated areas
    scrap_waste_designated_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Scrap/waste are placed at designated areas"
    )
    scrap_waste_designated_text_opening = fields.Text(string="Scrap/waste are placed at designated areas")
    scrap_waste_designated_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Scrap/waste are placed at designated areas"
    )
    scrap_waste_designated_text_closing = fields.Text(string="Scrap/waste are placed at designated areas")

    # 4 SIS Project material / store material at designated areas
    sis_material_designated_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="SIS Project material / store material at designated areas"
    )
    sis_material_designated_text_opening = fields.Text(string="SIS Project material / store material at designated areas")
    sis_material_designated_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="SIS Project material / store material at designated areas"
    )
    sis_material_designated_text_closing = fields.Text(string="SIS Project material / store material at designated areas")

    # 5 Stock availability as per trade agreement
    stock_availability_trade_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Stock availability as per trade agreement"
    )
    stock_availability_trade_text_opening = fields.Text(string="Stock availability as per trade agreement")
    stock_availability_trade_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Stock availability as per trade agreement"
    )
    stock_availability_trade_text_closing = fields.Text(string="Stock availability as per trade agreement")

    # 6 Stock display as per trade agreement
    stock_display_trade_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Stock display as per trade agreement"
    )
    stock_display_trade_text_opening = fields.Text(string="Stock display as per trade agreement")
    stock_display_trade_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Stock display as per trade agreement"
    )
    stock_display_trade_text_closing = fields.Text(string="Stock display as per trade agreement")

    # 7 Electrical wires / Equipments are in safe condition
    electrical_safe_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Electrical wires / Equipments are in safe condition"
    )
    electrical_safe_text_opening = fields.Text(string="Electrical wires / Equipments are in safe condition")
    electrical_safe_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Electrical wires / Equipments are in safe condition"
    )
    electrical_safe_text_closing = fields.Text(string="Electrical wires / Equipments are in safe condition")

    # 8 Sales record maintaining
    sales_record_opening = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Sales record maintaining"
    )
    sales_record_text_opening = fields.Text(string="Sales record maintaining")
    sales_record_closing = fields.Selection(
        [("yes", "Yes"), ("no", "No")],
        string="Sales record maintaining"
    )
    sales_record_text_closing = fields.Text(string="Sales record maintaining")


