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


def good_record(**changes):
    """Plot 104 from the sample sheet (a clean record)."""
    record = {
        "trial_code": "TOM-BIO-2026-02", "plot_id": 104, "date": "2026-06-15",
        "site": "Greenfield Research Farm, Block 4", "crop": "Tomato", "variety": "Rutgers",
        "treatment_group": "BioStim-A", "rep_number": 1,
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

    def tearDown(self):
        os.environ.pop("AGRITRIAL_DB", None)
        os.remove(self.path)

    # ---- validation, one test per problem seen on the real field sheet ----
    def test_clean_record_saves(self):
        result = db.save_record(good_record())
        self.assertTrue(result["saved"])
        self.assertEqual(result["record_id"], "TOM-BIO-2026-02-104")

    def test_impossible_date_rejected(self):             # plot 108: 31/6
        result = db.save_record(good_record(date="2026-06-31"))
        self.assertFalse(result["saved"])
        self.assertIn("not a real calendar date", result["errors"][0])

    def test_negative_yield_rejected(self):              # plot 111: -3.2
        result = db.save_record(good_record(yield_value=-3.2))
        self.assertFalse(result["saved"])

    def test_missing_instrument_reading_allowed(self):   # plot 112: SPAD blank
        result = db.save_record(good_record(chlorophyll_spad=None))
        self.assertTrue(result["saved"])

    def test_duplicate_replicate_rejected(self):         # plot 114: Rep 1 again
        self.assertTrue(db.save_record(good_record())["saved"])
        result = db.save_record(good_record(plot_id=114))
        self.assertFalse(result["saved"])
        self.assertIn("duplicate replicate", result["errors"][0])

    def test_rep_outside_plan_rejected(self):            # plot 113: Rep 4
        result = db.save_record(good_record(rep_number=4))
        self.assertFalse(result["saved"])

    def test_unknown_treatment_rejected(self):
        result = db.save_record(good_record(treatment_group="BioStim A"))
        self.assertFalse(result["saved"])

    def test_blank_plot_rejected(self):
        blank = good_record(height_cm=None, yield_value=None, chlorophyll_spad=None,
                            disease_pct=None, root_mass_g=None)
        self.assertFalse(db.save_record(blank)["saved"])

    # ---- sample data ----
    def test_sample_sheet_loads_ten_of_fourteen(self):
        summary = seed_sample_data.seed()
        self.assertEqual(len(summary["saved"]), 10)
        self.assertEqual(sorted(plot for plot, _ in summary["rejected"]), [108, 111, 113, 114])

    def test_get_values_for_ci(self):
        seed_sample_data.seed()
        self.assertEqual(sorted(db.get_values("yield_value", "Control")), [1.9, 2.0, 2.1])

    def test_get_values_rejects_unknown_measure(self):
        with self.assertRaises(ValueError):
            db.get_values("name; DROP TABLE trial_context", "Control")

    def test_filter_by_treatment(self):
        seed_sample_data.seed()
        rows = db.get_records(treatment_group="BioStim-C")
        self.assertEqual([r["plot_id"] for r in rows], [110, 112])

    # ---- sync ----
    def test_sync_not_configured(self):
        seed_sample_data.seed()
        with patch.object(sync_supabase, "load_env_file"):
            result = sync_supabase.sync_to_supabase()
        self.assertEqual(result["status"], "not_configured")

    def test_sync_success_marks_records(self):
        seed_sample_data.seed()
        os.environ["SUPABASE_URL"] = "https://example.supabase.co"
        os.environ["SUPABASE_SERVICE_KEY"] = "test-key"
        fake = MagicMock()
        fake.__enter__.return_value.status = 201
        with patch.object(sync_supabase, "load_env_file"), \
             patch("sync_supabase.urllib.request.urlopen", return_value=fake):
            result = sync_supabase.sync_to_supabase()
        self.assertEqual(result, {"status": "ok", "synced": 10, "pending": 0})
        self.assertEqual(db.get_unsynced_records(), [])

    def test_sync_offline_keeps_records_pending(self):
        seed_sample_data.seed()
        os.environ["SUPABASE_URL"] = "https://example.supabase.co"
        os.environ["SUPABASE_SERVICE_KEY"] = "test-key"
        with patch.object(sync_supabase, "load_env_file"), \
             patch("sync_supabase.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("no internet")):
            result = sync_supabase.sync_to_supabase()
        self.assertEqual(result["status"], "offline")
        self.assertEqual(len(db.get_unsynced_records()), 10)

    def test_payload_has_no_local_flag(self):
        seed_sample_data.seed()
        payload = sync_supabase.build_payload(db.get_unsynced_records())
        self.assertNotIn("synced", payload[0])


if __name__ == "__main__":
    unittest.main()
