
(function () {
    console.log("JS Loaded");

    // Initialize Select2 for preferred companies
    $(document).ready(function () {
        $('.js-company-multiselect').select2({
            width: '100%',
            placeholder: 'Select Preferred Companies'
        });
    });


    const form = document.getElementById("interview_form");
    const experienceType = document.getElementById("experience_type");

    const toggleRequired = (ids, enable) => {
        ids.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                if (enable) {
                    el.setAttribute("required", "required");
                } else {
                    el.removeAttribute("required");
                }
            }
        });
    };

   function toggleExperienceFields() {
        const isFresher = !experienceType.value || experienceType.value === "fresher";

        const experienceFields = document.getElementById("experience_fields");
        const professionalFields = document.getElementById("professional_section");
        const salaryFields = document.getElementById("salary_fields");

        // Show or hide fields
        experienceFields.style.display = isFresher ? "none" : "block";
        professionalFields.style.display = isFresher ? "none" : "block";
        salaryFields.style.display = isFresher ? "none" : "block";

        // Toggle required attribute
        toggleRequired(
            ["total_experience_years", "retail_experience_years", "current_salary", "expected_salary"],
            !isFresher
        );

        const proInputs = professionalFields.querySelectorAll("input");
        proInputs.forEach(input => {
            if (!isFresher) {
                input.setAttribute("required", "required");
            } else {
                input.removeAttribute("required");
            }
        });
   }


    function validateDateRange(fromName, toName, count, label) {
    let isValid = true;

    for (let i = 0; i < count; i++) {
        const from = document.querySelector(`input[name="${fromName}_${i}"]`);
        const to = document.querySelector(`input[name="${toName}_${i}"]`);

        // Always clear old error
        if (to) to.setCustomValidity('');

        if (from && to && from.value && to.value) {
            const fromDate = new Date(from.value);
            const toDate = new Date(to.value);

            if (toDate < fromDate) {
                to.setCustomValidity(`${label} To Date cannot be earlier than From Date`);
                isValid = false;
            }
        }
    }

    return isValid;
}



    function validateProfessionalDates() {
        const count = parseInt(document.getElementById('professional_count')?.value || '0');
        return validateDateRange('from_date', 'to_date', count, "Work");
    }

    function validateEducationDates() {
        const count = parseInt(document.getElementById('education_count')?.value || '0');
        return validateDateRange('date_from', 'date_to', count, "Education");
    }


    window.addEducationEntry = function () {
        const section = document.getElementById("education-details-section");
        const index = parseInt(document.getElementById("education_count").value);

        const wrapper = document.createElement("div");
        wrapper.className = "row education-entry mb-3";
        wrapper.innerHTML = `
            <div class="col-md-4">
                <label>Education Level</label>
                <select name="degree_${index}" class="form-select degree-select" required>
                    <option value="">Select Level</option>
                    <option value="ssc">SSC</option>
                    <option value="inter">Inter</option>
                    <option value="graduate">Graduate</option>
                    <option value="bachelor">Bachelor Degree</option>
                    <option value="masters">Masters Degree</option>
                    <option value="doctoral">Doctoral Degree</option>
                </select>
            </div>
            <div class="col-md-4">
                <label>From Date:</label>
                <input type="date" name="date_from_${index}" class="form-control"/>
            </div>
            <div class="col-md-4">
                <label>To Date:</label>
                <input type="date" name="date_to_${index}" class="form-control"/>
            </div>
            <div class="col-md-4 mt-2">
                <label>Year of Passing</label>
                <input type="text" name="year_of_passing_${index}" class="form-control"/>
            </div>
            <div class="col-md-2 mt-4">
                <button type="button" class="btn btn-outline-danger btn-sm remove-entry" title="Delete">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;
        section.appendChild(wrapper);
        document.getElementById("education_count").value = index + 1;

//        setupRealTimeDateValidation();
        updateUsedDegrees(); // ✅ Important: Refresh disabled options
    };

    function updateUsedDegrees() {
        const selectedValues = [];
        const allSelects = document.querySelectorAll('select[name^="degree_"]');

        // Step 1: Collect all selected values
        allSelects.forEach(select => {
            if (select.value) selectedValues.push(select.value);
        });

        // Step 2: For each dropdown, disable values selected elsewhere
        allSelects.forEach(currentSelect => {
            const currentValue = currentSelect.value;
            const options = currentSelect.querySelectorAll('option');

            options.forEach(option => {
                if (option.value === "") {
                    option.disabled = false;
                    return;
                }
                // Disable if selected elsewhere and not the current value
                if (selectedValues.includes(option.value) && option.value !== currentValue) {
                    option.disabled = true;
                } else {
                    option.disabled = false;
                }
            });
        });
}


    window.addProfessionalEntry = function () {
        const section = document.getElementById('professional_fields');
        const index = parseInt(document.getElementById('professional_count').value);

        const wrapper = document.createElement('div');
        wrapper.className = 'row professional-entry mb-3';
        wrapper.innerHTML = `
            <div class="col-md-4">
                <label>Company Name</label>
                <input type="text" name="company_name_${index}" class="form-control" required/>
            </div>
            <div class="col-md-4">
                <label>Designation</label>
                <input type="text" name="designation_${index}" class="form-control" required/>
            </div>
            <div class="col-md-4">
                <label>Years of Experience</label>
                <input type="number" name="years_experience_${index}" class="form-control" step="0.1" min="0"/>
            </div>
            <div class="col-md-6 mt-2">
                <label>From Date:</label>
                <input type="date" name="from_date_${index}" class="form-control"/>
            </div>
            <div class="col-md-6 mt-2">
                <label>To Date:</label>
                <input type="date" name="to_date_${index}" class="form-control"/>
            </div>
            <div class="col-md-2 mt-4">
                <button type="button" class="btn btn-outline-danger btn-sm remove-entry" title="Delete">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;
        section.appendChild(wrapper);
        document.getElementById('professional_count').value = index + 1;
//        setupRealTimeDateValidation();
    };

    window.addReferenceEntry = function () {
        const section = document.getElementById("reference-details-section");
        const index = parseInt(document.getElementById("reference_count").value);

        const wrapper = document.createElement("div");
        wrapper.className = "row reference-entry mb-3";
        wrapper.innerHTML = `
            <div class="col-md-6">
                <label>Name</label>
                <input type="text" name="ref_name_${index}" class="form-control" required/>
            </div>
            <div class="col-md-6">
                <label>Phone Number</label>
                <input type="text" name="ref_phone_${index}" class="form-control" pattern="\\d{10}" required/>
            </div>
            <div class="col-md-2 mt-4">
                <button type="button" class="btn btn-outline-danger btn-sm remove-entry" title="Delete">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;
        section.appendChild(wrapper);
        document.getElementById("reference_count").value = index + 1;
    };

    document.addEventListener("click", function (e) {
        const removeBtn = e.target.closest(".remove-entry");
        if (removeBtn) {
            const entry = removeBtn.closest(".education-entry, .professional-entry, .reference-entry");
            if (entry) entry.remove();
        }
    });

    if (form) {
    form.addEventListener("submit", function (e) {
        const validPro = validateProfessionalDates();
        const validEdu = validateEducationDates();

        if (!validPro || !validEdu) {
            e.preventDefault();  // ❌ Prevent submission if any date range is invalid

            // ✅ Show only one validation message at a time
            const invalidFields = form.querySelectorAll("input:invalid, select:invalid");
            if (invalidFields.length) {
                invalidFields[0].reportValidity();
            }
        }
    });
}
    document.addEventListener("change", function (e) {
    const name = e.target.name;

    // For education degree dropdown
    if (name?.startsWith("degree_")) {
        updateUsedDegrees();
    }

    // Real-time professional date validation
    if (name?.startsWith("from_date_") || name?.startsWith("to_date_")) {
        validateProfessionalDates();
    }

    // Real-time education date validation
    if (name?.startsWith("date_from_") || name?.startsWith("date_to_")) {
        validateEducationDates();
    }
});


    document.getElementById("add_professional_btn")?.addEventListener("click", window.addProfessionalEntry);
    document.getElementById("add_reference_btn")?.addEventListener("click", window.addReferenceEntry);
    document.getElementById("add_education_btn")?.addEventListener("click", window.addEducationEntry);


    function calculateAgeFromDOB() {
        const dobField = document.getElementById("dob");
        const ageField = document.getElementById("age");

        if (dobField && ageField && dobField.value) {
            const dob = new Date(dobField.value);
            const today = new Date();
            let age = today.getFullYear() - dob.getFullYear();
            const m = today.getMonth() - dob.getMonth();

            if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
                age--;
            }

            ageField.value = age > 0 ? age : '';
        } else if (ageField) {
            ageField.value = '';
        }
    }

    const dobInput = document.getElementById("dob");
    if (dobInput) {
        dobInput.addEventListener("change", calculateAgeFromDOB);
        calculateAgeFromDOB(); // run once on load
    }

    if (experienceType) {
        experienceType.addEventListener("change", toggleExperienceFields);
        toggleExperienceFields();
    }

//    setupRealTimeDateValidation();
// === Photo Upload with Validation & Remove ===
const photoInput = document.getElementById('photo_file');
const photoPreview = document.getElementById('photo_preview');
const photoContainer = document.getElementById('photo_preview_container');
const photoRemoveBtn = document.getElementById('remove_photo_btn');

if (photoInput && photoPreview && photoContainer && photoRemoveBtn) {
  photoInput.addEventListener('change', function (e) {
    const file = e.target.files[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        alert('Please upload a valid image file (PNG, JPG, JPEG)');
        photoInput.value = "";
        photoPreview.src = "";
        photoContainer.style.display = 'none';
        photoRemoveBtn.classList.add('d-none');
        photoInput.setAttribute('required', 'required');
        return;
      }

      const reader = new FileReader();
      reader.onload = function (event) {
        photoPreview.src = event.target.result;
        photoPreview.classList.remove('d-none');
        photoContainer.style.display = 'flex';
        photoRemoveBtn.classList.remove('d-none');
        photoInput.removeAttribute('required');
      };
      reader.readAsDataURL(file);
    }
  });

  photoRemoveBtn.addEventListener('click', function () {
    photoInput.value = "";
    photoPreview.src = "";
    photoPreview.classList.add('d-none');
    photoContainer.style.display = 'none';
    photoRemoveBtn.classList.add('d-none');
    photoInput.setAttribute('required', 'required');
  });
}

// === Resume Upload with Validation & Remove ===
const resumeInput = document.getElementById('resume_file');
const resumeLink = document.getElementById('resume_preview_link');
const resumeContainer = document.getElementById('resume_preview_container');
const resumeRemoveBtn = document.getElementById('remove_resume_btn');

if (resumeInput && resumeLink && resumeContainer && resumeRemoveBtn) {
  resumeInput.addEventListener('change', function (e) {
    const file = e.target.files[0];
    const allowedTypes = [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];

    if (file) {
      if (!allowedTypes.includes(file.type)) {
        alert('Please upload a valid resume file (PDF, DOC, DOCX)');
        resumeInput.value = "";
        resumeLink.href = "#";
        resumeLink.textContent = "";
        resumeContainer.style.display = 'none';
        resumeRemoveBtn.classList.add('d-none');
        resumeInput.setAttribute('required', 'required');
        return;
      }

      const url = URL.createObjectURL(file);
      resumeLink.href = url;
      resumeLink.textContent = "📄 View Uploaded Resume";
      resumeContainer.style.display = 'flex';
      resumeRemoveBtn.classList.remove('d-none');
      resumeInput.removeAttribute('required');
    }
  });

  resumeRemoveBtn.addEventListener('click', function () {
    resumeInput.value = "";
    resumeLink.href = "#";
    resumeLink.textContent = "";
    resumeContainer.style.display = 'none';
    resumeRemoveBtn.classList.add('d-none');
    resumeInput.setAttribute('required', 'required');
  });
}

})();
