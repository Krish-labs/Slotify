from typing import Any

from app.exporters.excel_exporter import ExcelExporter


class ValidationReportExporter(ExcelExporter):
    def export(self, validation_result: dict, output_path: str):
        self.create_workbook()

        # Summary sheet
        ws_summary = self.workbook.active
        ws_summary.title = "Summary"
        self._write_summary(ws_summary, validation_result)

        # Errors sheet
        if validation_result.get("errors"):
            ws_errors = self.workbook.create_sheet(title="Errors")
            self._write_errors(ws_errors, validation_result["errors"])

        # Warnings sheet
        if validation_result.get("warnings"):
            ws_warnings = self.workbook.create_sheet(title="Warnings")
            self._write_warnings(ws_warnings, validation_result["warnings"])

        # Violations sheet
        if validation_result.get("violations"):
            ws_violations = self.workbook.create_sheet(title="Violations")
            self._write_violations(ws_violations, validation_result["violations"])

        self.save(output_path)

    def _write_summary(self, ws, result: dict):
        headers = ["Metric", "Value"]
        self.write_header_row(ws, headers, row=1)

        data: list[list[Any]] = [
            ["Status", "PASS" if result.get("is_valid") else "FAIL"],
            ["Total Errors", len(result.get("errors", []))],
            ["Total Warnings", len(result.get("warnings", []))],
            ["Total Violations", sum(result.get("violations", {}).values())],
        ]

        for row_idx, row_data in enumerate(data, 2):
            self.write_data_row(ws, row_data, row_idx)

        self.auto_fit_columns(ws)

    def _write_errors(self, ws, errors: list[str]):
        headers = ["#", "Error"]
        self.write_header_row(ws, headers, row=1)

        for row_idx, error in enumerate(errors, 2):
            self.write_data_row(ws, [row_idx - 1, error], row_idx)

        self.auto_fit_columns(ws)

    def _write_warnings(self, ws, warnings: list[str]):
        headers = ["#", "Warning"]
        self.write_header_row(ws, headers, row=1)

        for row_idx, warning in enumerate(warnings, 2):
            self.write_data_row(ws, [row_idx - 1, warning], row_idx)

        self.auto_fit_columns(ws)

    def _write_violations(self, ws, violations: dict[str, int]):
        headers = ["Violation Type", "Count"]
        self.write_header_row(ws, headers, row=1)

        for row_idx, (v_type, count) in enumerate(violations.items(), 2):
            self.write_data_row(ws, [v_type, count], row_idx)

        self.auto_fit_columns(ws)
