"""Static demo content for DEMO-001 — Phase II Oncology Pilot Study."""

from __future__ import annotations

PROTOCOL_NUMBER = "DEMO-001"
STUDY_NAME = "Phase II Oncology Pilot Study"

STUDY_META = {
    "indication": "Non-small cell lung cancer (NSCLC), PD-L1 ≥ 1%",
    "therapeutic_area": "Oncology",
    "phase": "PHASE_2",
    "sponsor": "Demo Pharma Inc",
    "short_name": "DEMO-001 NSCLC",
    "description": (
        "Randomized Phase II study evaluating ABC-123 plus standard of care "
        "versus standard of care alone in previously treated NSCLC."
    ),
}

ALL_DOMAINS = [
    "STUDY_OVERVIEW",
    "STUDY_DESIGN",
    "POPULATION",
    "ENDPOINTS",
    "DRUG_TREATMENT",
    "SAFETY",
    "REGULATORY",
    "STATISTICAL",
    "SITES",
]

INTAKE_CONVERSATION: list[dict] = [
    {
        "role": "assistant",
        "domain": "STUDY_OVERVIEW",
        "content": (
            "Hello! I'm your TrialGenesis intake specialist. Let's begin with the "
            "study overview for the Phase II Oncology Pilot Study. Please share the "
            "title, therapeutic area, indication, phase, sponsor, and compound code."
        ),
    },
    {
        "role": "user",
        "content": (
            "Phase II randomized study of ABC-123 in previously treated NSCLC. "
            "Sponsor: Demo Pharma Inc. Compound ABC-123. Oncology / NSCLC, Phase 2."
        ),
    },
    {
        "role": "assistant",
        "domain": "STUDY_DESIGN",
        "content": (
            "Thank you. Describe the study design: parallel/crossover, randomization, "
            "blinding, comparator, treatment duration, and study periods."
        ),
    },
    {
        "role": "user",
        "content": (
            "Parallel-group, 1:1 randomization, open-label. Comparator is investigator's "
            "choice SOC chemotherapy. Treatment until progression or unacceptable toxicity. "
            "Screening, treatment, and follow-up periods."
        ),
    },
    {
        "role": "assistant",
        "domain": "POPULATION",
        "content": (
            "Describe the target population: inclusion and exclusion criteria, age range, "
            "estimated sample size, and key demographics."
        ),
    },
    {
        "role": "user",
        "content": (
            "Adults ≥18 with histologically confirmed NSCLC, PD-L1 ≥ 1%, progressed on "
            "one prior line. ECOG 0-1. N≈120. Exclude active autoimmune disease and "
            "untreated brain metastases."
        ),
    },
    {
        "role": "assistant",
        "domain": "ENDPOINTS",
        "content": (
            "What are the primary and key secondary endpoints, including timepoints "
            "and instruments?"
        ),
    },
    {
        "role": "user",
        "content": (
            "Primary: Progression-free survival (PFS) per RECIST 1.1 at 24 weeks. "
            "Secondary: ORR, OS, duration of response, safety/tolerability."
        ),
    },
    {
        "role": "assistant",
        "domain": "DRUG_TREATMENT",
        "content": (
            "Describe the investigational product: INN name, doses, route, formulation, "
            "and treatment regimen."
        ),
    },
    {
        "role": "user",
        "content": (
            "ABC-123 10 mg/kg IV Q3W plus SOC. Control arm SOC chemotherapy per "
            "investigator choice (docetaxel or gemcitabine)."
        ),
    },
    {
        "role": "assistant",
        "domain": "SAFETY",
        "content": (
            "What are the key safety concerns, monitoring approach, and stopping rules?"
        ),
    },
    {
        "role": "user",
        "content": (
            "Immune-related AEs, infusion reactions. Safety reviewed every cycle. "
            "DSMB at 50% enrollment. Hold for Grade ≥3 irAE until resolution to ≤1."
        ),
    },
    {
        "role": "assistant",
        "domain": "REGULATORY",
        "content": (
            "Which regulatory regions apply and what is the IND/CTA status?"
        ),
    },
    {
        "role": "user",
        "content": (
            "US and EU planned. US IND active. EMA CTA submitted. ICH E6(R2) GCP."
        ),
    },
    {
        "role": "assistant",
        "domain": "STATISTICAL",
        "content": (
            "Describe the statistical framework, primary analysis method, and alpha level."
        ),
    },
    {
        "role": "user",
        "content": (
            "Frequentist framework. Primary PFS analyzed with stratified log-rank; "
            "Cox model for HR. Two-sided alpha 0.05. 80% power to detect HR 0.65."
        ),
    },
    {
        "role": "assistant",
        "domain": "SITES",
        "content": (
            "How many sites, which countries, and expected enrollment rate?"
        ),
    },
    {
        "role": "user",
        "content": (
            "Approximately 25 sites across US, Germany, and France. "
            "Target enrollment 8 patients/site/year."
        ),
    },
    {
        "role": "assistant",
        "domain": "SITES",
        "content": (
            "Thank you — all nine intake domains are covered. "
            "You can now compile the Study Brief."
        ),
    },
]

