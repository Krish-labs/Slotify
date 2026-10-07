# Import all models to ensure they are registered with Base.metadata
from app.database.models.academic_term import AcademicTerm
from app.database.models.audit_log import AuditLog
from app.database.models.batch import Batch
from app.database.models.class_model import Class
from app.database.models.faculty import Faculty
from app.database.models.faculty_load import FacultyLoad
from app.database.models.leave import Leave
from app.database.models.notification import Notification
from app.database.models.permission import Permission
from app.database.models.resource import Resource
from app.database.models.resource_availability import ResourceAvailability
from app.database.models.role import Role, role_permissions
from app.database.models.section import Section
from app.database.models.subject import Subject
from app.database.models.substitution import Substitution
from app.database.models.teaching_assignment import TeachingAssignment
from app.database.models.time_slot import TimeSlot
from app.database.models.timetable import Timetable
from app.database.models.timetable_entry import TimetableEntry
from app.database.models.timetable_job import TimetableJob
from app.database.models.timetable_template import TimetableTemplate
from app.database.models.timetable_version import TimetableVersion
from app.database.models.user import User, user_roles

__all__ = [
    "User",
    "user_roles",
    "Role",
    "role_permissions",
    "Permission",
    "Faculty",
    "FacultyLoad",
    "TeachingAssignment",
    "Class",
    "Section",
    "Batch",
    "Subject",
    "Resource",
    "ResourceAvailability",
    "TimetableTemplate",
    "TimeSlot",
    "Timetable",
    "TimetableEntry",
    "TimetableVersion",
    "TimetableJob",
    "Leave",
    "Substitution",
    "Notification",
    "AuditLog",
    "AcademicTerm",
]
