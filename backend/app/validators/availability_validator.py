from dataclasses import dataclass
from uuid import UUID


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]


class AvailabilityValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_faculty_availability(
        self, faculty_id: UUID, time_slot_id: UUID, availability_map: dict
    ) -> ValidationResult:
        self.errors = []
        self.warnings = []

        key = (faculty_id, time_slot_id)
        if key in availability_map:
            avail = availability_map[key]
            if not avail.get("is_available", True):
                reason = avail.get("reason", "Not available")
                self.errors.append(
                    f"Faculty {faculty_id} not available at time slot {time_slot_id}: {reason}"
                )

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )

    def validate_resource_availability(
        self, resource_id: UUID, time_slot_id: UUID, availability_map: dict
    ) -> ValidationResult:
        self.errors = []
        self.warnings = []

        key = (resource_id, time_slot_id)
        if key in availability_map:
            avail = availability_map[key]
            if not avail.get("is_available", True):
                reason = avail.get("reason", "Not available")
                self.errors.append(
                    f"Resource {resource_id} not available at time slot {time_slot_id}: {reason}"
                )

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )

    def validate_all_entries(
        self, entries: list[dict], faculty_availability: dict, resource_availability: dict
    ) -> ValidationResult:
        self.errors = []
        self.warnings = []

        for entry in entries:
            faculty_result = self.validate_faculty_availability(
                entry["faculty_id"], entry["time_slot_id"], faculty_availability
            )
            resource_result = self.validate_resource_availability(
                entry["resource_id"], entry["time_slot_id"], resource_availability
            )

            self.errors.extend(faculty_result.errors)
            self.errors.extend(resource_result.errors)
            self.warnings.extend(faculty_result.warnings)
            self.warnings.extend(resource_result.warnings)

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )
