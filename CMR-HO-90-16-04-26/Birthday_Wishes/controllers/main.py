# hr_birthday/models/hr_birthday.py
from odoo import models, api
from datetime import date

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def get_today_birthdays(self):
        today = date.today()
        employees = self.search([('birthday', '!=', False)])
        print(employees)
        result = []
        for emp in employees:

            if emp.birthday.day == today.day and emp.birthday.month == today.month:
                result.append({
                    'name': emp.name,
                    'birthday': emp.birthday.strftime('%d-%m-%Y'),
                    'id':emp.barcode,
                })
        return result

    @api.model
    def get_today_anniversaries(self):
        today = date.today()
        employees = self.search([('date_of_joining', '!=', False)])
        result = []

        for emp in employees:
            doj = emp.date_of_joining

            if doj.day == today.day and doj.month == today.month:
                years = today.year - doj.year  # only number

                suffix = "th"
                if years % 10 == 1 and years % 100 != 11:
                    suffix = "st"
                elif years % 10 == 2 and years % 100 != 12:
                    suffix = "nd"
                elif years % 10 == 3 and years % 100 != 13:
                    suffix = "rd"

                years_text = f"{years}{suffix}"
                print(years_text)
                result.append({
                    'name': emp.name,
                    'date_of_joining': doj.strftime('%d-%m-%Y'),
                    'years_completed': years,
                    'years_suffix': years_text,
                    'id': emp.barcode,
                })
        return result



