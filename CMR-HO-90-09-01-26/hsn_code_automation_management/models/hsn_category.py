# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

CATEGORY_SELECTION = [
    ("1", "Live Animals, Bovine & Poultry"),
    ("2", "Meat & Edible Offal of Animals"),
    ("3", "Fish Meat & Fillets"),
    ("4", "Eggs, Honey & Milk Products"),
    ("5", "Non Edible Animal Products"),
    ("6", "Live Trees & Plants"),
    ("7", "Vegetables"),
    ("8", "Fruits & Dry Fruits"),
    ("9", "Tea, Coffee & Spices"),
    ("10", "Edible Grains"),
    ("11", "Milling Industry Products"),
    ("12", "Oil Seeds, Fruit & Part of Plants"),
    ("13", "Gums, Resins, Vegetable SAP & Extracts"),
    ("14", "Vegetable Material & Products"),
    ("15", "Fats, Oils & Waxes their Fractions"),
    ("16", "Preserved/Prepared Food Items"),
    ("17", "Sugar, Jaggery, Honey & bubble Gums"),
    ("18", "Chocolate & Cocoa Products"),
    ("19", "Pizza, Cake, Bread, Pasta & Waffles"),
    ("20", "Edible Plants-Fruits, Nuts & Juices"),
    ("21", "Tea & Coffee Extract & Essence"),
    ("22", "Water-Mineral & Aerated"),
    ("23", "Flours, Meals & Pellets"),
    ("24", "Tobacco, Stemmed & Stripped"),
    ("25", "Salts & Sands"),
    ("26", "Mineral Ores & Slags"),
    ("27", "Fossil Fuels-Coal & Petroleum"),
    ("28", "Gases & Non Metals"),
    ("29", "Hydrocarbons-Cyclic & Acyclic"),
    ("30", "Drugs & Pharmaceuticals"),
    ("31", "Fertilisers"),
    ("32", "Tanning & Colouring Products"),
    ("33", "Essential Oils, Beauty Products"),
    ("34", "Soaps, Waxes, Polish products"),
    ("35", "Casein, Albumin, Gelatin, Enzymes"),
    ("36", "Propellants, Explosives, Fuses, Fireworks"),
    ("37", "Photographic & Cinematographic Films"),
    ("38", "Insecticides, Artificial Carbon & Graphite"),
    ("39", "Polymers, Polyethylene, Cellulose"),
    ("40", "Rubber, Plates, Belt, Condesnsed Milk"),
    ("41", "Raw hides & Skins, Leather"),
    ("42", "Trunks, Suit-cases, Vanity cases"),
    ("43", "Raw Fur Skins, Articles of apparel"),
    ("44", "Fuel wood, Wood Charcoal"),
    ("45", "Natural Cork, Shuttlecock Cork"),
    ("46", "Plaiting Materials, Basketwork"),
    ("47", "Mechanical & Chemical woodpulp"),
    ("48", "Newsprint, Uncoated paper & paperboard"),
    ("49", "Printed Books, Brochures, Newspapers"),
    ("50", "Silk Worm Coccon, Yarn, Waste & Woven Fabrics"),
    ("51", "Wool materials & Waste, Animal Hairs"),
    ("52", "Cotton materials, Synthetics & Woven fabrics"),
    ("53", "Flex raw, Vegetable materials & Paper yarn"),
    ("54", "Synthetic felaments, Woven fabrics & Rayons"),
    ("55", "Synthetic felament tows & Polyster staple fiber"),
    ("56", "Towels, Napkins, ropes & Netting materials"),
    ("57", "Carpets & Floor coverings textile Handlooms"),
    ("58", "Labels, Bades, Woven pile & Chennile, Terry towelings"),
    ("59", "Rubberised textile fabrics, Convayer belts"),
    ("60", "Pile,Wrap Knit,Tarry & Croched fabrics"),
    ("61", "Men & Women Clothing"),
    ("62", "Men & Women Jackets, Coats & Garments"),
    ("63", "Blankets & Bedsheets"),
    ("64", "Shoes & Footwear Products"),
    ("65", "Hats & Accessories"),
    ("66", "Umbrellas & Accessories"),
    ("67", "Artificial flowers, Wigs & False Beards"),
    ("68", "Monumental & Building Stones"),
    ("69", "Bricks, Blocks & Ceramics"),
    ("70", "Glasses, Mirrors, Flasks"),
    ("71", "Pearls, Diamonds, Gold, Platinum"),
    ("72", "Iron, Alloys, Scrap & Granules"),
    ("73", "Iron tube, piles & Sheets"),
    ("74", "Copper Mattes, Rods, Bars, Wires, Plates"),
    ("75", "Nickel Mattes & Unwrought Nickel"),
    ("76", "Unwrought Aluminium- Rods, Sheets & Profiles"),
    ("78", "Unwrought Lead-Rods, Sheets & Profiles"),
    ("79", "Unwrought Zinc-Rods, Sheets & Profiles"),
    ("80", "Unwrought Tin-Rods, Sheets & Profiles"),
    ("81", "Magnesium, Cobalt, Tungsten Articles"),
    ("82", "Hand Tools & Cutlery"),
    ("83", "Locks, Metal Mountings & Fittings"),
    ("84", "Industrial Machinery"),
    ("85", "Electrical Parts & Electronics"),
    ("86", "Railway Locomotives & Parts"),
    ("87", "Tractors & Motor Vehicles"),
    ("88", "Balloons, Parachutes & Airlift Gear"),
    ("89", "Cruise Ships & Boats"),
    ("90", "Medical, Chemical & Astronomy"),
    ("91", "Watches & Clocks"),
    ("92", "Musical Instruments"),
    ("93", "Military Weapons & firearms"),
    ("94", "Furniture, Bedding & lighting"),
    ("95", "Children Toys, Table & Board Games & Sports Goods"),
    ("96", "Pencil Lighter Toiletries"),
    ("97", "Paintings Decoratives Sculptures"),
    ("98", "Machinery Lab Chemicals Drugs Medicines"),
    ("99", "Services"),
]