STUDY_BRIEF: dict = {
    "study_overview": {
        "title": "A Phase II Study of ABC-123 in Previously Treated NSCLC",
        "therapeutic_area": "Oncology",
        "indication": "Non-small cell lung cancer (NSCLC), PD-L1 ≥ 1%",
        "phase": "Phase 2",
        "sponsor": "Demo Pharma Inc",
        "compound_code": "ABC-123",
    },
    "study_design": {
        "design_type": "Parallel-group, randomized, open-label",
        "randomization": "1:1 stratified by PD-L1 expression and prior therapy",
        "blinding": "Open-label",
        "comparator": "Investigator's choice standard of care chemotherapy",
        "treatment_duration": "Until progression or unacceptable toxicity",
        "number_of_periods": 3,
    },
    "population": {
        "description": "Adults with previously treated advanced NSCLC",
        "inclusion_criteria": [
            "Age ≥ 18 years",
            "Histologically confirmed NSCLC",
            "PD-L1 tumor proportion score ≥ 1%",
            "Progressed on one prior systemic therapy",
            "ECOG performance status 0 or 1",
        ],
        "exclusion_criteria": [
            "Active autoimmune disease requiring systemic treatment",
            "Untreated or symptomatic brain metastases",
            "Prior therapy with same mechanism class as ABC-123",
        ],
        "age_range": {"min": 18, "max": None},
        "estimated_sample_size": 120,
    },
    "endpoints": {
        "primary": [
            {
                "name": "Progression-free survival",
                "timepoint": "24 weeks",
                "instrument": "RECIST 1.1",
            }
        ],
        "secondary": [
            {"name": "Objective response rate", "timepoint": "Every 8 weeks"},
            {"name": "Overall survival", "timepoint": "End of study"},
            {"name": "Duration of response", "timepoint": "Per RECIST 1.1"},
        ],
        "safety": [
            {"name": "Incidence of adverse events", "timepoint": "Continuous"},
            {"name": "Laboratory abnormalities", "timepoint": "Each cycle"},
        ],
    },
    "drug_treatment": {
        "inn_name": "ABC-123",
        "doses": ["10 mg/kg IV every 3 weeks"],
        "route": "Intravenous infusion",
        "formulation": "Lyophilized powder for solution",
        "regimen": "ABC-123 plus investigator's choice SOC chemotherapy",
    },
    "safety": {
        "key_concerns": [
            "Immune-related adverse events",
            "Infusion-related reactions",
            "Hepatotoxicity",
        ],
        "monitoring_approach": "Safety assessed every treatment cycle; labs per schedule of assessments",
        "stopping_rules": [
            "Hold ABC-123 for Grade ≥ 3 irAE until resolution to Grade ≤ 1",
            "Discontinue for confirmed progressive disease per RECIST 1.1",
        ],
        "sae_definitions": "Per ICH E2A",
        "rems_required": False,
    },
    "regulatory": {
        "regions": ["United States", "European Union"],
        "ind_cta_status": "US IND active; EMA CTA submitted",
        "submission_type": "IND / CTA",
        "gcp_standard": "ICH E6(R2)",
        "special_designations": [],
    },
    "statistical": {
        "framework": "FREQUENTIST",
        "primary_analysis_method": "Stratified log-rank test; Cox proportional hazards model",
        "alpha_level": 0.05,
        "multiple_testing_approach": "Hierarchical testing for secondary endpoints",
        "key_subgroups": ["PD-L1 ≥ 50%", "Prior anti-PD-1/PD-L1 therapy"],
    },
    "sites": {
        "planned_sites": 25,
        "countries": ["United States", "Germany", "France"],
        "estimated_enrollment_rate_per_month": 10,
        "site_selection_criteria": [
            "Oncology trial experience",
            "RECIST-trained imaging",
            "Adequate infusion capacity",
        ],
    },
}

PROTOCOL_CONTENT: dict = {
    "document_type": "PROTOCOL",
    "version": "1.0",
    "title": "A Phase II Study of ABC-123 in Previously Treated NSCLC",
    "protocol_number": "DEMO-001",
    "synopsis": {
        "title": "A Phase II Study of ABC-123 in Previously Treated NSCLC",
        "sponsor": "Demo Pharma Inc",
        "indication": "Non-small cell lung cancer (NSCLC)",
        "phase": "Phase 2",
        "design": "Randomized, parallel-group, open-label",
        "primary_objective": "Evaluate progression-free survival of ABC-123 plus SOC vs SOC alone",
        "primary_endpoint": "PFS per RECIST 1.1 at 24 weeks",
        "sample_size": "N = 120",
        "duration": "Approximately 24 months",
        "regimens": ["ABC-123 10 mg/kg Q3W + SOC", "SOC chemotherapy alone"],
    },
    "objectives": {
        "primary": "Evaluate efficacy of ABC-123 plus SOC versus SOC alone on PFS",
        "secondary": [
            "Objective response rate per RECIST 1.1",
            "Overall survival",
            "Duration of response",
            "Safety and tolerability",
        ],
        "exploratory": ["Biomarker associations with response"],
    },
    "study_design": {
        "type": "Parallel-group randomized",
        "blinding": "Open-label",
        "randomization": "1:1 stratified",
        "treatment_arms": ["ABC-123 + SOC", "SOC alone"],
        "duration_weeks": 104,
        "follow_up_weeks": 52,
    },
    "eligibility": {
        "inclusion_criteria": STUDY_BRIEF["population"]["inclusion_criteria"],
        "exclusion_criteria": STUDY_BRIEF["population"]["exclusion_criteria"],
    },
    "study_procedures": [
        "Screening assessments within 28 days of randomization",
        "Treatment visits every 3 weeks",
        "Tumor imaging every 8 weeks per RECIST 1.1",
        "Safety labs each cycle",
        "End-of-treatment and follow-up visits",
    ],
    "endpoints": {
        "primary": {
            "name": "Progression-free survival",
            "measure": "Time from randomization to progression or death",
            "timepoint": "24 weeks",
        },
        "secondary": [
            {
                "name": "Objective response rate",
                "measure": "Proportion with CR or PR",
                "timepoint": "Every 8 weeks",
            }
        ],
    },
    "statistical_considerations": {
        "sample_size_rationale": "120 patients provide 80% power to detect HR 0.65 at alpha 0.05",
        "primary_analysis": "Stratified log-rank test with Cox model",
        "alpha": 0.05,
        "power": 0.80,
    },
    "safety_monitoring": {
        "dsmb": True,
        "stopping_rules": STUDY_BRIEF["safety"]["stopping_rules"],
    },
    "regulatory_references": ["ICH E6(R2)", "ICH E9", "21 CFR Part 312"],
}

ICF_CONTENT: dict = {
    "document_type": "ICF",
    "version": "1.0",
    "title": "Informed Consent Form — DEMO-001 NSCLC Study",
    "study_summary": (
        "You are being asked to take part in a research study of a study drug called "
        "ABC-123 for non-small cell lung cancer. The study compares ABC-123 plus standard "
        "chemotherapy to standard chemotherapy alone."
    ),
    "sections": {
        "introduction": (
            "You are being invited to participate in a research study. Please read this "
            "form carefully and ask questions before deciding."
        ),
        "purpose": (
            "The purpose of this study is to learn whether adding ABC-123 to standard "
            "chemotherapy helps control lung cancer longer than chemotherapy alone."
        ),
        "number_of_participants": (
            "About 120 people will take part in this study at approximately 25 clinics."
        ),
        "study_procedures": [
            "Screening tests to confirm eligibility",
            "Study drug infusions every 3 weeks if assigned to ABC-123",
            "Regular blood tests and clinic visits",
            "CT or MRI scans every 8 weeks",
        ],
        "risks_and_discomforts": [
            "Immune-related side effects such as rash or diarrhea",
            "Infusion reactions during study drug administration",
            "Side effects from chemotherapy",
        ],
        "potential_benefits": [
            "Possible improvement in cancer control",
            "Close medical monitoring during the study",
        ],
        "alternatives": (
            "You may choose not to participate and receive standard care outside this study."
        ),
        "confidentiality": (
            "Your personal health information will be kept confidential as required by law."
        ),
        "costs_and_compensation": (
            "Study drug and study-related tests are provided at no cost. Travel reimbursement "
            "may be available per site policy."
        ),
        "injury_treatment": (
            "If you are injured as a result of study participation, contact the study doctor "
            "immediately. Compensation for research-related injury is described in the protocol."
        ),
        "voluntary_participation": (
            "Participation is voluntary. You may withdraw at any time without penalty."
        ),
        "contact_information": {
            "study_questions": "Dr. Study Investigator — +1-555-0100",
            "rights_questions": "Institutional Review Board — +1-555-0199",
            "injury_contact": "24-hour study hotline — +1-555-0188",
        },
        "authorization": (
            "Authorization for use and disclosure of protected health information for "
            "research purposes as described in this document."
        ),
    },
    "readability_level": "8th grade",
    "regulatory_references": ["21 CFR Part 50", "ICH E6(R2)", "45 CFR Part 46"],
}

