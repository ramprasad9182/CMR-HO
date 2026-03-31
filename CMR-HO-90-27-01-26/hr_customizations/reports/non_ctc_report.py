from odoo import models

class ReportNonCTC(models.AbstractModel):
    _name = 'report.hr_customizations.non_ctc_template'
    _description = 'Non CTC Report'

    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.payslip'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.payslip',
            'docs': docs,
            # 👇 Add your model function here to use it in QWeb
            'get_salary_components': self.env['hr.payslip'].get_salary_components,
        }
