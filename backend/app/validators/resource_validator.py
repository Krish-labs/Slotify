from dataclasses import dataclass


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]


class ResourceValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_resource(self, resource: dict) -> ValidationResult:
        self.errors = []
        self.warnings = []

        if not resource.get("name"):
            self.errors.append("Resource name is required")

        resource_type = resource.get("resource_type")
        valid_types = ["CLASSROOM", "SOFTWARE_LAB", "HARDWARE_LAB"]
        if resource_type not in valid_types:
            self.errors.append(
                f"Invalid resource_type: {resource_type}. Must be one of {valid_types}"
            )

        capacity = resource.get("capacity", 0)
        if capacity <= 0:
            self.errors.append("Capacity must be positive")

        if resource_type == "CLASSROOM" and capacity > 100:
            self.warnings.append("Classroom capacity seems unusually high (>100)")

        if resource_type in ("SOFTWARE_LAB", "HARDWARE_LAB") and capacity > 30:
            self.warnings.append(f"{resource_type} capacity seems unusually high (>30)")

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )

    def validate_availability(self, availability: dict) -> ValidationResult:
        self.errors = []
        self.warnings = []

        if not availability.get("resource_id"):
            self.errors.append("resource_id is required")

        day = availability.get("day_of_week")
        if day is None or not 0 <= day <= 6:
            self.errors.append("day_of_week must be between 0 (Monday) and 6 (Sunday)")

        start = availability.get("start_time")
        end = availability.get("end_time")
        if start and end and start >= end:
            self.errors.append("start_time must be before end_time")

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )
