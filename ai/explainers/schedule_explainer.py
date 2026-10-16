from typing import Dict


class ScheduleExplainer:
    """Explains scheduling decisions and results in natural language."""

    def explain_generation_result(self, result: Dict) -> str:
        """Explain timetable generation result."""
        status = result.get("status", "UNKNOWN")
        entries = result.get("entries_count", 0)
        time = result.get("solve_time_seconds", 0)

        if status == "SUCCESS":
            return (
                f"Timetable generated successfully with {entries} scheduled sessions "
                f"in {time:.1f} seconds. All hard constraints satisfied."
            )
        elif status == "PARTIAL":
            return (
                f"Timetable generated with {entries} sessions, but some assignments "
                f"could not be scheduled. Review unassigned sessions."
            )
        elif status == "FAILED":
            return (
                f"Timetable generation failed. The solver could not find a feasible "
                f"solution within {time:.1f} seconds. Consider relaxing constraints."
            )
        else:
            return f"Generation status: {status}. {entries} entries processed."

    def explain_validation_result(self, validation: Dict) -> str:
        """Explain validation results."""
        is_valid = validation.get("is_valid", False)
        errors = validation.get("errors", [])
        warnings = validation.get("warnings", [])
        violations = validation.get("violations", {})

        if is_valid and not warnings:
            return "Validation passed. No errors or warnings found."

        parts = []
        if not is_valid:
            parts.append(f"Validation FAILED with {len(errors)} error(s):")
            for err in errors[:5]:
                parts.append(f"  • {err}")
            if len(errors) > 5:
                parts.append(f"  ... and {len(errors) - 5} more errors")

        if warnings:
            parts.append(f"Warnings ({len(warnings)}):")
            for warn in warnings[:3]:
                parts.append(f"  • {warn}")

        if violations:
            parts.append("Soft constraint violations:")
            for v_type, count in violations.items():
                parts.append(f"  • {v_type}: {count}")

        return "\n".join(parts)

    def explain_reoptimization(self, impact: Dict, result: Dict) -> str:
        """Explain reoptimization results."""
        affected = impact.get("affected_entries", 0)
        pinned = impact.get("pinned_entries", 0)
        status = result.get("status", "UNKNOWN")

        if status == "SUCCESS":
            return (
                f"Reoptimization completed. {affected} entries were reoptimized "
                f"while {pinned} entries remained pinned. Minimal disruption achieved."
            )
        else:
            return (
                f"Reoptimization failed for {affected} affected entries. "
                f"{pinned} entries were pinned. Consider expanding scope or relaxing constraints."
            )

    def explain_resource_utilization(self, stats: Dict) -> str:
        """Explain resource utilization statistics."""
        total = stats.get("total_resources", 0)
        used = stats.get("used_resources", 0)
        utilization = stats.get("utilization_percent", 0)
        emergency_used = stats.get("emergency_resources_used", 0)

        parts = [
            f"Resource utilization: {utilization:.1f}% ({used}/{total} resources used)."
        ]

        if emergency_used > 0:
            parts.append(
                f"Warning: {emergency_used} emergency resource(s) were used. "
                f"Consider adding more resources or adjusting schedule."
            )

        if utilization < 50:
            parts.append("Low utilization - resources may be overallocated.")

        if utilization > 90:
            parts.append("High utilization - limited flexibility for changes.")

        return " ".join(parts)

    def explain_faculty_workload(self, workload: Dict) -> str:
        """Explain faculty workload distribution."""
        total_faculty = workload.get("total_faculty", 0)
        avg_hours = workload.get("average_hours", 0)
        max_hours = workload.get("max_hours", 0)
        min_hours = workload.get("min_hours", 0)
        overloaded = workload.get("overloaded_faculty", 0)
        underloaded = workload.get("underloaded_faculty", 0)

        parts = [
            f"Faculty workload: {total_faculty} faculty, average {avg_hours:.1f} hrs/week."
        ]

        if overloaded > 0:
            parts.append(f"{overloaded} faculty overloaded (>20 hrs/week).")

        if underloaded > 0:
            parts.append(f"{underloaded} faculty underloaded (<10 hrs/week).")

        if max_hours - min_hours > 10:
            parts.append("Significant workload imbalance detected.")

        return " ".join(parts)
