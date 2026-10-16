from dataclasses import dataclass

import pandas as pd


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]


class LoadValidator:
    REQUIRED_COLUMNS = [
        "faculty_employee_id",
        "faculty_name",
        "subject_code",
        "subject_name",
        "class_name",
        "section",
        "session_type",
        "theory_hours",
        "practical_hours",
        "tutorial_hours",
        "project_hours",
        "academic_year",
        "semester",
    ]

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_dataframe(self, df) -> ValidationResult:
        self.errors = []
        self.warnings = []

        # Check required columns
        missing_cols = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing_cols:
            self.errors.append(f"Missing required columns: {missing_cols}")

        # Check for duplicates
        dup_cols = [
            "faculty_employee_id",
            "subject_code",
            "class_name",
            "section",
            "academic_year",
            "semester",
            "session_type",
        ]
        available_dup_cols = [c for c in dup_cols if c in df.columns]
        if available_dup_cols:
            duplicates = df.duplicated(subset=available_dup_cols, keep=False)
            if duplicates.any():
                self.warnings.append(f"Found {duplicates.sum()} duplicate rows")

        # Check data types for numeric columns
        numeric_cols = [
            "theory_hours",
            "practical_hours",
            "tutorial_hours",
            "project_hours",
            "session_duration",
        ]
        for col in numeric_cols:
            if col in df.columns:
                if (
                    not df[col]
                    .apply(
                        lambda x: (
                            isinstance(x, int | float)
                            or (isinstance(x, str) and x.strip() == "")
                            or pd.isna(x)
                        )
                    )
                    .all()
                ):
                    self.errors.append(f"{col} must be numeric")

        # Check for negative hours
        for col in ["theory_hours", "practical_hours", "tutorial_hours", "project_hours"]:
            if col in df.columns:
                numeric_vals = pd.to_numeric(df[col], errors="coerce")
                if (numeric_vals < 0).any():
                    self.errors.append(f"{col} cannot be negative")

        # Check session_type values
        if "session_type" in df.columns:
            valid_types = ["THEORY", "PRACTICAL", "TUTORIAL", "PROJECT"]
            invalid = ~df["session_type"].isin(valid_types)
            if invalid.any():
                self.errors.append(
                    f"Invalid session_type values: {df.loc[invalid, 'session_type'].unique()}"
                )

        # Check semester range
        if "semester" in df.columns:
            if not df["semester"].between(1, 8).all():
                self.errors.append("semester must be between 1 and 8")

        # Check required_resource_type values
        if "required_resource_type" in df.columns:
            valid_types = ["CLASSROOM", "LAB", "COMPUTER_LAB", "SEMINAR_HALL", "WORKSHOP", "NONE"]
            invalid = ~df["required_resource_type"].isin(valid_types)
            if invalid.any():
                self.warnings.append(
                    f"Invalid required_resource_type values (will default to NONE): {df.loc[invalid, 'required_resource_type'].unique()}"
                )

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )

    def validate_load_records(self, records: list[dict]) -> ValidationResult:
        self.errors = []
        self.warnings = []

        for i, record in enumerate(records):
            if not record.get("faculty_id"):
                self.errors.append(f"Row {i}: faculty_id is required")
            if not record.get("academic_term_id"):
                self.errors.append(f"Row {i}: academic_term_id is required")
            if not record.get("subject_id"):
                self.errors.append(f"Row {i}: subject_id is required")
            if not record.get("class_id"):
                self.errors.append(f"Row {i}: class_id is required")
            if not record.get("section_id"):
                self.errors.append(f"Row {i}: section_id is required")

            theory = record.get("theory_hours", 0)
            practical = record.get("practical_hours", 0)
            tutorial = record.get("tutorial_hours", 0)
            project = record.get("project_hours", 0)

            if theory < 0 or practical < 0 or tutorial < 0 or project < 0:
                self.errors.append(f"Row {i}: hours cannot be negative")

            if theory + practical + tutorial + project == 0:
                self.warnings.append(f"Row {i}: total hours is zero")

            # Practical sessions require batch
            if record.get("session_type") == "PRACTICAL" and not record.get("batch_id"):
                self.errors.append(f"Row {i}: practical sessions require batch_id")

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )
