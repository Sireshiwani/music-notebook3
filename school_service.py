"""School membership, assignments, and access control (SCHOOLS_SPEC)."""
from collections import defaultdict

from models import db, User, Teacher, Student, School, SchoolAssignment, Note


def teacher_can_access_student(teacher: Teacher, student: Student) -> bool:
    """Class link (private roster) OR any school assignment for this pair."""
    if not teacher or not student:
        return False
    if student in teacher.students:
        return True
    return (
        SchoolAssignment.query.filter_by(teacher_id=teacher.id, student_id=student.id).first()
        is not None
    )


def teacher_accessible_student_ids(teacher: Teacher) -> set:
    ids = {s.id for s in teacher.students}
    for row in SchoolAssignment.query.filter_by(teacher_id=teacher.id).all():
        ids.add(row.student_id)
    return ids


def teacher_accessible_students(teacher: Teacher):
    """All students this teacher may open notes for (class + school assignments)."""
    ids = teacher_accessible_student_ids(teacher)
    if not ids:
        return []
    return (
        Student.query.filter(Student.id.in_(ids))
        .join(User)
        .order_by(User.full_name)
        .all()
    )


def teacher_school_rosters(teacher: Teacher):
    """Per-school assigned students (SchoolAssignment)."""
    out = []
    for school in sorted(teacher.schools, key=lambda s: s.name):
        rows = SchoolAssignment.query.filter_by(school_id=school.id, teacher_id=teacher.id).all()
        sid_set = {r.student_id for r in rows}
        students = (
            Student.query.filter(Student.id.in_(sid_set)).join(User).order_by(User.full_name).all()
            if sid_set
            else []
        )
        out.append({"school": school, "students": students})
    return out


def hod_owns_school(user, school: School) -> bool:
    return user and user.role == "hod" and school and school.hod_user_id == user.id


def teacher_student_badges(teacher: Teacher) -> dict:
    """Map student_id -> sorted labels (Private class, school names from assignments)."""
    badges = defaultdict(set)
    for s in teacher.students:
        badges[s.id].add("Private class")
    for a in SchoolAssignment.query.filter_by(teacher_id=teacher.id).all():
        sch = School.query.get(a.school_id)
        if sch:
            badges[a.student_id].add(sch.name)
    return {sid: sorted(labels) for sid, labels in badges.items()}


def hod_can_view_note(user, note: Note) -> bool:
    """HOD sees school-scoped notes only, for schools they manage (not private lessons)."""
    if not user or user.role != "hod" or not note.school_id:
        return False
    school = School.query.get(note.school_id)
    return bool(school and school.hod_user_id == user.id)
