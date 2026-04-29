from odoo import http
from odoo.http import request
import logging
import base64

_logger = logging.getLogger(__name__)

class InterviewFormController(http.Controller):

    @http.route('/form/<string:access_token>', type='http', auth='public', website=True)
    def public_interview_form(self, access_token, **kwargs):
        form = request.env['hr.interview.form'].sudo().search([('access_token', '=', access_token)], limit=1)
        if not form:
            return request.not_found()

        jobs = request.env['hr.job'].sudo().search([])
        companies = request.env['res.company'].sudo().search([])
        departments = request.env['hr.department'].sudo().search([])
        company_ids = request.httprequest.form.getlist('company_ids')
        countries = request.env['res.country'].sudo().search([('name', '=', 'India')], limit=1)
        states = request.env['res.country.state'].sudo().search([('country_id', '=', countries.id)])

        _logger.info(f"Selected Company IDs: {company_ids}")

        return request.render('recruitment_interview_form.interview_form_page', {
            'form': form,
            'jobs': jobs,
            'companies': companies,
            'company_ids': company_ids,
            'departments': departments,
            'countries': [countries],
            'states': states,
            'default_country_id': countries.id,
        })


    @http.route('/form/submit', type='http', auth='public', methods=['POST'], website=True, csrf=True)
    def submit_interview_form(self, **post):
        _logger.info("Received POST data: %s", post)
        try:

            resume_file = request.httprequest.files.get('resume_file')
            photo_file = request.httprequest.files.get('photo_file')

            if resume_file:
                _logger.info("Resume uploaded: %s", resume_file.filename)
            if photo_file:
                _logger.info("Photo uploaded: %s", photo_file.filename)




            form_id = int(post.get('form_id'))
            name = post.get('name')
            email = post.get('email')
            job_id = int(post.get('job_id')) if post.get('job_id') else False
            department_id = int(post.get('department_id')) if post.get('department_id') else False
            partner_mobile = post.get('partner_mobile')
            partner_phone = post.get('partner_phone')
            salary_type = post.get('salary_type')
            experience_type = post.get('experience_type')

            # Permanent Address
            permanent_street = post.get('permanent_street')
            permanent_street2 = post.get('permanent_street2')
            permanent_city = post.get('permanent_city')
            permanent_state_id = post.get('permanent_state_id')
            permanent_zip = post.get('permanent_zip')
            permanent_country_id = post.get('permanent_country_id')

            # Personal Info
            dob = post.get('dob')
            age = post.get('age')
            marital_status = post.get('marital_status')
            gender = post.get('gender')

            # Work Experience
            total_experience_years = post.get('total_experience_years')
            retail_experience_years = post.get('retail_experience_years')

            # Company Selection
            raw_company_ids = request.httprequest.form.getlist('company_ids')
            multi_company_ids = [(6, 0, list(map(int, raw_company_ids)))] if raw_company_ids else []
            auto_company_id = int(raw_company_ids[0]) if len(raw_company_ids) == 1 else False

            # Professional Experience
            professional_details = []
            for i in range(int(post.get('professional_count', 0))):
                company_name = post.get(f'company_name_{i}')
                designation = post.get(f'designation_{i}')
                from_date = post.get(f'from_date_{i}')
                to_date = post.get(f'to_date_{i}')
                years_experience = post.get(f'years_experience_{i}')
                if company_name and designation:
                    professional_details.append((0, 0, {
                        'company_name': company_name,
                        'designation': designation,
                        'from_date': from_date,
                        'to_date': to_date,
                        'years_experience': years_experience,
                        'sequence': i + 1,
                    }))

            # References
            reference_details = []
            for i in range(int(post.get('reference_count', 0))):
                ref_name = post.get(f'ref_name_{i}')
                ref_phone = post.get(f'ref_phone_{i}')
                if ref_name:
                    reference_details.append((0, 0, {
                        'name': ref_name,
                        'phone': ref_phone,
                    }))

            # Education
            education_details = []
            for i in range(int(post.get('education_count', 0))):
                degree = post.get(f'degree_{i}')
                date_from = post.get(f'date_from_{i}')
                date_to = post.get(f'date_to_{i}')
                year_of_passing = post.get(f'year_of_passing_{i}')
                if degree:
                    education_details.append((0, 0, {
                        'degree': degree,
                        'date_from': date_from,
                        'date_to': date_to,
                        'year_of_passing': year_of_passing,
                        'sequence': i + 1,
                    }))

            # Check form exists
            form = request.env['hr.interview.form'].sudo().browse(form_id)
            if not form.exists():
                _logger.warning("Form with id %s does not exist", form_id)
                return request.not_found()

            # Final create values
            vals = {
                'interview_form_id': form_id,
                'name': job_id and request.env['hr.job'].sudo().browse(job_id).name or '',
                'partner_name': name,
                'email_from': email,
                'job_id': job_id,
                'company_id': auto_company_id,  # ✅ Auto-set if one selected
                'department_id': department_id,
                'partner_mobile': partner_mobile,
                'partner_phone': partner_phone,
                'experience_type': experience_type,
                'total_experience': total_experience_years,
                'retail_experience_years': retail_experience_years,
                'salary_type': salary_type,
                'current_salary': post.get('current_salary'),
                'salary_expected': post.get('expected_salary'),
                'current_ctc': post.get('current_ctc') if salary_type == 'ctc' else False,
                'expected_ctc': post.get('expected_ctc') if salary_type == 'ctc' else False,
                'multi_company_ids': multi_company_ids,
                'applicant_professional_ids': professional_details,
                'applicant_reference_ids': reference_details,
                'applicant_education_ids': education_details,
                'permanent_street': permanent_street,
                'permanent_street2': permanent_street2,
                'permanent_city': permanent_city,
                'permanent_state_id': permanent_state_id,
                'permanent_zip': permanent_zip,
                'permanent_country_id': permanent_country_id,
                'dob': dob,
                'age': age,
                'gender': gender,
                'marital_status': marital_status,
            }

            _logger.info("Creating hr.applicant with values: %s", vals)
            applicant = request.env['hr.applicant'].sudo().create(vals)
            _logger.info("✅ Applicant created successfully with ID: %s", applicant.id)

            # Attach uploaded resume
            if resume_file:
                resume_data = base64.b64encode(resume_file.read())
                request.env['ir.attachment'].sudo().create({
                    'name': resume_file.filename,
                    'datas': resume_data,
                    'res_model': 'hr.applicant',
                    'res_id': applicant.id,
                    'type': 'binary',
                    'mimetype': resume_file.mimetype,
                })

            # Attach uploaded photo
            if photo_file:
                photo_data = base64.b64encode(photo_file.read())
                request.env['ir.attachment'].sudo().create({
                    'name': photo_file.filename,
                    'datas': photo_data,
                    'res_model': 'hr.applicant',
                    'res_id': applicant.id,
                    'type': 'binary',
                    'mimetype': photo_file.mimetype,
                })

            _logger.info("Applicant created successfully.")

            return request.redirect('/form/thank-you')

        except Exception as e:
            _logger.exception("Error submitting interview form: %s", e)
            return request.render('recruitment_interview_form.error_page', {
                'error_msg': "Something went wrong while submitting the form. Please try again."
            })

    @http.route('/form/thank-you', type='http', auth='public', website=True)
    def thank_you_page(self, **kwargs):
        return request.render('recruitment_interview_form.interview_form_thank_you')

