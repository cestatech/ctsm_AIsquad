"""Static demo content for DEMO-002 — Phase III Rheumatoid Arthritis Pivotal Study."""

from __future__ import annotations

PROTOCOL_NUMBER = "DEMO-002"

STUDY_NAME = "Phase III Rheumatoid Arthritis Pivotal Study"

STUDY_META = {
    "indication": "Moderate-to-severe rheumatoid arthritis (RA) with inadequate MTX response",
    "therapeutic_area": "Immunology / Rheumatology",
    "phase": "PHASE_3",
    "sponsor": "Demo Pharma Inc",
    "short_name": "DEMO-002 RA",
    "description": (
        "Randomized, double-blind Phase III study of XYZ-456 versus adalimumab "
        "in patients with RA on background methotrexate."
    ),
}

INTAKE_CONVERSATION: list[dict] = [
    {
        "role": "assistant",
        "domain": "STUDY_OVERVIEW",
        "content": (
            "Welcome to sponsor intake for the Phase III RA pivotal study. "
            "Please provide study title, therapeutic area, indication, phase, sponsor, and compound."
        ),
    },
    {
        "role": "user",
        "content": (
            "Phase III RA study of XYZ-456 vs adalimumab. Demo Pharma Inc. "
            "Immunology, moderate-to-severe RA, compound XYZ-456."
        ),
    },
    {
        "role": "assistant",
        "domain": "STUDY_DESIGN",
        "content": "Describe study design, randomization, blinding, comparator, and treatment duration.",
    },
    {
        "role": "user",
        "content": (
            "Parallel-group, 1:1:1 randomization, double-blind. Arms: XYZ-456, adalimumab, placebo. "
            "Background MTX required. 52-week double-blind period plus open-label extension."
        ),
    },
    {
        "role": "assistant",
        "domain": "POPULATION",
        "content": "Describe inclusion/exclusion criteria, age range, and planned sample size.",
    },
    {
        "role": "user",
        "content": (
            "Adults 18–75 with RA per ACR/EULAR 2010, DAS28-CRP ≥ 3.2, inadequate MTX response. "
            "N≈450. Exclude prior biologic DMARD failure >2 agents."
        ),
    },
    {
        "role": "assistant",
        "domain": "ENDPOINTS",
        "content": "Primary and key secondary endpoints with timepoints.",
    },
    {
        "role": "user",
        "content": (
            "Primary: ACR20 at Week 12. Secondary: DAS28-CRP remission, HAQ-DI change, "
            "radiographic progression at Week 52, safety."
        ),
    },
    {
        "role": "assistant",
        "domain": "DRUG_TREATMENT",
        "content": "Investigational product dosing, route, and regimen details.",
    },
    {
        "role": "user",
        "content": (
            "XYZ-456 150 mg SC Q2W; adalimumab 40 mg SC Q2W per label; stable MTX 15–25 mg weekly."
        ),
    },
    {
        "role": "assistant",
        "domain": "SAFETY",
        "content": "Key safety concerns and monitoring.",
    },
    {
        "role": "user",
        "content": (
            "Infection risk, injection-site reactions, TB screening. Labs every 12 weeks. "
            "DSMB quarterly."
        ),
    },
    {
        "role": "assistant",
        "domain": "REGULATORY",
        "content": "Regulatory regions and submission status.",
    },
    {
        "role": "user",
        "content": "US, EU, Japan. IND active US; PMDA consultation complete.",
    },
    {
        "role": "assistant",
        "domain": "STATISTICAL",
        "content": "Statistical framework and primary analysis approach.",
    },
    {
        "role": "user",
        "content": (
            "Frequentist, non-inferiority margin 10% for ACR20 vs adalimumab. "
            "Stratified CMH test, alpha 0.05."
        ),
    },
    {
        "role": "assistant",
        "domain": "SITES",
        "content": "Planned sites, countries, enrollment rate.",
    },
    {
        "role": "user",
        "content": "60 sites across US, Germany, Poland, Japan. Target 15 patients/site/year.",
    },
    {
        "role": "assistant",
        "domain": "SITES",
        "content": "All nine domains are covered. You may compile the Study Brief.",
    },
]

