from datetime import time
from uuid import uuid4

from app.core.workbook_paths import timing_reference_path
from app.services.timing_reference import reference_teaching_times, reference_time_slots


def test_real_reference_contributes_only_one_hour_teaching_intervals():
    times = reference_teaching_times(timing_reference_path())

    assert times[0] == (time(8, 0), time(9, 0))
    assert times[4] == (time(13, 0), time(14, 0))
    assert len(reference_time_slots(timing_reference_path(), uuid4())) == 48
