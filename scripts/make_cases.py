"""Generate the starter synthetic evaluation cases in evals/cases/.

All patients and notes are fictional. Answer keys are DRAFTS until a certified
coder reviews them; set "review_status" to "reviewed by CPC <date>" after review.
CPT codes appear as numbers only (no AMA descriptors).
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "evals" / "cases"
DRAFT = "reviewed by CPC 2026-11-11"

CASES = [
    {
        "id": "case_001", "date_of_service": "2026-03-10",
        "note": """Established patient, 58M, follow-up for type 2 diabetes and hypertension. Commercial insurance.
HPI: Home glucose readings 220-280 fasting over the past month. Taking metformin 1000 mg BID as prescribed. No hypoglycemia.
Vitals: BP 142/88. A1c today (sent out) pending; last A1c 9.4%.
Assessment/Plan:
1. Type 2 diabetes mellitus with hyperglycemia, uncontrolled. Add empagliflozin 10 mg daily. Continue metformin. Recheck A1c in 3 months.
2. Essential hypertension, not at goal. Increase lisinopril to 20 mg.
Long-term use of oral hypoglycemic drugs.
Medical decision making: moderate (two chronic illnesses with exacerbation/progression, prescription drug management).""",
        "gold": {"diagnoses": [{"code": "E11.65"}, {"code": "I10"}, {"code": "Z79.84"}], "first_listed": "E11.65",
                 "procedures": [{"code": "99214"}], "edit_flags_expected": []},
    },
    {
        "id": "case_002", "date_of_service": "2026-02-02",
        "note": """Established patient, 24F, 2 days of sore throat, fever 101.2 F, tender anterior cervical nodes, tonsillar exudate. No cough. Commercial insurance.
In-office rapid strep antigen test (immunoassay with direct optical observation): POSITIVE.
Assessment: Acute streptococcal pharyngitis.
Plan: Amoxicillin 500 mg BID x 10 days. Return if not improved in 72 hours.
MDM: low (acute uncomplicated illness, prescription drug management).""",
        "gold": {"diagnoses": [{"code": "J02.0"}], "first_listed": "J02.0",
                 "procedures": [{"code": "99213"}, {"code": "87880"}], "edit_flags_expected": []},
    },
    {
        "id": "case_003", "date_of_service": "2026-04-15",
        "note": """Established patient, 35M, cut right forearm on a kitchen knife while cooking at home 2 hours ago. Commercial insurance.
Exam: 2.0 cm linear laceration, dorsal right forearm, subcutaneous depth, no foreign body, no tendon involvement, neurovascularly intact.
Procedure: Wound irrigated, simple single-layer closure with 4-0 nylon, 3 sutures. Length repaired: 2.0 cm.
Assessment: Laceration without foreign body of right forearm, initial encounter.
Plan: Suture removal in 10 days. Tetanus up to date.""",
        "gold": {"diagnoses": [{"code": "S51.811A"}], "first_listed": "S51.811A",
                 "optional_dx": ["W26.0XXA", "Y93.G3", "Y92.010", "Y92.000", "Y92.009", "Y99.8"],
                 "procedures": [{"code": "12001"}], "edit_flags_expected": []},
    },
    {
        "id": "case_004", "date_of_service": "2026-05-20",
        "note": """Established patient, 67F, Medicare. Two issues today.
1. Right knee pain from known primary osteoarthritis, worse this month. After consent and sterile prep, injected the right knee joint (intra-articular) with methylprednisolone acetate 40 mg and lidocaine, without ultrasound guidance. Tolerated well.
2. Hypertension follow-up, separately evaluated: BP 150/92 on amlodipine 5 mg; increased to 10 mg; BMP ordered. Reviewed home log.
Assessment: Primary osteoarthritis, right knee. Essential hypertension, not controlled.
The hypertension evaluation is significant and separately identifiable from the knee injection. MDM for the hypertension: low.""",
        "gold": {"diagnoses": [{"code": "M17.11"}, {"code": "I10"}], "first_listed": "M17.11",
                 "first_listed_alternates": ["I10"],
                 "procedures": [{"code": "20610", "optional_modifiers": ["RT"]},
                                {"code": "99213", "modifiers": ["25"]}, {"code": "J1030", "units": 1}],
                 "edit_flags_expected": []},
    },
    {
        "id": "case_005", "date_of_service": "2026-01-12",
        "note": """Established patient, 49M, 6 days of cough, fever and shortness of breath. Commercial insurance.