SAP_CONTENT: dict = {
    "document_type": "SAP",
    "version": "1.0",
    "title": "Statistical Analysis Plan — DEMO-001",
    "study_design_summary": (
        "Randomized 1:1 open-label Phase II study comparing ABC-123 plus SOC "
        "versus SOC alone in previously treated NSCLC (N=120)."
    ),
    "analysis_populations": {
        "ITT": "All randomized subjects",
        "mITT": "All randomized subjects who receive at least one dose",
        "PP": "ITT excluding major protocol deviations affecting efficacy",
        "safety": "All subjects receiving at least one dose of study treatment",
    },
    "estimands": [
        {
            "name": "Primary PFS estimand",
            "treatment": "ABC-123 + SOC vs SOC",
            "population": "ITT",
            "variable": "Time to progression or death",
            "intercurrent_events": ["Treatment discontinuation", "Subsequent anti-cancer therapy"],
            "summary_measure": "Hazard ratio",
        }
    ],
    "primary_endpoint_analysis": {
        "endpoint": "Progression-free survival",
        "hypothesis": "H0: HR = 1 vs Ha: HR ≠ 1",
        "test": "Stratified log-rank test",
        "covariates": ["PD-L1 stratum", "Prior anti-PD-1/PD-L1 therapy"],
        "alpha": 0.05,
        "two_sided": True,
        "multiplicity_adjustment": "None for primary endpoint",
    },
    "secondary_endpoints": [
        {
            "endpoint": "Objective response rate",
            "analysis_method": "Cochran-Mantel-Haenszel test",
            "notes": "Confirmed per RECIST 1.1",
        },
        {
            "endpoint": "Overall survival",
            "analysis_method": "Stratified log-rank test",
            "notes": "Tested hierarchically after PFS",
        },
    ],
    "subgroup_analyses": ["PD-L1 ≥ 50%", "Prior anti-PD-1/PD-L1 therapy"],
    "sensitivity_analyses": [
        "PFS censoring at start of subsequent anti-cancer therapy",
        "Per-protocol analysis",
    ],
    "missing_data": {
        "anticipated_mechanism": "MAR",
        "primary_approach": "Cox model with covariates",
        "sensitivity_approach": "Tipping point analysis for missing tumor assessments",
    },
    "interim_analyses": {
        "planned": True,
        "number": 1,
        "stopping_rules": ["DSMB review at 50% enrollment for safety"],
    },
    "safety_analyses": {
        "AE_summary": "Incidence tables by SOC and preferred term",
        "lab_analysis": "Shift tables for hematology and chemistry",
        "exposure_analysis": "Duration of exposure and dose intensity",
    },
    "software": ["SAS 9.4", "R 4.3"],
    "regulatory_references": ["ICH E9(R1)", "ICH E3", "FDA SAP Guidance 2019"],
}

