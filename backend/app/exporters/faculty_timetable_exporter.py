from typing import Any

from app.exporters.excel_exporter import ExcelExporter


class FacultyTimetableExporter(ExcelExporter):
    DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]

    def export(
        self,
        entries: list[dict],
        faculty_map: dict,
        time_slots: dict,
        resources: dict,
        output_path: str,
    ):
        self.create_workbook()

        # Group entries by faculty
        faculty_entries: dict[Any, list[Any]] = {}
        for entry in entries:
            faculty_id = entry["faculty_id"]
            if faculty_id not in faculty_entries:
                faculty_entries[faculty_id] = []
            faculty_entries[faculty_id].append(entry)

        # Create one sheet per faculty
        for faculty_id, faculty_entry_list in faculty_entries.items():
            faculty = faculty_map.get(faculty_id)
            sheet_name = (
                f"{faculty['first_name']} {faculty['last_name']}"[:31]
                if faculty
                else str(faculty_id)[:31]
            )
            ws = self.workbook.create_sheet(title=sheet_name)

            self._write_faculty_timetable(ws, faculty_entry_list, time_slots, resources)

        if "Sheet" in self.workbook.sheetnames:
            self.workbook.remove(self.workbook["Sheet"])

        self.save(output_path)

    def _write_faculty_timetable(self, ws, entries: list[dict], time_slots: dict, resources: dict):
        slot_map = {}
        for entry in entries:
            ts = time_slots.get(entry["time_slot_id"])
            if ts:
                key = (ts["day_of_week"], ts["period_number"])
                slot_map[key] = ts

        sorted_slots = sorted(slot_map.keys(), key=lambda x: (x[0], x[1]))

        headers = ["Period"] + self.DAYS
        self.write_header_row(ws, headers, row=1)

        for row_idx, (day, period) in enumerate(sorted_slots, 2):
            ts = slot_map[(day, period)]
            ws.cell(row=row_idx, column=1, value=f"P{period} ({ts['start_time']}-{ts['end_time']})")
            ws.cell(row=row_idx, column=1).border = self.thin_border
            ws.cell(row=row_idx, column=1).alignment = self.cell_alignment

            day_entries = [
                e
                for e in entries
                if time_slots.get(e["time_slot_id"])
                and time_slots[e["time_slot_id"]]["day_of_week"] == day
                and time_slots[e["time_slot_id"]]["period_number"] == period
            ]

            for day_idx in range(6):
                col = day_idx + 2
                day_entry = next(
                    (
                        e
                        for e in day_entries
                        if time_slots.get(e["time_slot_id"])
                        and time_slots[e["time_slot_id"]]["day_of_week"] == day
                    ),
                    None,
                )
                if day_entry:
                    subject = day_entry.get("subject_name", "")
                    section = day_entry.get("section_name", "")
                    resource = resources.get(day_entry["resource_id"], {}).get("name", "")
                    session_type = day_entry["session_type"]
                    cell_value = f"{subject}\n{section}\n{resource}\n({session_type})"
                else:
                    cell_value = ""

                cell = ws.cell(row=row_idx, column=col, value=cell_value)
                cell.alignment = self.cell_alignment
                cell.border = self.thin_border

        self.auto_fit_columns(ws)