STUDY_BRIEF: dict = {
    "study_overview": {
        "title": "A Phase III Study of XYZ-456 in Rheumatoid Arthritis",
        "therapeutic_area": "Immunology / Rheumatology",
        "indication": "Moderate-to-severe rheumatoid arthritis",
        "phase": "Phase 3",
        "sponsor": "Demo Pharma Inc",
        "compound_code": "XYZ-456",
    },
    "study_design": {
        "design_type": "Randomized, double-blind, parallel-group",
        "randomization": "1:1:1 stratified by region and prior biologic use",
        "blinding": "Double-blind",
        "comparator": "Adalimumab and placebo",
        "treatment_duration": "52 weeks",
        "number_of_periods": 2,
    },
    "population": {
        "description": "Adults with active RA on stable MTX",
        "inclusion_criteria": [
            "Age 18–75 years",
            "RA diagnosis per ACR/EULAR 2010",
            "DAS28-CRP ≥ 3.2",
            "Inadequate response to MTX",
        ],
        "exclusion_criteria": [
            "Prior failure of >2 biologic DMARDs",
            "Active serious infection",
            "Untreated latent TB",
        ],
        "age_range": {"min": 18, "max": 75},
        "estimated_sample_size": 450,
    },
    "endpoints": {
        "primary": [{"name": "ACR20 response", "timepoint": "Week 12", "instrument": "ACR core set"}],
        "secondary": [
            {"name": "DAS28-CRP remission", "timepoint": "Week 24"},
            {"name": "HAQ-DI change", "timepoint": "Week 12"},
            {"name": "mTSS change", "timepoint": "Week 52"},
        ],
        "safety": [{"name": "Adverse events", "timepoint": "Continuous"}],
    },
    "drug_treatment": {
        "inn_name": "XYZ-456",
        "doses": ["150 mg subcutaneous every 2 weeks"],
        "route": "Subcutaneous",
        "formulation": "Prefilled syringe",
        "regimen": "XYZ-456 or adalimumab plus weekly MTX",
    },
    "safety": {
        "key_concerns": ["Serious infections", "Injection-site reactions", "Hepatotoxicity"],
        "monitoring_approach": "Safety labs every 12 weeks; TB screening at screening",
        "stopping_rules": ["Hold for Grade ≥3 infection until resolved"],
        "sae_definitions": "Per ICH E2A",
        "rems_required": False,
    },
    "regulatory": {
        "regions": ["United States", "European Union", "Japan"],
        "ind_cta_status": "US IND active; EU CTA submitted",
        "submission_type": "IND / CTA",
        "gcp_standard": "ICH E6(R2)",
        "special_designations": [],
    },
    "statistical": {
        "framework": "FREQUENTIST",
        "primary_analysis_method": "Stratified Cochran-Mantel-Haenszel for ACR20",
        "alpha_level": 0.05,
        "multiple_testing_approach": "Hierarchical gatekeeping for secondary endpoints",
        "key_subgroups": ["Prior biologic use", "Region"],
    },
    "sites": {
        "planned_sites": 60,
        "countries": ["United States", "Germany", "Poland", "Japan"],
        "estimated_enrollment_rate_per_month": 25,
        "site_selection_criteria": ["RA trial experience", "X-ray capability", "Biologic storage"],
    },
}

