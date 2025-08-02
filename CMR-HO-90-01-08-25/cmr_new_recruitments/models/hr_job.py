from odoo import models, fields, api

class HrJob(models.Model):
    _inherit = 'hr.job'

    hired_count = fields.Integer(string="Hired", compute="_compute_hired_count")
    vacant_count = fields.Integer(string="Vacant", compute="_compute_vacant_count")
    application_count = fields.Integer(string="Applications", compute="_compute_application_count")
    # vacancy = fields.Integer(string="Vacant", compute = "_compute_vacant")



    @api.depends('no_of_recruitment', 'hired_count')
    def _compute_vacant_count(self):
        for record in self:
            record.vacant_count = record.no_of_recruitment - record.hired_count


    def _compute_hired_count(self):
        Applicant = self.env['hr.applicant']
        for record in self:
            record.hired_count = Applicant.search_count([
                ('job_id', '=', record.id),
                ('stage_id.name', '=', 'Contract Signed'),
            ])

    def _compute_application_count(self):
        Applicant = self.env['hr.applicant']
        for record in self:
            record.application_count = Applicant.search_count([
                ('job_id', '=', record.id)
            ])

    def _compute_new_application_count(self):
        self.env.cr.execute(
            """
            WITH job_stage AS (
                SELECT DISTINCT ON (j.id)
                    j.id AS job_id,
                    s.id AS stage_id,
                    s.sequence AS sequence
                FROM hr_job j
                LEFT JOIN hr_job_hr_recruitment_stage_rel rel
                    ON rel.hr_job_id = j.id
                JOIN hr_recruitment_stage s
                    ON s.id = rel.hr_recruitment_stage_id
                    OR s.id NOT IN (
                        SELECT hr_recruitment_stage_id
                        FROM hr_job_hr_recruitment_stage_rel
                        WHERE hr_recruitment_stage_id IS NOT NULL
                    )
                WHERE j.id in %s
                ORDER BY 1, 3 ASC
            )
            SELECT s.job_id, COUNT(a.id) AS new_applicant
            FROM hr_applicant a
            JOIN job_stage s
                ON s.job_id = a.job_id
                AND a.stage_id = s.stage_id
                AND a.active IS TRUE

            GROUP BY s.job_id
            """,
            [tuple(self.ids)]  # 👈 Only one argument now
        )

        new_applicant_count = dict(self.env.cr.fetchall())
        for job in self:
            job.new_application_count = new_applicant_count.get(job.id, 0)