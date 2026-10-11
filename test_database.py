"""
Run with:  python -m unittest test_database -v
Uses a temporary database, so your real agritrial.db is never touched.
"""
import os
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

import db
import seed_sample_data
import sync_supabase
from protocols import STANDARD_TRAITS, TOMATO_TRIAL

SITE = TOMATO_TRIAL["sites"][0][0]


def good_record(**changes):
    """Plot 104 from the tomato sample sheet (a clean record)."""
    record = {
        "trial_code": "TOM-BIO-2026-02", "plot_number": 104, "date": "2026-06-15",
        "site": SITE, "treatment_group": "BioStim-A", "rep_number": 1,
        "height_cm": 52, "yield_value": 2.8, "chlorophyll_spad": 45,
        "disease_pct": 8, "root_mass_g": 145,
    }
    record.update(changes)
    return record


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        os.environ["AGRITRIAL_DB"] = self.path
        for name in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
            os.environ.pop(name, None)
        db.create_tables()
        db.register_trial(TOMATO_TRIAL)

    def tearDown(self):
        os.environ.pop("AGRITRIAL_DB", None)
        os.remove(self.path)

    # ---- validation: one test per problem seen on the real field sheet ----
    def test_clean_record_saves(self):
        result = db.save_record(good_record())
        self.assertTrue(result["saved"])
        self.assertEqual(result["readings"], 5)

    def test_impossible_date_rejected(self):             # plot 108: 31/6
        result = db.save_record(good_record(date="2026-06-31"))
        self.assertFalse(result["saved"])
        self.assertIn("not a real calendar date", result["errors"][0])

    def test_negative_yield_rejected(self):              # plot 111: -3.2
        self.assertFalse(db.save_record(good_record(yield_value=-3.2))["saved"])

    def test_missing_instrument_reading_allowed(self):   # plot 112: SPAD blank
        result = db.save_record(good_record(chlorophyll_spad=None))
        self.assertTrue(result["saved"])
        self.assertEqual(result["readings"], 4)

    def test_duplicate_replicate_rejected(self):         # plot 114: Rep 1 again
        self.assertTrue(db.save_record(good_record())["saved"])
        result = db.save_record(good_record(plot_number=114))
        self.assertFalse(result["saved"])
        self.assertIn("duplicate replicate", result["errors"][0])

    def test_rep_outside_plan_rejected(self):            # plot 113: Rep 4
        self.assertFalse(db.save_record(good_record(rep_number=4))["saved"])

    def test_unknown_treatment_rejected(self):
        self.assertFalse(db.save_record(good_record(treatment_group="BioStim A"))["saved"])

    def test_unknown_site_rejected(self):
        result = db.save_record(good_record(site="Greenfield Farm"))
        self.assertFalse(result["saved"])
        self.assertIn("not registered", result["errors"][0])

    def test_test_from_another_crop_rejected(self):
        result = db.save_record(good_record(oil_pct=33.2))
        self.assertFalse(result["saved"])
        self.assertIn("not a test of this trial", result["errors"][0])

    def test_blank_plot_rejected(self):
        blank = good_record(height_cm=None, yield_value=None, chlorophyll_spad=None,
                            disease_pct=None, root_mass_g=None)
        self.assertFalse(db.save_record(blank)["saved"])

    def test_old_plot_id_name_still_accepted(self):
        record = good_record()
        record["plot_id"] = record.pop("plot_number")
        self.assertTrue(db.save_record(record)["saved"])

    # ---- repeated readings (the "aggregated data" problem on slide 9) ----
    def test_same_plot_can_be_measured_again_later(self):
        db.save_record(good_record())
        later = db.save_record(good_record(date="2026-06-29", height_cm=70))
        self.assertTrue(later["saved"])
        records = db.get_records(treatment_group="BioStim-A")
        self.assertEqual([r["date"] for r in records], ["2026-06-15", "2026-06-29"])

    def test_same_reading_twice_rejected(self):
        db.save_record(good_record())
        result = db.save_record(good_record())
        self.assertFalse(result["saved"])
        self.assertIn("already been captured", result["errors"][0])

    def test_plot_cannot_change_treatment(self):
        db.save_record(good_record())
        result = db.save_record(good_record(treatment_group="Control", date="2026-06-29"))
        self.assertFalse(result["saved"])

    # ---- sample data ----
    def test_sample_data_loads(self):
        summary = seed_sample_data.seed()
        self.assertEqual(len(summary["tomato"]["saved"]), 10)
        self.assertEqual(sorted(p for p, _ in summary["tomato"]["rejected"]), [108, 111, 113, 114])
        self.assertEqual(len(summary["canola"]["saved"]), 6)
        self.assertEqual(summary["canola"]["rejected"], [])

    def test_seeding_twice_does_not_duplicate_trials(self):
        seed_sample_data.seed()
        seed_sample_data.seed()
        self.assertEqual(len(db.list_trials()), 2)

    def test_get_values_for_ci(self):
        seed_sample_data.seed()
        self.assertEqual(sorted(db.get_values("yield_value", "Control", crop="Tomato")), [1.9, 2.0, 2.1])

    def test_filter_by_treatment(self):
        seed_sample_data.seed()
        rows = db.get_records(trial_code="TOM-BIO-2026-02", treatment_group="BioStim-C")
        self.assertEqual([r["plot_number"] for r in rows], [110, 112])

    def test_get_values_rejects_unknown_measure(self):
        with self.assertRaises(ValueError):
            db.get_values("name; DROP TABLE trials", "Control")

    # ---- canola and calculated values ----
    def test_calculated_values_match_the_slide(self):
        seed_sample_data.seed()
        self.assertEqual(db.get_values("oil_yield", "Control", crop="Canola"), [758.95])   # slide: 759
        self.assertEqual(db.get_values("k_na_ratio", "Control", crop="Canola"), [3.92])    # slide: 3.92

    def test_calculated_values_are_not_stored(self):
        seed_sample_data.seed()
        conn = db.get_connection()
        names = {r[0] for r in conn.execute("SELECT trait_name FROM assessment_traits")}
        conn.close()
        self.assertNotIn("oil_yield", names)
        self.assertNotIn("k_na_ratio", names)

    def test_canola_record_has_all_columns(self):
        seed_sample_data.seed()
        record = db.get_records(crop="Canola", treatment_group="Humic acid")[0]
        self.assertEqual(record["yield_value"], 2589)
        self.assertEqual(record["prolin"], 1.98)
        self.assertEqual(record["oil_yield"], 921.68)     # 2589 x 35.6 / 100 (slide shows 922)

    # ---- a new crop needs no schema change ----
    def test_new_crop_needs_no_schema_change(self):
        lettuce = {
            "trial_code": "LET-TEST-01", "crop": "Lettuce", "planned_reps": 2,
            "sites": [("Test tunnel", None)],
            "treatments": {"Control": None, "Kelp": "Seaweed drench"},
            "traits": [t for t in STANDARD_TRAITS if t[0] in ("height_cm", "nitrate_mgl")],
        }
        db.register_trial(lettuce)
        result = db.save_record({"trial_code": "LET-TEST-01", "plot_number": 1, "date": "2026-10-01",
                                 "site": "Test tunnel", "treatment_group": "Kelp", "rep_number": 1,
                                 "height_cm": 12.5, "nitrate_mgl": 40})
        self.assertTrue(result["saved"])
        self.assertEqual(db.get_values("nitrate_mgl", "Kelp", crop="Lettuce"), [40])

    # ---- sync ----
    def test_sync_not_configured(self):
        seed_sample_data.seed()
        with patch.object(sync_supabase, "load_env_file"):
            result = sync_supabase.sync_to_supabase()
        self.assertEqual(result["status"], "not_configured")

    def test_sync_success_marks_readings(self):
        seed_sample_data.seed()
        total = len(db.get_unsynced_records())
        os.environ["SUPABASE_URL"] = "https://example.supabase.co"
        os.environ["SUPABASE_SERVICE_KEY"] = "test-key"
        fake = MagicMock()
        fake.__enter__.return_value.status = 201
        with patch.object(sync_supabase, "load_env_file"), \
             patch("sync_supabase.urllib.request.urlopen", return_value=fake):
            result = sync_supabase.sync_to_supabase()
        self.assertEqual(result, {"status": "ok", "synced": total, "pending": 0})
        self.assertEqual(db.get_unsynced_records(), [])
        self.assertEqual(total, 47 + 126)   # tomato 47 readings (blanks skipped) + canola 6 x 21

    def test_sync_offline_keeps_readings_pending(self):
        seed_sample_data.seed()
        total = len(db.get_unsynced_records())
        os.environ["SUPABASE_URL"] = "https://example.supabase.co"
        os.environ["SUPABASE_SERVICE_KEY"] = "test-key"
        with patch.object(sync_supabase, "load_env_file"), \
             patch("sync_supabase.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("no internet")):
            result = sync_supabase.sync_to_supabase()
        self.assertEqual(result["status"], "offline")
        self.assertEqual(len(db.get_unsynced_records()), total)

    def test_payload_has_no_local_id(self):
        seed_sample_data.seed()
        payload = sync_supabase.build_payload(db.get_unsynced_records())
        self.assertNotIn("data_id", payload[0])
        self.assertIn("trait_name", payload[0])


if __name__ == "__main__":
    unittest.main()
