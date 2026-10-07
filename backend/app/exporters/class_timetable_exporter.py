from typing import Any

from app.exporters.excel_exporter import ExcelExporter


class ClassTimetableExporter(ExcelExporter):
    DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
    SHIFTS = ["MORNING", "LATE"]

    def export(
        self,
        entries: list[dict],
        sections: dict,
        time_slots: dict,
        resources: dict,
        output_path: str,
    ):
        self.create_workbook()

        # Group entries by section
        sections_entries: dict[Any, list[Any]] = {}
        for entry in entries:
            section_id = entry["section_id"]
            if section_id not in sections_entries:
                sections_entries[section_id] = []
            sections_entries[section_id].append(entry)

        # Create one sheet per section
        for section_id, section_entries in sections_entries.items():
            section = sections.get(section_id)
            sheet_name = section["name"] if section else str(section_id)[:31]
            ws = self.workbook.create_sheet(title=sheet_name[:31])

            self._write_section_timetable(ws, section_entries, time_slots, resources)

        # Remove default sheet
        if "Sheet" in self.workbook.sheetnames:
            self.workbook.remove(self.workbook["Sheet"])

        self.save(output_path)

    def _write_section_timetable(self, ws, entries: list[dict], time_slots: dict, resources: dict):
        # Get unique time slots sorted by day and period
        slot_map = {}
        for entry in entries:
            ts = time_slots.get(entry["time_slot_id"])
            if ts:
                key = (ts["day_of_week"], ts["period_number"])
                slot_map[key] = ts

        sorted_slots = sorted(slot_map.keys(), key=lambda x: (x[0], x[1]))

        # Headers
        headers = ["Period"] + self.DAYS
        self.write_header_row(ws, headers, row=1)

        # Write time slot rows
        for row_idx, (day, period) in enumerate(sorted_slots, 2):
            ts = slot_map[(day, period)]
            ws.cell(row=row_idx, column=1, value=f"P{period} ({ts['start_time']}-{ts['end_time']})")
            ws.cell(row=row_idx, column=1).border = self.thin_border
            ws.cell(row=row_idx, column=1).alignment = self.cell_alignment

            # Find entry for this day and period
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
                    faculty = day_entry.get("faculty_name", "")
                    resource = resources.get(day_entry["resource_id"], {}).get("name", "")
                    session_type = day_entry["session_type"]
                    cell_value = f"{subject}\n{faculty}\n{resource}\n({session_type})"
                else:
                    cell_value = ""

                cell = ws.cell(row=row_idx, column=col, value=cell_value)
                cell.alignment = self.cell_alignment
                cell.border = self.thin_border

        self.auto_fit_columns(ws)
