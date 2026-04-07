"""Student goal sets, rubric, audit logging (TERMS_AND_GOALS_SPEC)."""
import json
from datetime import datetime
from typing import Optional, Tuple

from models import (
    db,
    StudentGoalSet,
    GoalRubricItem,
    GoalAuditEntry,
    SchoolTerm,
    CalendarPeriod,
    School,
    SchoolAssignment,
    school_teachers,
)


def _scope_key_school_term(term_id: int) -> str:
    return f"s{term_id}"


def _scope_key_private(cal_id: int) -> str:
    return f"p{cal_id}"


MAX_GOAL_SLOTS = 5


def completion_percent(goal_set: StudentGoalSet) -> int:
    items = goal_set.rubric_items
    if not items:
        return 0
    done = sum(1 for i in items if i.is_completed)
    return int(100 * done / len(items))


def save_five_goal_slots(goal_set: StudentGoalSet, actor_user_id: int, texts, dones) -> None:
    """Persist up to five goals; slot index 0–4 maps to tabs Goal 1–5. Empty text skips that slot."""
    if len(texts) != MAX_GOAL_SLOTS or len(dones) != MAX_GOAL_SLOTS:
        raise ValueError("Expected five text and five done values")
    GoalRubricItem.query.filter_by(goal_set_id=goal_set.id).delete(synchronize_session=False)
    saved = []
    for idx in range(MAX_GOAL_SLOTS):
        t = (texts[idx] or "").strip()
        d = bool(dones[idx])
        if not t:
            continue
        db.session.add(
            GoalRubricItem(
                goal_set_id=goal_set.id,
                text=t,
                sort_order=idx,
                is_completed=d,
                completed_at=datetime.utcnow() if d else None,
            )
        )
        saved.append({"slot": idx + 1, "text": t[:300], "done": d})
    log_audit(
        goal_set,
        actor_user_id,
        "goals_table_saved",
        f"Updated goals ({len(saved)} filled of {MAX_GOAL_SLOTS} slots).",
        {"slots": saved},
    )


def log_audit(goal_set: StudentGoalSet, actor_user_id: int, action: str, summary: str, detail=None):
    entry = GoalAuditEntry(
        goal_set_id=goal_set.id,
        actor_user_id=actor_user_id,
        action=action,
        summary=summary,
        detail_json=json.dumps(detail) if detail is not None else None,
        created_at=datetime.utcnow(),
    )
    db.session.add(entry)
    goal_set.updated_at = datetime.utcnow()


def get_or_create_goal_set(student_id: int, teacher_id: int, *, school_term_id=None, calendar_period_id=None):
    """Exactly one of school_term_id or calendar_period_id must be set."""
    if (school_term_id is None) == (calendar_period_id is None):
        raise ValueError("Provide exactly one of school_term_id or calendar_period_id")

    if school_term_id is not None:
        sk = _scope_key_school_term(school_term_id)
    else:
        sk = _scope_key_private(calendar_period_id)

    existing = StudentGoalSet.query.filter_by(
        student_id=student_id, teacher_id=teacher_id, scope_key=sk
    ).first()
    if existing:
        return existing, False

    gs = StudentGoalSet(
        student_id=student_id,
        teacher_id=teacher_id,
        school_term_id=school_term_id,
        calendar_period_id=calendar_period_id,
        scope_key=sk,
    )
    db.session.add(gs)
    db.session.flush()
    return gs, True


def ensure_goal_set_created_audit(goal_set: StudentGoalSet, actor_user_id: int):
    log_audit(
        goal_set,
        actor_user_id,
        "goal_set_created",
        "Goal set created for this term/period.",
        {"scope_key": goal_set.scope_key},
    )


def teacher_may_edit_goal_set(user, goal_set: StudentGoalSet) -> bool:
    if user.role != "teacher" or not user.teacher_profile:
        return False
    return goal_set.teacher_id == user.teacher_profile.id


def user_may_view_goal_set(user, goal_set: StudentGoalSet) -> bool:
    if teacher_may_edit_goal_set(user, goal_set):
        return True
    if user.role == "student" and user.student_profile and goal_set.student_id == user.student_profile.id:
        return True
    if user.role == "parent" and user.parent_profile:
        student_ids = [c.id for c in user.parent_profile.children]
        return goal_set.student_id in student_ids
    if user.role == "hod" and user.id:
        if goal_set.school_term_id:
            term = SchoolTerm.query.get(goal_set.school_term_id)
            if term and term.school and term.school.hod_user_id == user.id:
                return True
    return False


def teacher_school_options(teacher_id: int):
    """Schools this teacher belongs to, each with its terms."""
    schools = (
        School.query.join(school_teachers, school_teachers.c.school_id == School.id)
        .filter(school_teachers.c.teacher_id == teacher_id)
        .order_by(School.name)
        .all()
    )
    out = []
    for s in schools:
        terms = (
            SchoolTerm.query.filter_by(school_id=s.id)
            .order_by(SchoolTerm.sort_order, SchoolTerm.start_date)
            .all()
        )
        out.append({"school": s, "terms": terms})
    return out


def teacher_has_school_context_for_student(teacher_id: int, student_id: int, school_id: int) -> bool:
    return (
        SchoolAssignment.query.filter_by(
            school_id=school_id, teacher_id=teacher_id, student_id=student_id
        ).first()
        is not None
    )


def note_context_valid(
    *,
    school_id,
    school_term_id,
    calendar_period_id,
    teacher_id,
    student_id,
) -> Tuple[bool, Optional[str]]:
    """Validate note period fields. Legacy: all null allowed."""
    if school_term_id is None and calendar_period_id is None and school_id is None:
        return True, None
    if calendar_period_id is not None:
        if school_id is not None or school_term_id is not None:
            return False, "Private lessons cannot mix school fields with a calendar period."
        return True, None
    if school_term_id is not None:
        term = SchoolTerm.query.get(school_term_id)
        if not term:
            return False, "Invalid school term."
        if school_id is not None and term.school_id != school_id:
            return False, "School term does not belong to the selected school."
        if not teacher_has_school_context_for_student(teacher_id, student_id, term.school_id):
            return False, "You are not assigned to this student in this school for this term."
        return True, None
    return False, "Select a calendar period (private) or a school term."