PROTOCOL_CONTENT: dict = {
    "document_type": "PROTOCOL",
    "version": "1.0",
    "title": "A Phase III Study of XYZ-456 in Rheumatoid Arthritis",
    "protocol_number": PROTOCOL_NUMBER,
    "synopsis": {
        "title": "A Phase III Study of XYZ-456 in Rheumatoid Arthritis",
        "sponsor": "Demo Pharma Inc",
        "indication": "Rheumatoid arthritis",
        "phase": "Phase 3",
        "design": "Randomized, double-blind, active- and placebo-controlled",
        "primary_objective": "Demonstrate efficacy of XYZ-456 on ACR20 at Week 12",
        "primary_endpoint": "Proportion achieving ACR20 at Week 12",
        "sample_size": "N = 450",
        "duration": "52 weeks",
        "regimens": ["XYZ-456 + MTX", "Adalimumab + MTX", "Placebo + MTX"],
    },
    "objectives": {
        "primary": "Evaluate ACR20 response rate for XYZ-456 versus adalimumab at Week 12",
        "secondary": ["DAS28-CRP remission", "HAQ-DI", "Radiographic progression", "Safety"],
        "exploratory": ["Pharmacokinetics and immunogenicity"],
    },
    "study_design": {
        "type": "Parallel-group randomized",
        "blinding": "Double-blind",
        "randomization": "1:1:1 stratified",
        "treatment_arms": ["XYZ-456", "Adalimumab", "Placebo"],
        "duration_weeks": 52,
        "follow_up_weeks": 12,
    },
    "eligibility": {
        "inclusion_criteria": STUDY_BRIEF["population"]["inclusion_criteria"],
        "exclusion_criteria": STUDY_BRIEF["population"]["exclusion_criteria"],
    },
    "study_procedures": [
        "Screening within 28 days",
        "Randomization at Week 0",
        "Study drug Q2W through Week 50",
        "Joint counts and DAS28 at Weeks 0, 4, 12, 24, 52",
        "X-rays at baseline and Week 52",
    ],
    "endpoints": {
        "primary": {
            "name": "ACR20",
            "measure": "≥20% improvement in ACR core set",
            "timepoint": "Week 12",
        },
        "secondary": [{"name": "DAS28-CRP remission", "measure": "DAS28-CRP < 2.6", "timepoint": "Week 24"}],
    },
    "statistical_considerations": {
        "sample_size_rationale": "450 patients for 90% power on non-inferiority margin",
        "primary_analysis": "Stratified CMH test",
        "alpha": 0.05,
        "power": 0.90,
    },
    "safety_monitoring": {"dsmb": True, "stopping_rules": STUDY_BRIEF["safety"]["stopping_rules"]},
    "regulatory_references": ["ICH E6(R2)", "ICH E9", "21 CFR Part 312"],
}

ICF_CONTENT: dict = {
    "document_type": "ICF",
    "version": "1.0",
    "title": "Informed Consent Form — DEMO-002 RA Study",
    "study_summary": (
        "You are being asked to join a research study of XYZ-456 for rheumatoid arthritis. "
        "The study compares XYZ-456 to adalimumab and placebo, all with methotrexate."
    ),
    "sections": {
        "introduction": "You are invited to participate in a research study. Please read carefully.",
        "purpose": "To learn whether XYZ-456 improves RA symptoms compared with approved treatments.",
        "number_of_participants": "About 450 people at 60 clinics worldwide.",
        "study_procedures": [
            "Screening visits and blood tests",
            "Subcutaneous injections every 2 weeks",
            "Joint exams and questionnaires",
            "X-rays of hands and feet",
        ],
        "risks_and_discomforts": ["Injection-site reactions", "Infections", "Routine blood draw discomfort"],
        "potential_benefits": ["Possible improvement in joint symptoms", "Close medical monitoring"],
        "alternatives": "You may choose standard RA care outside this study.",
        "confidentiality": "Your health information will be kept confidential per applicable law.",
        "costs_and_compensation": "Study drug provided at no cost. Visit stipend per site policy.",
        "injury_treatment": "Contact the study doctor immediately for research-related injury.",
        "voluntary_participation": "You may withdraw at any time without penalty.",
        "contact_information": {
            "study_questions": "Dr. RA Investigator — +1-555-0200",
            "rights_questions": "IRB — +1-555-0299",
            "injury_contact": "24-hour hotline — +1-555-0288",
        },
        "authorization": "Authorization for use of protected health information for research.",
    },
    "readability_level": "8th grade",
    "regulatory_references": ["21 CFR Part 50", "ICH E6(R2)"],
}

