# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
import requests
from bs4 import BeautifulSoup

COMMON_URL = "https://cleartax.in/s/chapter-"

CATEGORY_SELECTION = {
    "1": "live-animal-products",
    "2": "meat-edible-meat-offal",
    "3": "fish-crustaceans-molluscs-aquatic-invertebrates",
    "4": "dairy-eggs-natural-honey-edible-animal-product",
    "5": "animal-origin-products",
    "6": "vegetable-products",
    "7": "edible-vegetable-roots-tuber",
    "8": "edible-fruit-nut-citrus-fruit-peel-melons",
    "9": "coffee-tea-mate-spices",
    "10": "cereals",
    "11": "milling-products-malt-starches-inulin-wheat-gluten",
    "12": "oil-seeds-oleaginous-fruits-grainsseeds-fruit-industrial-medical-plants-straw-fodder",
    "13": "lac-gums-resins-vegetable-saps-extracts",
    "14": "vegetable-plaiting-product-materials",
    "15": "edible-animal-vegetable-fats-oils-cleavage-products-prepared-waxes",
    "16": "fish-meat-crustaceans-molluscs-aquatic-invertebrates-preparations",
    "17": "sugar-confectionery",
    "18": "cocoa-preparations",
    "19": "cereals-flour-starch-milk-pastrycooks-products-preparations",
    "20": "vegetables-fruit-nuts-preparations",
    "21": "miscellaneous-edible-preparations",
    "22": "beverages-spirits-vinegar",
    "23": "residues-waste-food-industries-prepared-animal-fodder",
    "24": "tobacco-manufactured-substitutes",
    "25": "mineral-products-salt-sulphur-earths-stone-plastering-materials-lime-cement",
    "26": "ores-slag-ash",
    "27": "mineral-fuels-oils-distillation-bituminous-substances-mineral-waxes",
    "28": "organic-inorganic-chemicals-compounds-precious-metals",
    "29": "elements-isotopes",
    "30": "pharmaceutical-products",
    "31": "fertilizers",
    "32": "tanning-dyeing-extracts-dyes-pigments-paints-varnishes-putty-mastics-inks",
    "33": "essential-oils-resinoids-perfumery-cosmetic-toilet-preparations",
    "34": "soap-washing-lubricating-artificial-waxes-polishing-scouring-candles-modelling-pastes-dental-waxes-preparations",
    "35": "albuminoidal-substances-starches-glues-enzymes",
    "36": "explosives-pyrotechnic-matches-pyrophoric-alloys-combustible-preparations",
    "37": "photographic-cinematographic-goods",
    "38": "chemical-products",
    "39": "plastics",
    "40": "rubber",
    "41": "raw-hides-skins-furskins-leather",
    "42": "leather-travel-goods-handbags-containers-animal-silkworm-gut",
    "43": "furskins-artificial-fur",
    "44": "wood-charcoal",
    "45": "cork",
    "46": "straw-esparto-basketware-wickerwork",
    "47": "pulp-wood-fibrous-cellulosic-material",
    "48": "waste-scrap-paper-paperboard",
    "49": "printed-books-newspapers-pictures-manuscripts-typescripts-plans",
    "50": "textiles",
    "51": "wool-animal-hair-horsehair-yarn-woven-fabric",
    "52": "cotton",
    "53": "vegetable-textile-fibres-paper-yarn-woven-fabrics-paper-yarn",
    "54": "man-made-filaments-strip",
    "55": "man-made-staple-fibres",
    "56": "wadding-felt-nonwovens-yarns-twine-cordage-ropes-cables",
    "57": "carpets-floor-coverings",
    "58": "woven-fabrics-tufted-textile-lace-tapestries-trimmings-embroidery",
    "59": "impregnated-coated-covered-laminated-textile-fabrics",
    "60": "knitted-crocheted-fabrics",
    "61": "apparel-clothing-accessories-knitted-crocheted",
    "62": "apparel-clothing-accessories-not-knitted-crocheted",
    "63": "sets-worn-clothing-textile-rags",
    "64": "footwear-gaiters-parts",
    "65": "headgear-parts",
    "66": "sun-umbrellas-walking-sticks-seat-whips-riding-crops-parts",
    "67": "prepared-feathers-artificial-flowers-human-hair",
    "68": "stone-plaster-cement-asbestos-mica",
    "69": "ceramic-products",
    "70": "glass-glassware",
    "71": "natural-cultured-pearls-precious-semi-precious-stones-metals-clad-imitation-jewelry-coin",
    "72": "iron-steel",
    "73": "iron-steel-articles",
    "74": "copper",
    "75": "nickel",
    "76": "aluminium",
    "77": "none",
    "78": "lead",
    "79": "zinc",
    "80": "tin",
    "81": "cermets",
    "82": "tools-implements-cutlery-spoons-forks",
    "83": "base-metal",
    "84": "nuclear-reactors-boilers-machinery-mechanical-appliances",
    "85": "electrical-machinery-equipment-sound-recorders-reproducers-television-image-parts-accessories",
    "86": "railway-tramway-locomotives-rolling-stock-track-fixtures-fittings-electro-mechanical-traffic-signalling-equipment-parts",
    "87": "vehicles-railway-tramway-rolling-stock-parts-accessories",
    "88": "aircraft-spacecraft-parts",
    "89": "ships-boats-floating-structures",
    "90": "optical-photographic-cinematographic-measuring-checking-precision-medical-surgical-instruments-apparatus-parts-accessories",
    "91": "clocks-watches-parts",
    "92": "musical-instruments-parts-accessories",
    "93": "arms-ammunitions-parts-accessories",
    "94": "furniture-mattresses-cushions-lamps-lightings-illuminated-signs-name-plates",
    "95": "toys-games-sports-parts-accessories",
    "96": "miscellaneous-manufactured-articles",
    "97": "art-collectors-pieces-antiques-works",
    "98": "laboratory-chemicals-baggage-imports",
    "99": "services-sac-code-gst-rate",
}


