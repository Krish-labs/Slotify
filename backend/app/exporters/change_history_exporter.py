from collections.abc import Sequence

from app.exporters.excel_exporter import ExcelExporter


class ChangeHistoryExporter(ExcelExporter):
    def export(self, versions: Sequence, output_path: str):
        self.create_workbook()

        # Summary sheet
        ws_summary = self.workbook.active
        ws_summary.title = "Version History"
        self._write_version_history(ws_summary, versions)

        # Changes detail sheet
        ws_changes = self.workbook.create_sheet(title="Changes Detail")
        self._write_changes_detail(ws_changes, versions)

        self.save(output_path)

    def _write_version_history(self, ws, versions: Sequence):
        headers = [
            "Version",
            "Status",
            "Change Type",
            "Change Summary",
            "Created By",
            "Created At",
            "Parent Version",
        ]
        self.write_header_row(ws, headers, row=1)

        for row_idx, version in enumerate(versions, 2):
            data = [
                version.version_number,
                version.status,
                version.change_type or "",
                version.change_summary or "",
                str(version.created_by) if version.created_by else "",
                version.created_at.strftime("%Y-%m-%d %H:%M") if version.created_at else "",
                str(version.parent_version_id) if version.parent_version_id else "",
            ]
            self.write_data_row(ws, data, row_idx)

        self.auto_fit_columns(ws)

    def _write_changes_detail(self, ws, versions: Sequence):
        headers = ["Version", "Change Type", "Details"]
        self.write_header_row(ws, headers, row=1)

        row_idx = 2
        for version in versions:
            if version.change_summary:
                data = [
                    version.version_number,
                    version.change_type or "",
                    version.change_summary,
                ]
                self.write_data_row(ws, data, row_idx)
                row_idx += 1

        self.auto_fit_columns(ws)