SAP_CONTENT: dict = {
    "document_type": "SAP",
    "version": "1.0",
    "title": "Statistical Analysis Plan — DEMO-002",
    "study_design_summary": "Phase III 1:1:1 RA study, N=450, primary endpoint ACR20 at Week 12.",
    "analysis_populations": {
        "ITT": "All randomized subjects",
        "mITT": "Randomized subjects receiving ≥1 dose",
        "PP": "ITT without major protocol deviations",
        "safety": "Subjects receiving ≥1 dose",
    },
    "estimands": [{
        "name": "Primary ACR20 estimand",
        "treatment": "XYZ-456 vs adalimumab vs placebo",
        "population": "ITT",
        "variable": "ACR20 response at Week 12",
        "intercurrent_events": ["Treatment discontinuation", "Rescue therapy"],
        "summary_measure": "Risk difference",
    }],
    "primary_endpoint_analysis": {
        "endpoint": "ACR20 at Week 12",
        "hypothesis": "Non-inferiority of XYZ-456 vs adalimumab",
        "test": "Stratified Cochran-Mantel-Haenszel",
        "covariates": ["Region", "Prior biologic use"],
        "alpha": 0.05,
        "two_sided": False,
        "multiplicity_adjustment": "Hierarchical testing for secondary endpoints",
    },
    "secondary_endpoints": [
        {"endpoint": "DAS28-CRP remission", "analysis_method": "Logistic regression", "notes": "Week 24"},
    ],
    "subgroup_analyses": ["Prior biologic use", "Geographic region"],
    "sensitivity_analyses": ["Per-protocol analysis", "Tipping point for missing ACR components"],
    "missing_data": {
        "anticipated_mechanism": "MAR",
        "primary_approach": "Multiple imputation for partial ACR data",
        "sensitivity_approach": "Composite estimand with intercurrent events",
    },
    "interim_analyses": {"planned": True, "number": 1, "stopping_rules": ["DSMB safety review at 50% enrollment"]},
    "safety_analyses": {
        "AE_summary": "SOC and PT incidence tables",
        "lab_analysis": "Shift tables for hepatic and hematology parameters",
        "exposure_analysis": "Duration of exposure by arm",
    },
    "software": ["SAS 9.4", "R 4.3"],
    "regulatory_references": ["ICH E9(R1)", "FDA RA guidance"],
}

EDC_CRF_CONTENT: dict = {
    "document_type": "EDC_CRF",
    "version": "1.0",
    "title": "DEMO-002 eCRF Specification",
    "edc_vendor": "TrialGenesis Mock EDC",
    "build_status": "COMPLETE",
    "visit_schedule": [
        {"visit_id": "SCR", "label": "Screening", "day": -28, "window_days": 28},
        {"visit_id": "W0", "label": "Baseline / Randomization", "day": 1, "window_days": 0},
        {"visit_id": "W4", "label": "Week 4", "day": 29, "window_days": 7},
        {"visit_id": "W12", "label": "Week 12 (Primary)", "day": 85, "window_days": 7},
        {"visit_id": "W52", "label": "Week 52 / EOS", "day": 365, "window_days": 14},
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
            ],
        },
        {
            "form_id": "IE",
            "form_name": "Inclusion / Exclusion",
            "visit": "Screening",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "IEYN", "label": "Meets eligibility?", "type": "yesno", "required": True},
                {"field_id": "DAS28", "label": "DAS28-CRP at screening", "type": "number", "required": True},
            ],
        },
        {
            "form_id": "RA",
            "form_name": "Joint Count / ACR Components",
            "visit": "Week 12",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "TJC68", "label": "Tender joint count (68)", "type": "number", "required": True},
                {"field_id": "SJC66", "label": "Swollen joint count (66)", "type": "number", "required": True},
                {"field_id": "CRP", "label": "CRP (mg/L)", "type": "number", "required": True},
                {"field_id": "ACR20", "label": "ACR20 met?", "type": "yesno", "required": True},
            ],
        },
        {
            "form_id": "HAQ",
            "form_name": "HAQ-DI",
            "visit": "Week 12",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "HAQSC", "label": "HAQ-DI score", "type": "number", "required": True},
            ],
        },
        {
            "form_id": "EX",
            "form_name": "Study Drug Exposure",
            "visit": "Baseline",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "ARM", "label": "Treatment arm", "type": "select", "options": ["XYZ-456", "Adalimumab", "Placebo"], "required": True},
                {"field_id": "EXSTDTC", "label": "First dose date", "type": "date", "required": True},
            ],
        },
        {
            "form_id": "AE",
            "form_name": "Adverse Events",
            "visit": "All visits",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "AETERM", "label": "AE term", "type": "text", "required": True},
                {"field_id": "AESEV", "label": "Severity", "type": "select", "options": ["1", "2", "3", "4", "5"], "required": True},
            ],
        },
        {
            "form_id": "DS",
            "form_name": "Disposition",
            "visit": "Week 52",
            "status": "COMPLETE",
            "fields": [
                {"field_id": "DSDECOD", "label": "Disposition", "type": "select", "options": ["Completed", "Withdrawal", "Lost to follow-up"], "required": True},
            ],
        },
    ],
}

