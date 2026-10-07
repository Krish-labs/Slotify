from enum import StrEnum


class Permission(StrEnum):
    LOAD_CREATE = "load:create"
    LOAD_READ = "load:read"
    LOAD_UPDATE = "load:update"
    LOAD_DELETE = "load:delete"

    RESOURCE_CREATE = "resource:create"
    RESOURCE_READ = "resource:read"
    RESOURCE_UPDATE = "resource:update"
    RESOURCE_DELETE = "resource:delete"

    CLASS_CREATE = "class:create"
    CLASS_READ = "class:read"
    CLASS_UPDATE = "class:update"
    CLASS_DELETE = "class:delete"

    SUBJECT_CREATE = "subject:create"
    SUBJECT_READ = "subject:read"
    SUBJECT_UPDATE = "subject:update"
    SUBJECT_DELETE = "subject:delete"

    SECTION_CREATE = "section:create"
    SECTION_READ = "section:read"
    SECTION_UPDATE = "section:update"
    SECTION_DELETE = "section:delete"

    BATCH_CREATE = "batch:create"
    BATCH_READ = "batch:read"
    BATCH_UPDATE = "batch:update"
    BATCH_DELETE = "batch:delete"

    TIMETABLE_GENERATE = "timetable:generate"
    TIMETABLE_READ = "timetable:read"
    TIMETABLE_CREATE = "timetable:create"
    TIMETABLE_APPROVE = "timetable:approve"
    TIMETABLE_EXPORT = "timetable:export"

    FACULTY_READ = "faculty:read"
    FACULTY_UPDATE = "faculty:update"

    LEAVE_CREATE = "leave:create"
    LEAVE_READ = "leave:read"
    LEAVE_UPDATE = "leave:update"
    LEAVE_DELETE = "leave:delete"
    LEAVE_APPROVE = "leave:approve"

    SUBSTITUTION_CREATE = "substitution:create"
    SUBSTITUTION_READ = "substitution:read"
    SUBSTITUTION_UPDATE = "substitution:update"
    SUBSTITUTION_DELETE = "substitution:delete"
    SUBSTITUTION_APPROVE = "substitution:approve"

    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"
    AUDIT_READ = "audit:read"


class Role(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    HOD = "HOD"
    EDITOR = "EDITOR"
    FACULTY = "FACULTY"
    VIEWER = "VIEWER"


# Role groups used by endpoint guards. Roles are always referenced via the Role enum so a
# misspelt or retired name fails at import time instead of silently denying everyone.
#
# MANAGEMENT_ROLES: may manage master data (terms, faculty, assignments), approve and delete.
# LOAD_EDIT_ROLES: may also enter/edit/import load distribution (see approval-workflow.md).
MANAGEMENT_ROLES: tuple[Role, ...] = (Role.SUPER_ADMIN, Role.ADMIN, Role.HOD)
LOAD_EDIT_ROLES: tuple[Role, ...] = (*MANAGEMENT_ROLES, Role.EDITOR)

ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.SUPER_ADMIN: list(Permission),
    Role.ADMIN: list(Permission),
    Role.HOD: [
        Permission.LOAD_CREATE,
        Permission.LOAD_READ,
        Permission.LOAD_UPDATE,
        Permission.LOAD_DELETE,
        Permission.RESOURCE_CREATE,
        Permission.RESOURCE_READ,
        Permission.RESOURCE_UPDATE,
        Permission.RESOURCE_DELETE,
        Permission.CLASS_CREATE,
        Permission.CLASS_READ,
        Permission.CLASS_UPDATE,
        Permission.CLASS_DELETE,
        Permission.SUBJECT_CREATE,
        Permission.SUBJECT_READ,
        Permission.SUBJECT_UPDATE,
        Permission.SUBJECT_DELETE,
        Permission.SECTION_CREATE,
        Permission.SECTION_READ,
        Permission.SECTION_UPDATE,
        Permission.SECTION_DELETE,
        Permission.BATCH_CREATE,
        Permission.BATCH_READ,
        Permission.BATCH_UPDATE,
        Permission.BATCH_DELETE,
        Permission.TIMETABLE_GENERATE,
        Permission.TIMETABLE_READ,
        Permission.TIMETABLE_CREATE,
        Permission.TIMETABLE_APPROVE,
        Permission.TIMETABLE_EXPORT,
        Permission.FACULTY_READ,
        Permission.FACULTY_UPDATE,
        Permission.LEAVE_CREATE,
        Permission.LEAVE_READ,
        Permission.LEAVE_UPDATE,
        Permission.LEAVE_DELETE,
        Permission.LEAVE_APPROVE,
        Permission.SUBSTITUTION_CREATE,
        Permission.SUBSTITUTION_READ,
        Permission.SUBSTITUTION_UPDATE,
        Permission.SUBSTITUTION_DELETE,
        Permission.SUBSTITUTION_APPROVE,
        Permission.USER_MANAGE,
        Permission.AUDIT_READ,
    ],
    Role.EDITOR: [
        Permission.LOAD_CREATE,
        Permission.LOAD_READ,
        Permission.LOAD_UPDATE,
        Permission.RESOURCE_CREATE,
        Permission.RESOURCE_READ,
        Permission.RESOURCE_UPDATE,
        Permission.CLASS_CREATE,
        Permission.CLASS_READ,
        Permission.CLASS_UPDATE,
        Permission.SUBJECT_CREATE,
        Permission.SUBJECT_READ,
        Permission.SUBJECT_UPDATE,
        Permission.SECTION_CREATE,
        Permission.SECTION_READ,
        Permission.SECTION_UPDATE,
        Permission.BATCH_CREATE,
        Permission.BATCH_READ,
        Permission.BATCH_UPDATE,
        Permission.TIMETABLE_READ,
        Permission.TIMETABLE_EXPORT,
        Permission.FACULTY_READ,
        Permission.LEAVE_CREATE,
        Permission.LEAVE_READ,
        Permission.LEAVE_UPDATE,
        Permission.SUBSTITUTION_CREATE,
        Permission.SUBSTITUTION_READ,
        Permission.SUBSTITUTION_UPDATE,
    ],
    Role.FACULTY: [
        Permission.TIMETABLE_READ,
        Permission.FACULTY_READ,
        Permission.LEAVE_CREATE,
        Permission.LEAVE_READ,
        Permission.SUBSTITUTION_READ,
    ],
    Role.VIEWER: [
        Permission.LOAD_READ,
        Permission.RESOURCE_READ,
        Permission.CLASS_READ,
        Permission.SUBJECT_READ,
        Permission.SECTION_READ,
        Permission.BATCH_READ,
        Permission.TIMETABLE_READ,
        Permission.FACULTY_READ,
        Permission.LEAVE_READ,
        Permission.SUBSTITUTION_READ,
    ],
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, [])
