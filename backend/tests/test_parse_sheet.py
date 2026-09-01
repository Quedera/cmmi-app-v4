"""Regression coverage for DEF-008.

The XLS importer (import_test_data.py) used to detect area-header rows
only by the `"Area - "` prefix in col0. That worked for 27 of 28
discipline sheets in data/ITIL_CMMI_Assessment_v0.1.xls — but Strategy
Generation uses bare category labels in col0 ("People", "Supporting
Technology", "Strategy in the lifecycle", "Sourcing Strategy",
"Governance and compliance", "Business Alignment") with the area number
in col1 and no "Area - " prefix. The v3 / v4 importer ignored those
rows, so all 26 Strategy Generation questions landed in the live DB
with `area_name = NULL` and `area_number = NULL` (the symptom Tyto
reported in DEF-008).

The same bare-label pattern also appears mid-sheet in Demand Management,
Service Portfolio Management, Service Catalogue Management, and Common
Operation Mngt Activitie. Those questions were previously silently
assigned the previous "Area - " label because the bare-label area
headers were no-ops. The DEF-008 fix detects both formats and rejects
footer summary rows (which have populated col2/col3/col4) so they
don't get misread as area headers.

Run from the repo root:
    cd /home/nortclaw/workspace/cmmi-app
    python -m unittest backend.tests.test_parse_sheet -v
    # or:  python backend/tests/test_parse_sheet.py
"""

import os
import unittest
import xlrd

import import_test_data as itd


# Locate the canonical XLS relative to this test file so the test is
# robust to CWD.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
XLS_PATH = os.path.join(REPO_ROOT, "data", "ITIL_CMMI_Assessment_v0.1.xls")