class HSNCategory(models.Model):
    _name = "hsn.category"
    _description = "HSN Category"
    _rec_name = "hsn_code_category"

    hsn_code_category = fields.Selection(
        selection=CATEGORY_SELECTION,
        string="HSN Code Category",
        tracking=True,
        copy=False,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        compute="_compute_category_id",
        store=True,
        default=lambda self: (
            self.env.company if self.env.company.country_id.code == "IN" else None
        ),
    )

    _sql_constraints = [
        (
            "unique_hsn_code_category",
            "unique(hsn_code_category)",
            "HSN Code Category Must be unique!",
        )
    ]

    def action_category_selection(self):
        country_id_c = self.company_id.country_id
        country_id = self.env.company.country_id
        if country_id_c == country_id and country_id.code == "IN":

            if len(self) == 1:

                action = self.env["ir.actions.act_window"]._for_xml_id(
                    "hsn_code_automation_management.hsn_code_master_action"
                )

                action["context"] = {
                    "default_category_id": self.id,
                    "search_default_category_id": self.id,
                    "default_company_id": self.company_id.id,
                    "search_default_company_id": self.company_id.id,
                }
                action["domain"] = [("category_id", "=", self.id)]
                return action
            else:
                raise UserError(_("Kindly choose just one category!"))
        else:
            raise UserError(_("This country does not have access to this feature!."))

    @api.depends("hsn_code_category")
    def _compute_category_id(self):
        for rec in self:
            country_id = rec.company_id.country_id
            category_id = rec.hsn_code_category
            if country_id.code == "IN" and category_id:
                self.env["hsn.code.master"]._create_hsn_code_with_tax(
                    category_id, rec.company_id
                )