class HsnCodeMaster(models.Model):
    _name = "hsn.code.master"
    _description = "HSN/SAC Code Master"
    _rec_name = "hsn_code"

    _sql_constraints = [
        ("unique_hsn_code", "unique(hsn_code)", "The HSN/SAC Code must be unique"),
    ]
    hsn_code = fields.Char(string="HSN/SAC Code", required=True, copy=False)

    hsn_description = fields.Char(string="HSN/SAC Description")
    sale_tax_id = fields.Many2many("account.tax",'sale_tax', string="GST Sales", domain=[('type_tax_use','=','sale')])
    purchase_tax_id = fields.Many2many("account.tax", 'purchase_tax', string="GST Purchase", domain=[('type_tax_use','=','purchase')])
    igst_sale_tax_id = fields.Many2many("account.tax",'igst_sale', string="GST Sales(IGST)")
    igst_purchase_tax_id = fields.Many2many("account.tax",'igst_purchase', string="GST Purchase(IGST)")

    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    category_id = fields.Many2one("hsn.category", string="HSN Category", readonly=True)

    @api.model
    def _create_hsn_code_with_tax(self, hsn_category, company_id):
        hsn_category_selection = CATEGORY_SELECTION.get(hsn_category)
        if hsn_category == "99":
            url = f"{COMMON_URL}{hsn_category}-{hsn_category_selection}"
        else:
            url = f"{COMMON_URL}{hsn_category}-{hsn_category_selection}-gst-rate-hsn-code"

        page = requests.get(url)
        if page.status_code == 200:
            soup = BeautifulSoup(page.content, "html.parser")
            table = soup.find("div", id="hsn-sac-table-container")
            if table:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    rec = [cell.text.strip() for cell in cells]
                    if len(rec) >= 3:
                        sale_tax_ids = []
                        igst_sale_tax_ids = []
                        purchase_tax_ids = []
                        igst_purchase_tax_ids = []

                        tax_rate = rec[2]
                        if tax_rate == "":
                            # Set all tax fields to an empty list for Many2many fields
                            sale_tax_ids = igst_sale_tax_ids = purchase_tax_ids = igst_purchase_tax_ids = []
                        elif tax_rate in ["Nil", "0%"]:
                            if tax_rate == "Nil":
                                tax_rate = "0%"
                            tax_rate = float(tax_rate.replace("%", ""))

                            nil_tax = self.env["account.tax"].search(
                                [
                                    ("company_id", "=", company_id.id),
                                    ("tax_group_id.name", "=", "Nil Rated"),
                                    ("amount_type", "=", "percent"),
                                    ("amount", "=", tax_rate),
                                    ("l10n_in_reverse_charge", "=", False),
                                ]
                            )

                            for record in nil_tax:
                                if record.type_tax_use == "sale":
                                    igst_sale_tax_ids.append(record.id)
                                    sale_tax_ids.append(record.id)
                                elif record.type_tax_use == "purchase":
                                    igst_purchase_tax_ids.append(record.id)
                                    purchase_tax_ids.append(record.id)
                        else:
                            tax_rate = float(tax_rate.replace("%", ""))

                            igst_tax = self.env["account.tax"].search(
                                [
                                    ("company_id", "=", company_id.id),
                                    ("amount_type", "=", "percent"),
                                    ("amount", "=", tax_rate),
                                    ("l10n_in_reverse_charge", "=", False),
                                ]
                            )

                            gst_tax_sale = self.env["account.tax"].search(
                                [
                                    ("company_id", "=", company_id.id),
                                    ("type_tax_use", "=", "sale"),
                                    ("amount_type", "=", "group"),
                                ]
                            )

                            gst_tax_purchase = self.env["account.tax"].search(
                                [
                                    ("company_id", "=", company_id.id),
                                    ("type_tax_use", "=", "purchase"),
                                    ("amount_type", "=", "group"),
                                ]
                            )

                            # Append IGST tax for sale and purchase
                            igst_sale_tax_ids.extend(
                                [tax.id for tax in igst_tax if tax.type_tax_use == "sale"]
                            )
                            igst_purchase_tax_ids.extend(
                                [tax.id for tax in igst_tax if tax.type_tax_use == "purchase"]
                            )

                            for record in gst_tax_sale:
                                for child_rec in record.children_tax_ids:
                                    if (
                                            child_rec.amount == (float(tax_rate) / 2)
                                            and child_rec.l10n_in_reverse_charge == False
                                    ):
                                        sale_tax_ids.append(record.id)
                                        break
                            for record in gst_tax_purchase:
                                for child_rec in record.children_tax_ids:
                                    if (
                                            child_rec.amount == (float(tax_rate) / 2)
                                            and child_rec.l10n_in_reverse_charge == False
                                    ):
                                        purchase_tax_ids.append(record.id)
                                        break

                        # Get the category ID
                        get_category_id = self.env["hsn.category"].search(
                            [("hsn_code_category", "=", hsn_category)], limit=1
                        )

                        value = {
                            "hsn_code": rec[0],
                            "hsn_description": rec[1],
                            "sale_tax_id": [(6, 0, sale_tax_ids)],  # Many2many format
                            "igst_sale_tax_id": [(6, 0, igst_sale_tax_ids)],  # Many2many format
                            "purchase_tax_id": [(6, 0, purchase_tax_ids)],  # Many2many format
                            "igst_purchase_tax_id": [(6, 0, igst_purchase_tax_ids)],  # Many2many format
                            "category_id": get_category_id.id,
                            "company_id": company_id.id,
                        }

                        # Check if the HSN code exists and either update or create it
                        check_data = self.env["hsn.code.master"].search(
                            [("hsn_code", "=", value["hsn_code"])]
                        )
                        if check_data:
                            check_data.write(value)
                        else:
                            self.create(value)