Home COVID-19 antigen positive 4 days ago, confirmed by outside PCR (result reviewed).
Chest x-ray (outside, reviewed): right lower lobe infiltrate. SpO2 95% on room air.
Assessment: Pneumonia due to COVID-19.
Plan: Supportive care, return precautions, pulse oximeter at home.
MDM: moderate (acute illness with systemic symptoms, review of external tests).""",
        "gold": {"diagnoses": [{"code": "U07.1"}, {"code": "J12.82"}], "first_listed": "U07.1",
                 "procedures": [{"code": "99214"}], "edit_flags_expected": []},
    },
    {
        "id": "case_006", "date_of_service": "2026-06-03",
        "note": """Established patient, 72M, Medicare, follow-up of chronic systolic heart failure (EF 35% on last echo) and long-standing hypertension.
Weight stable, no edema, NYHA class II. BP 128/76.
Assessment: Chronic systolic (congestive) heart failure, stable. Hypertension.
Plan: Continue carvedilol, sacubitril/valsartan, spironolactone. BMP. Follow up 3 months.
MDM: moderate (chronic illness, prescription drug management).""",
        "gold": {"diagnoses": [{"code": "I11.0"}, {"code": "I50.22"}], "first_listed": "I11.0",
                 "procedures": [{"code": "99214"}], "edit_flags_expected": []},
    },
    {
        "id": "case_007", "date_of_service": "2026-07-08",
        "note": """Established patient, 64F, Medicare, follow-up for hypertension and chronic kidney disease stage 3a (eGFR 52, stable).
BP 132/80 on losartan. No edema.
Assessment: Hypertension. Chronic kidney disease, stage 3a.
Plan: Continue losartan. Renal panel in 6 months. Avoid NSAIDs.
MDM: low (stable chronic illnesses).""",
        "gold": {"diagnoses": [{"code": "I12.9"}, {"code": "N18.31"}], "first_listed": "I12.9",
                 "procedures": [{"code": "99213"}], "edit_flags_expected": []},
    },
    {
        "id": "case_008", "date_of_service": "2026-03-25",
        "note": """Established patient, 31F, 3 days of dysuria and urinary frequency. No fever, no flank pain. Commercial insurance.
In-office urinalysis by automated dipstick reader, without microscopy: positive leukocyte esterase and nitrites.
Urine culture sent (outside lab). Culture result called back same day: >100,000 CFU/mL Escherichia coli.
Assessment: Urinary tract infection due to E. coli.
Plan: Nitrofurantoin 100 mg BID x 5 days.
MDM: low.""",
        "gold": {"diagnoses": [{"code": "N39.0"}, {"code": "B96.20"}], "first_listed": "N39.0",
                 "procedures": [{"code": "99213"}, {"code": "81003"}], "edit_flags_expected": []},
    },
    {
        "id": "case_009", "date_of_service": "2026-08-14",
        "note": """Established patient, 19M, inverted his right ankle playing basketball yesterday. Commercial insurance.
Exam: swelling and tenderness over the anterior talofibular ligament, able to bear weight with pain. No bony tenderness at posterior malleolar edges.
In-office x-ray of right ankle, 3 views, interpreted by me: no fracture.
Assessment: Sprain of the anterior talofibular ligament, right ankle, initial encounter.
Plan: RICE, ankle brace, NSAIDs, follow up 2 weeks.
MDM: low.""",
        "gold": {"diagnoses": [{"code": "S93.491A"}], "first_listed": "S93.491A",
                 "optional_dx": ["W09.8XXA", "Y93.67", "Y92.310", "X50.0XXA"],
                 "procedures": [{"code": "99213"}, {"code": "73610"}], "edit_flags_expected": []},
    },
    {
        "id": "case_010", "date_of_service": "2026-02-18",
        "note": """Established patient, 55F, 5 days of productive cough and fever to 100.8 F. Commercial insurance.
Lungs: scattered rhonchi right base. SpO2 97%.
Assessment: Cough and fever, probable community-acquired pneumonia.
Plan: Chest x-ray ordered at outside imaging center. Will call with results and decide on antibiotics.
MDM: low.""",
        "gold": {"diagnoses": [{"code": "R05.9"}, {"code": "R50.9"}], "first_listed": "R05.9",
                 "first_listed_alternates": ["R50.9"],
                 "procedures": [{"code": "99213"}], "edit_flags_expected": []},
    },
    {
        "id": "case_011", "date_of_service": "2026-09-09",
        "note": """Nurse visit, 70F, Medicare, monthly vitamin B12 injection for pernicious anemia per standing order.
Cyanocobalamin 1,000 mcg given intramuscularly, left deltoid, by RN under general supervision of the physician, who was in the office suite. No reaction.
No physician evaluation today.""",
        "gold": {"diagnoses": [{"code": "D51.0"}], "first_listed": "D51.0",
                 "procedures": [{"code": "96372"}, {"code": "J3420", "units": 1}], "edit_flags_expected": []},
    },
]

OUT.mkdir(parents=True, exist_ok=True)
for c in CASES:
    c["review_status"] = DRAFT
    (OUT / f"{c['id']}.json").write_text(json.dumps(c, indent=2), encoding="utf-8")
print(f"wrote {len(CASES)} cases to {OUT}")