class TestParseSheetDEF008(unittest.TestCase):
    """Verify the DEF-008 fix: area-header detection covers both workbook
    formats ("Area - " prefix AND bare-label) without misreading footer
    summary rows.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(XLS_PATH):
            raise unittest.SkipTest(f"canonical XLS not found at {XLS_PATH}")
        cls.wb = xlrd.open_workbook(XLS_PATH)

    # --- Strategy Generation: the primary DEF-008 case --------------------

    def test_strategy_generation_has_no_null_areas(self):
        """All 26 questions must have a non-NULL area_name + area_number.

        Before the fix, all 26 questions had area=None and area_number=None.
        """
        s = self.wb.sheet_by_name("Strategy Generation")
        questions, _ = itd.parse_sheet(s, sheet_name="Strategy Generation")
        self.assertEqual(len(questions), 26)
        for q in questions:
            self.assertIsNotNone(q["area"],
                f"area must be set; got None for question: {q['question'][:50]!r}")
            self.assertIsNotNone(q["area_number"],
                f"area_number must be set; got None for question: {q['question'][:50]!r}")
            self.assertIsInstance(q["area_number"], int)
            self.assertGreaterEqual(q["area_number"], 1)
            self.assertLessEqual(q["area_number"], 26)

    def test_strategy_generation_covers_all_six_categories(self):
        """The 26 questions span 6 distinct category labels.

        These are the bare-label area categories in Strategy Generation:
            People (areas 1-5),
            Supporting Technology (areas 6-9),
            Strategy in the lifecycle (areas 10-13),
            Sourcing Strategy (areas 14-17),
            Governance and compliance (areas 18-22),
            Business Alignment (areas 23-26).
        """
        s = self.wb.sheet_by_name("Strategy Generation")
        questions, _ = itd.parse_sheet(s, sheet_name="Strategy Generation")
        distinct_categories = {q["area"] for q in questions}
        self.assertEqual(len(distinct_categories), 6)
        # Every area_name must be prefixed "Area - " so the stored
        # convention matches every other sheet in the workbook.
        for cat in distinct_categories:
            self.assertTrue(
                cat.startswith("Area - "),
                f"area_name should be normalised with 'Area - ' prefix; got {cat!r}",
            )

    def test_strategy_generation_area_numbers_are_contiguous_1_to_26(self):
        """Areas 1..26 must each have exactly one question."""
        s = self.wb.sheet_by_name("Strategy Generation")
        questions, _ = itd.parse_sheet(s, sheet_name="Strategy Generation")
        by_area = {}
        for q in questions:
            by_area.setdefault(q["area_number"], []).append(q)
        self.assertEqual(sorted(by_area.keys()), list(range(1, 27)))
        for n, qs in by_area.items():
            self.assertEqual(len(qs), 1, f"area {n} should have exactly 1 question")

    # --- Other affected sheets: bare-label mid-sheet area headers ---------

    def test_demand_management_areas_9_to_14_get_correct_labels(self):
        """Demand Management areas 9..11 should be "Patterns of Business
        Activity" and areas 12..14 should be "Service Level Packages".

        Before the fix these questions were silently labelled with the
        previous "Area - Basic Concepts" (area 8).
        """
        s = self.wb.sheet_by_name("Demand Management")
        questions, _ = itd.parse_sheet(s, sheet_name="Demand Management")
        by_area = {q["area_number"]: q["area"] for q in questions}
        for n in (9, 10, 11):
            self.assertEqual(by_area[n], "Area - Patterns of Business Activity",
                f"DM area {n} expected Patterns of Business Activity; got {by_area[n]!r}")
        for n in (12, 13, 14):
            self.assertEqual(by_area[n], "Area - Service Level Packages",
                f"DM area {n} expected Service Level Packages; got {by_area[n]!r}")

    def test_service_portfolio_management_areas_11_to_22_get_correct_labels(self):
        """SPM areas 11..15 = Define, 16..17 = Analyse, 18..19 = Approve,
        20..22 = Charter.

        Before the fix these were all labelled "Area - Basic Concepts".
        """
        s = self.wb.sheet_by_name("Service Portfolio Management")
        questions, _ = itd.parse_sheet(s, sheet_name="Service Portfolio Management")
        by_area = {q["area_number"]: q["area"] for q in questions}
        expected = {
            11: "Area - Define", 12: "Area - Define", 13: "Area - Define",
            14: "Area - Define", 15: "Area - Define",
            16: "Area - Analyse", 17: "Area - Analyse",
            18: "Area - Approve", 19: "Area - Approve",
            20: "Area - Charter", 21: "Area - Charter", 22: "Area - Charter",
        }
        for n, want in expected.items():
            self.assertEqual(by_area[n], want,
                f"SPM area {n} expected {want!r}; got {by_area[n]!r}")

    def test_service_catalogue_management_areas_11_to_24_get_correct_labels(self):
        """SCM areas 11..15 = Process Inputs, 16..20 = Process Activities,
        21..24 = Process Outputs.

        Before the fix these were all labelled "Area - Basic Concepts".
        """
        s = self.wb.sheet_by_name("Service Catalogue Management")
        questions, _ = itd.parse_sheet(s, sheet_name="Service Catalogue Management")
        by_area = {q["area_number"]: q["area"] for q in questions}
        expected = {
            11: "Area - Process Inputs", 12: "Area - Process Inputs",
            13: "Area - Process Inputs", 14: "Area - Process Inputs",
            15: "Area - Process Inputs",
            16: "Area - Process Activities", 17: "Area - Process Activities",
            18: "Area - Process Activities", 19: "Area - Process Activities",
            20: "Area - Process Activities",
            21: "Area - Process Outputs", 22: "Area - Process Outputs",
            23: "Area - Process Outputs", 24: "Area - Process Outputs",
        }
        for n, want in expected.items():
            self.assertEqual(by_area[n], want,
                f"SCM area {n} expected {want!r}; got {by_area[n]!r}")

    # --- Footer summary rows: must NOT be misread as area headers -----------

    def test_footer_summary_rows_are_not_misread_as_area_headers(self):
        """Footer summary rows (col0=label, col1=count, col2=max_score,
        col3=scores, col4=pct) look superficially like bare-label area
        headers but populate col2..4 — the new detector must skip them.

        Concretely: parsing must yield exactly the question count from the
        Summaries sheet for that discipline, NOT the question count + 6/7
        (which would happen if each footer row became a spurious 1-question
        area).
        """
        # From the canonical workbook's Summaries sheet, the expected
        # question counts. We verify the parse matches these.
        expected_counts = {
            "Strategy Generation": 26,
            "Demand Management": 14,
            "Service Portfolio Management": 22,
            "Service Catalogue Management": 24,
            "Service Level Management": 28,
            "Capacity Management": 27,
            "Availability Management": 23,
            "Service Continuity Management": 20,
            "Information Security Management": 19,
            "Supplier Management": 35,
            "Change Management": 24,
            "Service Asset _ Config_ Mngt_": 44,
            "Service Validation _ Testing": 19,
            "Event Management": 13,
            "Service Desk": 18,
            "Incident Management": 22,
            "Request Fulfillment": 18,
            "Problem Management": 17,
            "Access Management": 18,
            "Service Measurement": 10,
            "Service Reporting": 14,
            "Service Improvement": 11,
        }
        for sheet_name, want in expected_counts.items():
            s = self.wb.sheet_by_name(sheet_name)
            questions, _ = itd.parse_sheet(s, sheet_name=sheet_name)
            self.assertEqual(
                len(questions), want,
                f"{sheet_name}: expected {want} questions, got {len(questions)}"
            )

    # --- "Area - " prefix path still works (no regression on other sheets)

    def test_area_prefix_path_still_works_on_every_other_sheet(self):
        """For every discipline sheet (excluding Strategy Generation), the
        "Area - " prefix path must still produce a non-NULL area_name on
        every parsed question. Guards against the DEF-008 fix accidentally
        breaking the existing format.
        """
        for name in self.wb.sheet_names():
            if name in ("Title Sheet", "Exec Dashboard", "Summaries"):
                continue
            s = self.wb.sheet_by_name(name)
            questions, _ = itd.parse_sheet(s, sheet_name=name)
            for q in questions:
                self.assertIsNotNone(
                    q["area"],
                    f"{name}: area should be set after DEF-008 fix; got None for "
                    f"question: {q['question'][:50]!r}",
                )
                # Most sheets use "Area - " prefix; SG uses synthesised
                # "Area - <bare label>". Both formats start with "Area - ".
                self.assertTrue(
                    q["area"].startswith("Area - "),
                    f"{name}: area should be normalised to 'Area - ...'; "
                    f"got {q['area']!r}",
                )

    # --- DEF-009: empty-text option rows are preserved (XLS authors
    #     sometimes leave col0 blank for maturity levels with no
    #     specific descriptor — most common in Evaluation). --------------

    def test_evaluation_questions_all_have_six_options(self):
        """Every Evaluation question must have exactly 6 options after the
        DEF-009 parser fix. Before the fix, Evaluation had 16 questions
        with 2-4 options because the parser dropped empty-text option rows.
        """
        s = self.wb.sheet_by_name("Evaluation")
        questions, _ = itd.parse_sheet(s, sheet_name="Evaluation")
        self.assertEqual(len(questions), 16)
        scores_seen = set()
        for q in questions:
            self.assertEqual(len(q["options"]), 6,
                f"Evaluation Q{q['area_number']} should have 6 options, "
                f"got {len(q['options'])}: {[o['score'] for o in q['options']]}")
            for o in q["options"]:
                self.assertIn(o["score"], range(6),
                    f"option score out of range: {o['score']}")
                self.assertTrue(o.get("text"),
                    f"option text must not be empty/missing: {o}")
            qs = sorted(o["score"] for o in q["options"])
            self.assertEqual(qs, [0, 1, 2, 3, 4, 5],
                f"Evaluation Q{q['area_number']} scores must be 0-5 contiguous; got {qs}")
            # Per-question score uniqueness (DEF-004 guard)
            self.assertEqual(len(qs), len(set(qs)),
                f"Evaluation Q{q['area_number']} has duplicate scores: {qs}")
            scores_seen.update(qs)
        # Across the whole Evaluation sheet, scores 0-5 must all be present
        self.assertEqual(scores_seen, set(range(6)))

    def test_evaluation_empty_descriptor_options_use_placeholder(self):
        """Empty-text option rows from the XLS must surface as
        "(no descriptor)" so the question still has a complete 0-5 scale
        without losing the row entirely.
        """
        s = self.wb.sheet_by_name("Evaluation")
        questions, _ = itd.parse_sheet(s, sheet_name="Evaluation")
        # At least one option across all Evaluation questions should have
        # the placeholder text (since the XLS uses empty rows for some
        # maturity levels in nearly every question).
        placeholders = sum(
            1 for q in questions for o in q["options"] if o["text"] == "(no descriptor)"
        )
        self.assertGreater(placeholders, 0,
            "Expected at least one '(no descriptor)' placeholder across Evaluation "
            "questions; if this fails, the XLS authors may have filled in those "
            "descriptors and the placeholder path is no longer needed.")

    def test_no_question_in_any_sheet_has_wrong_option_count(self):
        """Sanity: after DEF-009, every question in every discipline sheet
        has exactly 6 options with scores 0-5 contiguous. Guards against
        any future XLS variant re-introducing the empty-text drop.
        """
        bad = []
        for name in self.wb.sheet_names():
            if name in ("Title Sheet", "Exec Dashboard", "Summaries"):
                continue
            s = self.wb.sheet_by_name(name)
            questions, _ = itd.parse_sheet(s, sheet_name=name)
            for q in questions:
                if len(q["options"]) != 6:
                    bad.append((name, q["area_number"], len(q["options"])))
        self.assertEqual(bad, [],
            f"questions with != 6 options after DEF-009: {bad}")


class TestParseSheetDEF009KMQuestions(unittest.TestCase):
    """Verify the DEF-009 fix: KM sheet's singular 'Comment' marker
    rows are recognised as question-prompt markers, restoring
    Q12-Q19 to the parsed output.

    Before the fix, the parser's question-prompt marker check matched
    only the plural 'Comments'. The KM sheet uses singular 'Comment'
    for Q12-Q19 (one XLS author, intentional), so all 8 questions
    were silently dropped — KM parsed to 11 questions instead of 19.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(XLS_PATH):
            raise unittest.SkipTest(f"canonical XLS not found at {XLS_PATH}")
        cls.wb = xlrd.open_workbook(XLS_PATH)

    def test_km_has_nineteen_questions(self):
        """KM must parse to 19 questions (was 11 before the fix)."""
        s = self.wb.sheet_by_name("Knowledge Management")
        questions, _ = itd.parse_sheet(s, sheet_name="Knowledge Management")
        self.assertEqual(len(questions), 19)

    def test_km_area_numbers_are_contiguous_1_to_19(self):
        """Area numbers 1..19 must each have exactly one question."""
        s = self.wb.sheet_by_name("Knowledge Management")
        questions, _ = itd.parse_sheet(s, sheet_name="Knowledge Management")
        by_area = {}
        for q in questions:
            by_area.setdefault(q["area_number"], []).append(q)
        self.assertEqual(sorted(by_area.keys()), list(range(1, 20)))
        for n, qs in by_area.items():
            self.assertEqual(len(qs), 1, f"KM area {n} should have exactly 1 question")

    def test_km_q12_through_q19_have_six_options(self):
        """The newly-restored Q12-Q19 must each have 6 options with
        scores 0-5 contiguous. Guards against the singular-Comment
        parser path silently mishandling option rows."""
        s = self.wb.sheet_by_name("Knowledge Management")
        questions, _ = itd.parse_sheet(s, sheet_name="Knowledge Management")
        for q in questions:
            self.assertEqual(len(q["options"]), 6,
                f"KM Q{q['area_number']} should have 6 options; "
                f"got {len(q['options'])}")
            scores = sorted(o["score"] for o in q["options"])
            self.assertEqual(scores, [0, 1, 2, 3, 4, 5],
                f"KM Q{q['area_number']} scores must be 0-5 contiguous; got {scores}")

    def test_km_q12_through_q15_in_data_and_information_management(self):
        """Q12-Q15 must be in 'Area - Data and Information Management'."""
        s = self.wb.sheet_by_name("Knowledge Management")
        questions, _ = itd.parse_sheet(s, sheet_name="Knowledge Management")
        by_area_num = {q["area_number"]: q["area"] for q in questions}
        for n in (12, 13, 14, 15):
            self.assertEqual(by_area_num[n], "Area - Data and Information Management",
                f"KM Q{n} expected Data and Information Management; got {by_area_num[n]!r}")

    def test_km_q16_in_purpose_goal_and_objective(self):
        """Q16 must be in 'Area - Purpose, Goal and Objective'."""
        s = self.wb.sheet_by_name("Knowledge Management")
        questions, _ = itd.parse_sheet(s, sheet_name="Knowledge Management")
        by_area_num = {q["area_number"]: q["area"] for q in questions}
        self.assertEqual(by_area_num[16], "Area - Purpose, Goal and Objective",
            f"KM Q16 expected Purpose, Goal and Objective; got {by_area_num[16]!r}")

    def test_km_q17_through_q19_in_kpi_area(self):
        """Q17-Q19 must be in 'Area - Key performance indicators and metrics'."""
        s = self.wb.sheet_by_name("Knowledge Management")
        questions, _ = itd.parse_sheet(s, sheet_name="Knowledge Management")
        by_area_num = {q["area_number"]: q["area"] for q in questions}
        for n in (17, 18, 19):
            self.assertEqual(by_area_num[n], "Area - Key performance indicators and metrics",
                f"KM Q{n} expected Key performance indicators and metrics; got {by_area_num[n]!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)