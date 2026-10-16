
STANDARD_TRAITS = [
    ("height_cm",        "Plant height",       "plant",       "cm",      0, 400,  None),
    ("leaf_count",       "Leaf count",         "plant",       "count",   0, 1000, None),
    ("fresh_weight_g",   "Fresh weight",       "plant",       "g",       0, None, None),
    ("dry_weight_g",     "Dry weight",         "plant",       "g",       0, None, None),
    ("chlorophyll_spad", "Chlorophyll (SPAD)", "plant",       "SPAD",    0, 100,  None),
    ("root_mass_g",      "Root mass",          "plant",       "g",       0, None, None),
    ("yield_value",      "Yield",              "plant",       "kg/plot", 0, None, None),
    ("disease_pct",      "Disease",            "plant",       "%",       0, 100,  None),
    ("ph",               "pH",                 "environment", None,      0, 14,   None),
    ("ec_mscm",          "EC",                 "environment", "mS/cm",   0, None, None),
    ("dissolved_o2",     "Dissolved O2",       "environment", "mg/L",    0, None, None),
    ("temp_c",           "Temperature",        "environment", "C",     -10, 60,   None),
    ("humidity_pct",     "Humidity",           "environment", "%",       0, 100,  None),
    ("nitrate_mgl",      "Nitrate",            "environment", "mg/L",    0, None, None),
    ("phosphate_mgl",    "Phosphate",          "environment", "mg/L",    0, None, None),
]


TOMATO_TRIAL = {
    "trial_code": "TOM-BIO-2026-02",
    "trial_name": "Tomato biostimulant trial",
    "crop": "Tomato",
    "variety": "Rutgers",
    "objective": "Compare three biostimulants against an untreated control (sample project data).",
    "planned_reps": 3,
    "sites": [("Greenfield Research Farm, Block 4", None)],
    "treatments": {
        "Control": "Untreated",
        "BioStim-A": "Seaweed extract",
        "BioStim-B": "Humic/fulvic acids",
        "BioStim-C": "Microbial consortium",
    },
    "traits": STANDARD_TRAITS,
}


CANOLA_TRAITS = [
    ("yield_value",          "Yield",     "plant", None, 0, None, None),
    ("bio_yield",            "Bio Yield", "plant", None, 0, None, None),
    ("pods_per_plant",       "pod/plant", "plant", None, 0, None, None),
    ("seeds_per_pod",        "seed/pod",  "plant", None, 0, None, None),
    ("thousand_seed_weight", "1000sw",    "plant", None, 0, None, None),
    ("oil_pct",              "Oil%",      "plant", "%",  0, 100,  None),
    ("n",                    "N",         "plant", None, 0, None, None),
    ("p",                    "P",         "plant", None, 0, None, None),
    ("k",                    "K",         "plant", None, 0, None, None),
    ("na",                   "Na",        "plant", None, 0, None, None),
    ("ca",                   "Ca",        "plant", None, 0, None, None),
    ("mg",                   "Mg",        "plant", None, 0, None, None),
    ("fe",                   "Fe",        "plant", None, 0, None, None),
    ("mn",                   "Mn",        "plant", None, 0, None, None),
    ("zn",                   "Zn",        "plant", None, 0, None, None),
    ("cu",                   "Cu",        "plant", None, 0, None, None),
    ("chl_a",                "Chl a",     "plant", None, 0, None, None),
    ("chl_b",                "Chl b",     "plant", None, 0, None, None),
    ("rwc",                  "RWC",       "plant", "%",  0, 100,  None),
    ("ionic_l",              "Ionic L",   "plant", None, 0, None, None),
    ("prolin",               "Prolin",    "plant", None, 0, None, None),
]

CANOLA_TRIAL = {
    "trial_code": "CANOLA-DEMO-01",              
    "trial_name": "Canola biostimulant trial (Week 20 slide data)",
    "crop": "Canola",
    "variety": None,
    "objective": "Compare biostimulant treatments on canola yield, oil and nutrient content.",
    "planned_reps": 1,
    "sites": [("Canola demo site (to be confirmed)", None)],
    "treatments": {
        "Control": None,
        "Amino acid": None,
        "Seaweed Extract": None,
        "Humic acid": None,
        "Fulvic acid": None,    
        "Combined": None,
    },
    "traits": CANOLA_TRAITS,
}


DERIVED_TRAITS = {
    "CANOLA-DEMO-01": {
        "oil_yield": lambda r: _safe(lambda: r["yield_value"] * r["oil_pct"] / 100),
        "k_na_ratio": lambda r: _safe(lambda: r["k"] / r["na"]),
    }
}


def _safe(calculation):
    """Return the result, or None if an input is missing or zero."""
    try:
        return round(calculation(), 2)
    except (KeyError, TypeError, ZeroDivisionError):
        return None
