from dataclasses import dataclass
from uuid import UUID


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]


class CapacityValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_section_capacity(
        self, section_strength: int, resource_capacity: int, section_id: UUID, resource_id: UUID
    ) -> ValidationResult:
        self.errors = []
        self.warnings = []

        if section_strength > resource_capacity:
            self.errors.append(
                f"Section {section_id} strength ({section_strength}) exceeds resource {resource_id} capacity ({resource_capacity})"
            )

        if section_strength > resource_capacity * 0.9:
            self.warnings.append(
                f"Section {section_id} nearly fills resource {resource_id} ({section_strength}/{resource_capacity})"
            )

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )

    def validate_batch_capacity(
        self, batch_strength: int, resource_capacity: int, batch_id: UUID, resource_id: UUID
    ) -> ValidationResult:
        self.errors = []
        self.warnings = []

        if batch_strength > resource_capacity:
            self.errors.append(
                f"Batch {batch_id} strength ({batch_strength}) exceeds resource {resource_id} capacity ({resource_capacity})"
            )

        if batch_strength > resource_capacity * 0.9:
            self.warnings.append(
                f"Batch {batch_id} nearly fills resource {resource_id} ({batch_strength}/{resource_capacity})"
            )

        # Check batch size guidelines (20-24 for practicals)
        if batch_strength < 15:
            self.warnings.append(f"Batch {batch_id} is small ({batch_strength}), consider merging")
        elif batch_strength > 25:
            self.warnings.append(
                f"Batch {batch_id} is large ({batch_strength}), consider splitting"
            )

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )

    def validate_all(
        self, entries: list[dict], sections: dict, batches: dict, resources: dict
    ) -> ValidationResult:
        self.errors = []
        self.warnings = []

        for entry in entries:
            resource = resources.get(entry["resource_id"])
            if not resource:
                continue

            if entry["session_type"] == "LECTURE":
                section = sections.get(entry["section_id"])
                if section:
                    result = self.validate_section_capacity(
                        section.get("strength", 0),
                        resource.get("capacity", 0),
                        entry["section_id"],
                        entry["resource_id"],
                    )
                    self.errors.extend(result.errors)
                    self.warnings.extend(result.warnings)

            elif entry["session_type"] in ("PRACTICAL", "TUTORIAL"):
                batch = batches.get(entry.get("batch_id"))
                if batch:
                    result = self.validate_batch_capacity(
                        batch.get("strength", 0),
                        resource.get("capacity", 0),
                        entry["batch_id"],
                        entry["resource_id"],
                    )
                    self.errors.extend(result.errors)
                    self.warnings.extend(result.warnings)

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )
