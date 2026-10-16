"""Unit tests for source-name resolution used by workbook scheduling."""

from types import SimpleNamespace

from app.services.workbook_schedule_service import _faculty_match, _resource_type


def _faculty(first_name, last_name):
    return SimpleNamespace(first_name=first_name, last_name=last_name)


def test_exact_full_name_matches():
    faculties = [_faculty("Anjali", "Bhatlawande")]
    assert _faculty_match("Dr. Anjali S. Bhatlawande", faculties) is faculties[0]


def test_title_without_trailing_space_still_matches():
    """Regression: 'Ms.Shubhangi Gosavi' failed the old title regex."""
    faculties = [_faculty("Shubhangi", "Gosavi")]
    assert _faculty_match("Ms.Shubhangi Gosavi", faculties) is faculties[0]


def test_surname_plus_initials_disambiguates_shared_surnames():
    faculties = [_faculty("Swati", "Deshmukh"), _faculty("Mayuri", "Deshmukh")]
    assert _faculty_match("Ms. Swati N. Deshmukh", faculties) is faculties[0]
    assert _faculty_match("Dr. Mayuri T. Deshmukh", faculties) is faculties[1]


def test_ambiguous_initials_do_not_match():
    faculties = [_faculty("Swati", "Deshmukh"), _faculty("Sneha", "Deshmukh")]
    assert _faculty_match("Ms. S. Deshmukh", faculties) is None


def test_unknown_faculty_returns_none():
    assert _faculty_match("Nobody Unknown", [_faculty("Anjali", "Bhatlawande")]) is None


def test_title_stripped_matches():
    """Title-stripped normalized match works when full name exact match fails."""
    faculties = [_faculty("John", "Doe")]
    # "Dr. John Doe" should match via title-stripping strategy
    result = _faculty_match("Dr. John Doe", faculties)
    assert result is faculties[0]


def test_middle_name_initial_not_required():
    """When source has initials but faculty has full first name, it should still match if initials match."""
    faculties = [_faculty("Robert", "Smith")]
    # "R. Smith" should match via initials
    result = _faculty_match("R. Smith", faculties)
    assert result is faculties[0]


def test_no_match_when_multiple_surnames():
    """When multiple faculty share surname and no unique initials, should return None."""
    faculties = [
        _faculty("Swati", "Deshmukh"),
        _faculty("Sneha", "Deshmukh"),
        _faculty("Rohit", "Deshmukh"),
    ]
    assert _faculty_match("S. Deshmukh", faculties) is None


def test_faculty_with_designation_matches():
    """Faculty with designation (Prof., Dr.) in source should match via stripping."""
    faculties = [_faculty("Anita", "Sharma")]
    result = _faculty_match("Prof. Anita Sharma", faculties)
    assert result is faculties[0]


def test_faculty_with_multiple_initials_matches():
    """Faculty with multiple initials in source should match when all initials are present."""
    faculties = [_faculty("George", "Washington")]
    result = _faculty_match("G. W. Washington", faculties)
    assert result is faculties[0]


def test_faculty_no_match_when_initials_insufficient():
    """When initials don't uniquely identify, should return None."""
    faculties = [_faculty("Alice", "Smith"), _faculty("Bob", "Smith")]
    # "S. Smith" has initial S which could be either Alice or Bob - ambiguous
    # Actually "S." could match either, so this should be None
    result = _faculty_match("S. Smith", faculties)
    assert result is None


def test_faculty_match_with_empty_name():
    """Empty or whitespace-only name should return None."""
    faculties = [_faculty("Anjali", "Bhatlawande")]
    assert _faculty_match("", faculties) is None
    assert _faculty_match("  ", faculties) is None


def test_practical_resource_type_mapping_is_conservative():
    assert _resource_type("LAB") == "HARDWARE_LAB"
    assert _resource_type("COMPUTER_LAB") == "SOFTWARE_LAB"
    assert _resource_type("WORKSHOP") == "HARDWARE_LAB"
    assert _resource_type("CLASSROOM") is None
    assert _resource_type("UNKNOWN") is None