EDC_CRF_CONTENT: dict = {
    "document_type": "EDC_CRF",
    "version": "1.0",
    "title": "DEMO-001 eCRF Specification",
    "edc_vendor": "TrialGenesis Mock EDC",
    "build_status": "COMPLETE",
    "visit_schedule": [
        {"visit_id": "SCR", "label": "Screening", "day": -28, "window_days": 28},
        {"visit_id": "C1D1", "label": "Cycle 1 Day 1", "day": 1, "window_days": 0},
        {"visit_id": "C2D1", "label": "Cycle 2 Day 1", "day": 22, "window_days": 3},
        {"visit_id": "TU8W", "label": "Tumor Assessment Week 8", "day": 57, "window_days": 7},
        {"visit_id": "EOT", "label": "End of Treatment", "day": None, "window_days": 7},
        {"visit_id": "FU30", "label": "30-Day Follow-up", "day": None, "window_days": 7},
    ],
    "forms": [
        {
            "form_id": "DM",
            "form_name": "Demographics",
            "visit": "Screening",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "BRTHDTC", "label": "Date of Birth", "type": "date", "required": True},
                {"field_id": "SEX", "label": "Sex", "type": "select", "options": ["M", "F"], "required": True},
                {"field_id": "RACE", "label": "Race", "type": "multiselect", "required": True},
                {"field_id": "ETHNIC", "label": "Ethnicity", "type": "select", "required": True},
            ],
        },
        {
            "form_id": "IE",
            "form_name": "Inclusion / Exclusion",
            "visit": "Screening",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "IEYN", "label": "Meets all eligibility criteria?", "type": "yesno", "required": True},
                {"field_id": "PDL1TPS", "label": "PD-L1 TPS (%)", "type": "number", "required": True},
                {"field_id": "ECOG", "label": "ECOG Performance Status", "type": "select", "options": ["0", "1"], "required": True},
            ],
        },
        {
            "form_id": "MH",
            "form_name": "Medical History",
            "visit": "Screening",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "MHTERM", "label": "Condition", "type": "text", "required": True},
                {"field_id": "MHSTDTC", "label": "Start Date", "type": "date", "required": False},
                {"field_id": "MHONGO", "label": "Ongoing?", "type": "yesno", "required": True},
            ],
        },
        {
            "form_id": "EX",
            "form_name": "Study Drug Exposure",
            "visit": "Cycle 1 Day 1",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "EXSTDTC", "label": "Treatment Start Date", "type": "date", "required": True},
                {"field_id": "EXDOSE", "label": "ABC-123 Dose (mg/kg)", "type": "number", "required": True},
                {"field_id": "EXROUTE", "label": "Route", "type": "select", "options": ["IV"], "required": True},
            ],
        },
        {
            "form_id": "AE",
            "form_name": "Adverse Events",
            "visit": "All treatment visits",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "AETERM", "label": "Adverse Event Term", "type": "text", "required": True},
                {"field_id": "AESTDTC", "label": "Start Date", "type": "date", "required": True},
                {"field_id": "AESEV", "label": "Severity (CTCAE)", "type": "select", "options": ["1", "2", "3", "4", "5"], "required": True},
                {"field_id": "AESER", "label": "Serious?", "type": "yesno", "required": True},
            ],
        },
        {
            "form_id": "TU",
            "form_name": "Tumor Assessment",
            "visit": "Tumor Assessment Week 8",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "TUDTC", "label": "Assessment Date", "type": "date", "required": True},
                {"field_id": "TUMETHOD", "label": "Method", "type": "select", "options": ["CT", "MRI"], "required": True},
                {"field_id": "TUORRES", "label": "Overall Response", "type": "select", "options": ["CR", "PR", "SD", "PD", "NE"], "required": True},
            ],
        },
        {
            "form_id": "DS",
            "form_name": "Disposition",
            "visit": "End of Treatment",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "DSDECOD", "label": "Disposition Reason", "type": "select", "options": ["Completed", "Progression", "Adverse Event", "Withdrawal"], "required": True},
                {"field_id": "DSSTDTC", "label": "Disposition Date", "type": "date", "required": True},
            ],
        },
    ],
}

