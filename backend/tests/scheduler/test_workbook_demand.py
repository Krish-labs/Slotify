import openpyxl
import pytest

from app.scheduler.workbook_demand import parse_workbook_demand
from app.services.load_source_service import WorkbookParseError, parse_source_workbook

SOURCE = "../data/raw/Load Distribution.xlsx"
REFERENCE = "../data/raw/TT Faculty_16_8_2026.xlsx"


def test_real_semester_i_workbook_is_parsed_without_reference_entries():
    parsed = parse_workbook_demand(SOURCE, "2026-27", 1, REFERENCE)

    assert parsed.semester == "Semester I • 2026-27"
    assert parsed.rows_read == 93
    assert len(parsed.demands) == 121
    assert parsed.source_hours == 424
    assert parsed.required_slots == 185
    assert parsed.unrepresented_hours == 54
    assert parsed.excluded_rows


def test_real_semester_ii_workbook_remains_separate():
    parsed = parse_workbook_demand(SOURCE, "2025-26", 2, REFERENCE)

    assert parsed.semester == "Semester II • 2025-26"
    assert parsed.rows_read == 81
    assert len(parsed.demands) == 101
    assert parsed.source_hours == 317
    assert parsed.required_slots == 132
    assert parsed.unrepresented_hours == 53


def test_reference_workbook_is_not_required_for_demand_parsing():
    parsed = parse_workbook_demand(SOURCE, "2026-27", 1, "/does/not/get/opened.xlsx")

    assert len(parsed.demands) == 121


def test_reference_timing_width_preserves_every_source_hour():
    parsed = parse_workbook_demand(SOURCE, "2026-27", 1, REFERENCE, slot_hours=1)

    assert parsed.source_hours == 424
    assert parsed.required_slots == 424
    assert parsed.unrepresented_hours == 0


def test_source_hours_reconcile_with_scheduled_slots_and_remainders():
    """Demand reconciliation: no source hour is rounded away or invented.

    With the default two-hour grid every source hour is either inside a
    scheduled slot or reported as an unrepresented one-hour remainder.
    """
    parsed = parse_workbook_demand(SOURCE, "2026-27", 1, REFERENCE)

    assert parsed.source_hours == parsed.required_slots * 2 + parsed.unrepresented_hours
    assert parsed.source_hours == 424
    assert all(d.unrepresented_hours in (0, 1) for d in parsed.demands)
    assert all(
        d.required_slots * 2 + d.unrepresented_hours == d.source_hours for d in parsed.demands
    )


def test_source_parser_reports_missing_source_sheet(tmp_path):
    path = tmp_path / "bad.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.title = "Other"
    workbook.save(path)

    with pytest.raises(WorkbookParseError) as error:
        parse_source_workbook(path)

    assert error.value.sheet is None
    assert error.value.field == "sheet_name"
    assert "Sheet1" in str(error.value)


def test_zero_load_rows_are_tracked_not_silently_dropped():
    """Rows with valid class/subject/faculty but zero workload are tracked.

    The real workbook contains rows 54, 55, and 98 (Semester I) that have
    class/subject information but all workload components are blank, dash,
    or zero. These must not be silently discarded.
    """
    parsed = parse_workbook_demand(SOURCE, "2026-27", 1, REFERENCE, slot_hours=1)

    zero_load_row_numbers = {z.source_row_number for z in parsed.zero_load_rows}
    assert 54 in zero_load_row_numbers, "Row 54 (TY 1&2, KPIT) should be tracked"
    assert 55 in zero_load_row_numbers, "Row 55 (TY, Elective) should be tracked"
    assert 98 in zero_load_row_numbers, "Row 98 (FY, Engineering Exploration Lab-1) should be tracked"

    # Verify the tracked data preserves source context
    row_54 = next(z for z in parsed.zero_load_rows if z.source_row_number == 54)
    assert row_54.faculty_name == "Mr. Anup G. Dakre"
    assert row_54.class_name == "TY 1& 2"
    assert row_54.subject_name == "KPIT: Embedded System Honors Course"
    assert row_54.theory is None
    assert row_54.practical == "0"
    assert row_54.tutorial == "-"
    assert row_54.project_stage is None
    dispositions = {d.source_row_number: d for d in parsed.row_dispositions}
    for row_number in (54, 55, 98):
        assert dispositions[row_number].disposition == "zero_load_review_required"
        assert "review" in dispositions[row_number].reason


def test_zero_load_rows_include_legitimate_bookkeeping_row():
    """Row 53 (BE2, Modernised IOT) has total_load=0 and is legitimate bookkeeping.

    This row has an explicit total_load of '0' and all components zero.
    It is tracked alongside genuinely incomplete rows; the distinction is
    made during human review, not by the parser.
    """
    parsed = parse_workbook_demand(SOURCE, "2026-27", 1, REFERENCE, slot_hours=1)

    zero_load_row_numbers = {z.source_row_number for z in parsed.zero_load_rows}
    assert 53 in zero_load_row_numbers, "Row 53 (BE2, Modernised IOT) should be tracked"

    row_53 = next(z for z in parsed.zero_load_rows if z.source_row_number == 53)
    assert row_53.total_load == "0"
    assert row_53.theory == "0"
    assert row_53.practical == "0"
    assert row_53.tutorial == "-"
    assert row_53.project_stage == "0"


def test_has_unreviewed_zero_load_flag_is_true_when_rows_exist():
    """The readiness flag correctly reports unreviewed zero-load rows."""
    parsed = parse_workbook_demand(SOURCE, "2026-27", 1, REFERENCE, slot_hours=1)

    assert parsed.has_unreviewed_zero_load is True
    assert len(parsed.zero_load_rows) == 4  # rows 53, 54, 55, 98


def test_ready_flag_is_false_when_zero_load_rows_exist():
    """The ready property (used by the API) is False when zero-load rows exist.

    This prevents the workbook-readiness endpoint from reporting 'ready: true'
    while in-scope source rows remain unreviewed.
    """
    parsed = parse_workbook_demand(SOURCE, "2026-27", 1, REFERENCE, slot_hours=1)

    # The API readiness check uses: bool(demands) and not invalid_rows and not has_unreviewed_zero_load
    api_ready = bool(parsed.demands) and not parsed.invalid_rows and not parsed.has_unreviewed_zero_load
    assert api_ready is False, "Readiness should be False due to unreviewed zero-load rows"


def test_approved_exclusion_rows_are_not_zero_load():
    """M.Tech rows are excluded, not tracked as zero-load."""
    parsed = parse_workbook_demand(SOURCE, "2026-27", 1, REFERENCE, slot_hours=1)

    # M.Tech rows should be in excluded_rows, not zero_load_rows
    excluded_class_names = [e.split(": ")[1].split(" is")[0] for e in parsed.excluded_rows]
    zero_load_class_names = [z.class_name for z in parsed.zero_load_rows]

    for excluded in excluded_class_names:
        assert excluded not in zero_load_class_names, f"{excluded} should be excluded, not zero-load"


def test_invalid_rows_are_distinct_from_zero_load():
    """Rows missing faculty/class/subject are invalid, not zero-load."""
    parsed = parse_workbook_demand(SOURCE, "2026-27", 1, REFERENCE, slot_hours=1)

    # In the current workbook there are no invalid rows for Semester I,
    # but the categories must remain distinct
    invalid_row_numbers = set()
    for inv in parsed.invalid_rows:
        # Extract row number from "Source row N: ..."
        import re
        m = re.search(r"Source row (\d+):", inv)
        if m:
            invalid_row_numbers.add(int(m.group(1)))

    zero_load_row_numbers = {z.source_row_number for z in parsed.zero_load_rows}
    assert invalid_row_numbers.isdisjoint(zero_load_row_numbers), "Invalid and zero-load rows must be disjoint"


def _source_row(number, *, class_name="FY", subject="Subject", faculty="Faculty", theory=None):
    return {
        "source_row_number": number,
        "source_semester": "Semester I • 2026-27",
        "class_name": class_name,
        "subject_name": subject,
        "faculty_name": faculty,
        "theory": theory,
        "practical": None,
        "tutorial": None,
        "project_stage": None,
        "total_load": None,
    }


def test_parser_assigns_explicit_dispositions_for_zero_excluded_and_invalid_rows(
    monkeypatch, tmp_path
):
    import app.scheduler.workbook_demand as parser

    monkeypatch.setattr(
        parser,
        "parse_source_workbook",
        lambda _path: [
            _source_row(10, theory="0"),
            _source_row(11, class_name="M.Tech CSE", theory="-"),
            _source_row(12, theory="-1"),
        ],
    )
    parsed = parser.parse_workbook_demand(tmp_path / "source.xlsx", "2026-27", 1)

    by_row = {d.source_row_number: d for d in parsed.row_dispositions}
    assert by_row[10].disposition == "zero_load_review_required"
    assert by_row[11].disposition == "approved_exclusion"
    assert by_row[12].disposition == "invalid_source_row"
    assert parsed.invalid_rows and "Source row 12" in parsed.invalid_rows[0]
    assert parsed.has_unreviewed_zero_load


def test_positive_workload_is_explicitly_a_demand(monkeypatch, tmp_path):
    import app.scheduler.workbook_demand as parser

    monkeypatch.setattr(parser, "parse_source_workbook", lambda _path: [_source_row(7, theory="2")])
    parsed = parser.parse_workbook_demand(tmp_path / "source.xlsx", "2026-27", 1)

    assert parsed.row_dispositions == (
        parser.SourceRowDisposition(7, "scheduled_demand", "Teaching workload represented as demand"),
    )


def test_unreviewed_zero_load_prevents_plan_from_being_complete(monkeypatch, tmp_path):
    import app.scheduler.workbook_demand as parser
    from app.scheduler.model import SolverInput
    from app.services.workbook_schedule_service import WorkbookSchedulePlan

    monkeypatch.setattr(parser, "parse_source_workbook", lambda _path: [_source_row(54)])
    parsed = parser.parse_workbook_demand(tmp_path / "source.xlsx", "2026-27", 1)
    plan = WorkbookSchedulePlan(parsed=parsed, solver_input=SolverInput([], [], []))

    assert plan.complete is False