SYNTHETIC_DATASET_CONTENT: dict = {
    "label": "SYNTHETIC",
    "document_type": "RAW_CLINICAL_DATA",
    "format": "EDC_EXPORT",
    "description": (
        "Synthetic patient-level eCRF exports for DEMO-002 RA study. "
        "Raw collection format — not SDTM."
    ),
    "random_seed": 2026,
    "synthetic_flag": "Y",
    "source_system": "TrialGenesis Mock EDC",
    "record_counts": {"subjects": 450, "form_entries": 3150},
    "datasets": {
        "demographics": {
            "form_id": "DM",
            "form_name": "Demographics",
            "visit": "Screening",
            "columns": ["SUBJECT_ID", "SITE_ID", "VISIT", "BRTHDTC", "SEX", "RACE"],
            "row_count": 450,
            "sample_rows": [
                {
                    "SUBJECT_ID": "DEMO-002-001",
                    "SITE_ID": "101",
                    "VISIT": "SCR",
                    "BRTHDTC": "1971-06-14",
                    "SEX": "F",
                    "RACE": "White",
                },
                {
                    "SUBJECT_ID": "DEMO-002-002",
                    "SITE_ID": "101",
                    "VISIT": "SCR",
                    "BRTHDTC": "1963-02-08",
                    "SEX": "M",
                    "RACE": "Asian",
                },
            ],
        },
        "ra_joint_count": {
            "form_id": "RA",
            "form_name": "Joint Count / ACR Components",
            "visit": "Week 12",
            "columns": [
                "SUBJECT_ID",
                "SITE_ID",
                "VISIT",
                "TJC68",
                "SJC66",
                "CRP",
                "ACR20",
            ],
            "row_count": 450,
            "sample_rows": [
                {
                    "SUBJECT_ID": "DEMO-002-001",
                    "SITE_ID": "101",
                    "VISIT": "W12",
                    "TJC68": "4",
                    "SJC66": "2",
                    "CRP": "8.2",
                    "ACR20": "Yes",
                },
            ],
        },
        "adverse_events": {
            "form_id": "AE",
            "form_name": "Adverse Events",
            "visit": "All visits",
            "columns": ["SUBJECT_ID", "SITE_ID", "VISIT", "AETERM", "AESEV"],
            "row_count": 1820,
            "sample_rows": [
                {
                    "SUBJECT_ID": "DEMO-002-001",
                    "SITE_ID": "101",
                    "VISIT": "W4",
                    "AETERM": "Injection site erythema",
                    "AESEV": "1",
                },
            ],
        },
    },
}

SYNTHETIC_RUN = {
    "run_name": "DEMO-002 RA Synthetic Cohort",
    "description": "Reproducible synthetic RA cohort (N=450) for DEMO-002. Labeled SYNTHETIC.",
    "target_n": 450,
    "random_seed": 2026,
    "configuration": {
        "distributions": {
            "age": {"type": "normal", "mean": 56, "sd": 11, "min": 22, "max": 74},
            "sex": {"type": "categorical", "weights": {"F": 0.72, "M": 0.28}},
            "arm": {"type": "categorical", "weights": {"XYZ-456": 0.33, "Adalimumab": 0.33, "Placebo": 0.34}},
        },
        "forms_generated": ["DM", "IE", "RA", "HAQ", "EX", "AE", "DS"],
        "label": "SYNTHETIC",
    },
}

SYNTHETIC_ASSUMPTIONS = [
    {
        "assumption_type": "DEMOGRAPHIC_DISTRIBUTION",
        "domain": "DM",
        "variable": "AGE",
        "description": "Age ~ Normal(56, 11) truncated to 22–74",
        "rationale": "Typical Phase III RA population",
        "parameters": {"mean": 56, "sd": 11},
        "source_reference": "Published RA trial demographics (approximated)",
    },
    {
        "assumption_type": "ACR20_RATE",
        "domain": "RA",
        "variable": "ACR20",
        "description": "ACR20 response calibrated to active-comparator RA trials",
        "rationale": "Supports efficacy table mock-ups",
        "parameters": {"acr20_rate_xyz": 0.62, "acr20_rate_ada": 0.58},
        "source_reference": "DEMO-002 protocol Section 8",
    },
]