SYNTHETIC_DATASET_CONTENT: dict = {
    "label": "SYNTHETIC",
    "document_type": "RAW_CLINICAL_DATA",
    "format": "EDC_EXPORT",
    "description": (
        "Synthetic patient-level eCRF exports for DEMO-001 development and validation. "
        "Raw collection format — not SDTM."
    ),
    "random_seed": 42,
    "synthetic_flag": "Y",
    "source_system": "TrialGenesis Mock EDC",
    "record_counts": {"subjects": 120, "form_entries": 960},
    "datasets": {
        "demographics": {
            "form_id": "DM",
            "form_name": "Demographics",
            "visit": "Screening",
            "columns": ["SUBJECT_ID", "SITE_ID", "VISIT", "BRTHDTC", "SEX", "RACE", "ETHNIC"],
            "row_count": 120,
            "sample_rows": [
                {
                    "SUBJECT_ID": "DEMO-001-001",
                    "SITE_ID": "001",
                    "VISIT": "SCR",
                    "BRTHDTC": "1961-04-12",
                    "SEX": "F",
                    "RACE": "White",
                    "ETHNIC": "Not Hispanic or Latino",
                },
                {
                    "SUBJECT_ID": "DEMO-001-002",
                    "SITE_ID": "001",
                    "VISIT": "SCR",
                    "BRTHDTC": "1966-09-03",
                    "SEX": "M",
                    "RACE": "Asian",
                    "ETHNIC": "Not Hispanic or Latino",
                },
                {
                    "SUBJECT_ID": "DEMO-001-003",
                    "SITE_ID": "002",
                    "VISIT": "SCR",
                    "BRTHDTC": "1954-11-28",
                    "SEX": "F",
                    "RACE": "Black or African American",
                    "ETHNIC": "Not Hispanic or Latino",
                },
            ],
        },
        "adverse_events": {
            "form_id": "AE",
            "form_name": "Adverse Events",
            "visit": "All treatment visits",
            "columns": [
                "SUBJECT_ID",
                "SITE_ID",
                "VISIT",
                "AETERM",
                "AESTDTC",
                "AESEV",
                "AESER",
            ],
            "row_count": 487,
            "sample_rows": [
                {
                    "SUBJECT_ID": "DEMO-001-001",
                    "SITE_ID": "001",
                    "VISIT": "C2D1",
                    "AETERM": "Fatigue",
                    "AESTDTC": "2025-02-01",
                    "AESEV": "2",
                    "AESER": "No",
                },
                {
                    "SUBJECT_ID": "DEMO-001-002",
                    "SITE_ID": "001",
                    "VISIT": "C1D1",
                    "AETERM": "Nausea",
                    "AESTDTC": "2025-01-20",
                    "AESEV": "1",
                    "AESER": "No",
                },
            ],
        },
        "tumor_assessment": {
            "form_id": "TU",
            "form_name": "Tumor Assessment",
            "visit": "Tumor Assessment Week 8",
            "columns": ["SUBJECT_ID", "SITE_ID", "VISIT", "TUDTC", "TUMETHOD", "TUORRES"],
            "row_count": 240,
            "sample_rows": [
                {
                    "SUBJECT_ID": "DEMO-001-001",
                    "SITE_ID": "001",
                    "VISIT": "TU8W",
                    "TUDTC": "2025-03-10",
                    "TUMETHOD": "CT",
                    "TUORRES": "SD",
                },
            ],
        },
    },
}

SYNTHETIC_RUN = {
    "run_name": "DEMO-001 Baseline Synthetic Cohort",
    "description": (
        "Reproducible synthetic NSCLC cohort (N=120) aligned to DEMO-001 protocol "
        "eligibility and endpoint definitions. Labeled SYNTHETIC — not for regulatory submission."
    ),
    "target_n": 120,
    "random_seed": 42,
    "configuration": {
        "distributions": {
            "age": {"type": "normal", "mean": 65, "sd": 9, "min": 38, "max": 84},
            "sex": {"type": "categorical", "weights": {"M": 0.55, "F": 0.45}},
            "arm": {"type": "categorical", "weights": {"ABC-123 + SOC": 0.5, "SOC": 0.5}},
        },
        "forms_generated": ["DM", "IE", "MH", "EX", "AE", "TU", "DS"],
        "label": "SYNTHETIC",
    },
}

SYNTHETIC_ASSUMPTIONS = [
    {
        "assumption_type": "DEMOGRAPHIC_DISTRIBUTION",
        "domain": "DM",
        "variable": "AGE",
        "description": "Age drawn from Normal(65, 9) truncated to 38–84 years",
        "rationale": "Matches expected NSCLC trial population",
        "parameters": {"mean": 65, "sd": 9},
        "source_reference": "SEER 2018–2022 age distribution (approximated)",
    },
    {
        "assumption_type": "TREATMENT_ASSIGNMENT",
        "domain": "DM",
        "variable": "ARM",
        "description": "1:1 random assignment to ABC-123 + SOC vs SOC",
        "rationale": "Mirrors protocol randomization",
        "parameters": {"ratio": "1:1"},
        "source_reference": "DEMO-001 protocol Section 5.1",
    },
    {
        "assumption_type": "AE_RATE",
        "domain": "AE",
        "variable": "AETERM",
        "description": "AE incidence calibrated to Phase II IO+chemo class",
        "rationale": "Supports safety table mock-ups",
        "parameters": {"mean_events_per_subject": 4.1},
        "source_reference": "Published NSCLC checkpoint inhibitor trials (approximated)",
    },
]

DEMO_MARKER = "demo-program-seed:v1"
