from typing import Any

from app.exporters.excel_exporter import ExcelExporter


class MasterTimetableExporter(ExcelExporter):
    DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]

    def export(
        self,
        entries: list[dict],
        resources: dict,
        time_slots: dict,
        sections: dict,
        faculty: dict,
        output_path: str,
    ):
        self.create_workbook()

        # Group entries by resource
        resource_entries: dict[Any, list[Any]] = {}
        for entry in entries:
            resource_id = entry["resource_id"]
            if resource_id not in resource_entries:
                resource_entries[resource_id] = []
            resource_entries[resource_id].append(entry)

        # Create one sheet per resource
        for resource_id, resource_entry_list in resource_entries.items():
            resource = resources.get(resource_id)
            sheet_name = resource["name"][:31] if resource else str(resource_id)[:31]
            ws = self.workbook.create_sheet(title=sheet_name)

            self._write_resource_timetable(ws, resource_entry_list, time_slots, sections, faculty)

        # Also create a consolidated view sheet
        ws_all = self.workbook.create_sheet(title="All Resources", index=0)
        self._write_consolidated_view(ws_all, entries, time_slots, resources, sections, faculty)

        if "Sheet" in self.workbook.sheetnames:
            self.workbook.remove(self.workbook["Sheet"])

        self.save(output_path)

    def _write_resource_timetable(
        self, ws, entries: list[dict], time_slots: dict, sections: dict, faculty: dict
    ):
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
                    section = sections.get(day_entry["section_id"], {}).get("name", "")
                    faculty_name = (
                        faculty.get(day_entry["faculty_id"], {}).get("first_name", "")
                        + " "
                        + faculty.get(day_entry["faculty_id"], {}).get("last_name", "")
                    )
                    session_type = day_entry["session_type"]
                    cell_value = f"{subject}\n{section}\n{faculty_name}\n({session_type})"
                else:
                    cell_value = ""

                cell = ws.cell(row=row_idx, column=col, value=cell_value)
                cell.alignment = self.cell_alignment
                cell.border = self.thin_border

        self.auto_fit_columns(ws)

    def _write_consolidated_view(
        self,
        ws,
        entries: list[dict],
        time_slots: dict,
        resources: dict,
        sections: dict,
        faculty: dict,
    ):
        # Create a consolidated view with resources as rows and time slots as columns
        pass
