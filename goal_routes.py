"""Routes: calendar periods, student goals, rubric, audit, HOD schools."""
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from models import (
    db,
    User,
    School,
    SchoolTerm,
    CalendarPeriod,
    StudentGoalSet,
    GoalRubricItem,
    GoalAuditEntry,
    Note,
    SchoolAssignment,
    Teacher,
    Student,
)
from goal_service import (
    get_or_create_goal_set,
    ensure_goal_set_created_audit,
    log_audit,
    completion_percent,
    teacher_may_edit_goal_set,
    user_may_view_goal_set,
    save_five_goal_slots,
)

goals_bp = Blueprint("goals", __name__)


def group_school_notes_by_teacher_student(notes):
    """
    Build HOD view structure: teachers (A→Z) → students under each (A→Z) → notes (newest first).
    Each item: {"teacher": Teacher, "students": [{"student": Student, "notes": [Note, ...]}, ...]}.
    """
    if not notes:
        return []
    by_teacher = defaultdict(lambda: defaultdict(list))
    teacher_by_id = {}
    student_by_id = {}
    for n in notes:
        by_teacher[n.teacher_id][n.student_id].append(n)
        teacher_by_id[n.teacher_id] = n.teacher
        student_by_id[n.student_id] = n.student
    for tid in by_teacher:
        for sid in by_teacher[tid]:
            by_teacher[tid][sid].sort(key=lambda x: x.date, reverse=True)
    teacher_ids = sorted(
        teacher_by_id.keys(), key=lambda i: teacher_by_id[i].user.full_name.lower()
    )
    out = []
    for tid in teacher_ids:
        student_ids = sorted(
            by_teacher[tid].keys(),
            key=lambda i: student_by_id[i].user.full_name.lower(),
        )
        out.append(
            {
                "teacher": teacher_by_id[tid],
                "students": [
                    {"student": student_by_id[sid], "notes": by_teacher[tid][sid]}
                    for sid in student_ids
                ],
            }
        )
    return out


# --- Calendar periods (teachers) ---


@goals_bp.route("/teacher/calendar-periods", methods=["GET", "POST"])
@login_required
def calendar_periods():
    if current_user.role != "teacher":
        flash("Access denied", "danger")
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        try:
            from datetime import date as date_cls

            sd = datetime.strptime(request.form.get("start_date") or "", "%Y-%m-%d").date()
            ed = datetime.strptime(request.form.get("end_date") or "", "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid dates. Use YYYY-MM-DD.", "danger")
            return redirect(url_for("goals.calendar_periods"))
        if not name or ed < sd:
            flash("Name required and end date must be on or after start date.", "danger")
            return redirect(url_for("goals.calendar_periods"))
        p = CalendarPeriod(name=name, start_date=sd, end_date=ed)
        db.session.add(p)
        db.session.commit()
        flash("Calendar period created.", "success")
        return redirect(url_for("goals.calendar_periods"))

    periods = CalendarPeriod.query.order_by(CalendarPeriod.start_date.desc()).all()
    return render_template("goals/calendar_periods.html", periods=periods)


@goals_bp.route("/teacher/calendar-periods/<int:period_id>/delete", methods=["POST"])
@login_required
def delete_calendar_period(period_id):
    if current_user.role != "teacher":
        abort(403)
    p = CalendarPeriod.query.get_or_404(period_id)
    if Note.query.filter_by(calendar_period_id=p.id).first() or StudentGoalSet.query.filter_by(
        calendar_period_id=p.id
    ).first():
        flash("This period is in use and cannot be deleted.", "warning")
        return redirect(url_for("goals.calendar_periods"))
    db.session.delete(p)
    db.session.commit()
    flash("Period removed.", "info")
    return redirect(url_for("goals.calendar_periods"))


# --- Goal rubric (teachers edit) ---


@goals_bp.route("/student/<int:student_id>/goal-set/<int:goal_set_id>/audit")
@login_required
def goal_audit_log(student_id, goal_set_id):
    gs = StudentGoalSet.query.get_or_404(goal_set_id)
    if gs.student_id != student_id:
        abort(404)
    if not user_may_view_goal_set(current_user, gs):
        flash("Not authorized", "danger")
        return redirect(url_for("dashboard.dashboard"))
    entries = (
        GoalAuditEntry.query.filter_by(goal_set_id=gs.id).order_by(GoalAuditEntry.created_at.desc()).all()
    )
    return render_template(
        "goals/goal_audit.html",
        goal_set=gs,
        student=gs.student,
        entries=entries,
        completion_pct=completion_percent(gs),
    )


@goals_bp.route("/goal-set/<int:goal_set_id>/save-five", methods=["POST"])
@login_required
def goal_set_save_five(goal_set_id):
    gs = StudentGoalSet.query.get_or_404(goal_set_id)
    if not teacher_may_edit_goal_set(current_user, gs):
        abort(403)
    texts = [(request.form.get(f"text_{i}") or "") for i in range(1, 6)]
    dones = [request.form.get(f"done_{i}") == "on" for i in range(1, 6)]
    save_five_goal_slots(gs, current_user.id, texts, dones)
    db.session.commit()
    flash("Goals saved.", "success")
    return redirect(request.referrer or url_for("notes.student_notes", student_id=gs.student_id))


@goals_bp.route("/goal-set/<int:goal_set_id>/rubric/add", methods=["POST"])
@login_required
def goal_rubric_add(goal_set_id):
    gs = StudentGoalSet.query.get_or_404(goal_set_id)
    if not teacher_may_edit_goal_set(current_user, gs):
        abort(403)
    text = (request.form.get("text") or "").strip()
    if not text:
        flash("Item text is required.", "warning")
        return redirect(request.referrer or url_for("dashboard.dashboard"))
    max_ord = db.session.query(func.max(GoalRubricItem.sort_order)).filter_by(goal_set_id=gs.id).scalar() or 0
    item = GoalRubricItem(goal_set_id=gs.id, text=text, sort_order=max_ord + 1, is_completed=False)
    db.session.add(item)
    db.session.flush()
    log_audit(
        gs,
        current_user.id,
        "rubric_item_added",
        f"Added goal item: {text[:200]}",
        {"item_id": item.id},
    )
    db.session.commit()
    flash("Goal item added.", "success")
    return redirect(request.referrer or url_for("notes.student_notes", student_id=gs.student_id))


@goals_bp.route("/goal-item/<int:item_id>/toggle", methods=["POST"])
@login_required
def goal_rubric_toggle(item_id):
    item = GoalRubricItem.query.get_or_404(item_id)
    gs = item.goal_set
    if not teacher_may_edit_goal_set(current_user, gs):
        abort(403)
    item.is_completed = not item.is_completed
    item.completed_at = datetime.utcnow() if item.is_completed else None
    action = "rubric_completed" if item.is_completed else "rubric_uncompleted"
    log_audit(
        gs,
        current_user.id,
        action,
        f"Item marked {'complete' if item.is_completed else 'incomplete'}: {item.text[:120]}",
        {"item_id": item.id},
    )
    db.session.commit()
    return redirect(request.referrer or url_for("notes.student_notes", student_id=gs.student_id))


@goals_bp.route("/goal-item/<int:item_id>/delete", methods=["POST"])
@login_required
def goal_rubric_delete(item_id):
    item = GoalRubricItem.query.get_or_404(item_id)
    gs = item.goal_set
    if not teacher_may_edit_goal_set(current_user, gs):
        abort(403)
    preview = item.text[:120]
    iid = item.id
    db.session.delete(item)
    log_audit(gs, current_user.id, "rubric_item_deleted", f"Removed goal item: {preview}", {"item_id": iid})
    db.session.commit()
    flash("Item removed.", "info")
    return redirect(request.referrer or url_for("notes.student_notes", student_id=gs.student_id))


@goals_bp.route("/goal-item/<int:item_id>/edit", methods=["POST"])
@login_required
def goal_rubric_edit(item_id):
    item = GoalRubricItem.query.get_or_404(item_id)
    gs = item.goal_set
    if not teacher_may_edit_goal_set(current_user, gs):
        abort(403)
    new_text = (request.form.get("text") or "").strip()
    if not new_text:
        flash("Text required.", "warning")
        return redirect(request.referrer or url_for("notes.student_notes", student_id=gs.student_id))
    old = item.text
    item.text = new_text
    log_audit(
        gs,
        current_user.id,
        "rubric_item_edited",
        "Updated goal item text.",
        {"item_id": item.id, "before": old[:500], "after": new_text[:500]},
    )
    db.session.commit()
    flash("Item updated.", "success")
    return redirect(request.referrer or url_for("notes.student_notes", student_id=gs.student_id))


# --- HOD: schools & terms ---


@goals_bp.route("/hod/schools", methods=["GET", "POST"])
@login_required
def hod_schools():
    if current_user.role != "hod":
        flash("Access denied", "danger")
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("School name is required.", "danger")
            return redirect(url_for("goals.hod_schools"))
        s = School(name=name, hod_user_id=current_user.id)
        db.session.add(s)
        db.session.commit()
        flash("School created.", "success")
        return redirect(url_for("goals.hod_schools"))

    schools = School.query.filter_by(hod_user_id=current_user.id).order_by(School.name).all()
    return render_template("goals/hod_schools.html", schools=schools)


@goals_bp.route("/hod/schools/<int:school_id>/terms", methods=["POST"])
@login_required
def hod_school_term_add(school_id):
    if current_user.role != "hod":
        abort(403)
    school = School.query.get_or_404(school_id)
    if school.hod_user_id != current_user.id:
        abort(403)
    name = (request.form.get("name") or "").strip()
    try:
        sd = datetime.strptime(request.form.get("start_date") or "", "%Y-%m-%d").date()
        ed = datetime.strptime(request.form.get("end_date") or "", "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid dates.", "danger")
        return redirect(url_for("goals.hod_school_detail", school_id=school_id))
    if not name or ed < sd:
        flash("Check name and date range.", "danger")
        return redirect(url_for("goals.hod_school_detail", school_id=school_id))
    t = SchoolTerm(school_id=school.id, name=name, start_date=sd, end_date=ed)
    db.session.add(t)
    db.session.commit()
    flash("Term added.", "success")
    return redirect(url_for("goals.hod_school_detail", school_id=school_id))


@goals_bp.route("/hod/schools/<int:school_id>", methods=["GET", "POST"])
@login_required
def hod_school_detail(school_id):
    if current_user.role != "hod":
        abort(403)
    school = School.query.get_or_404(school_id)
    if school.hod_user_id != current_user.id:
        abort(403)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_teacher":
            uname = (request.form.get("teacher_username") or "").strip()
            u = User.query.filter_by(username=uname, role="teacher").first()
            if not u or not u.teacher_profile:
                flash("Teacher username not found.", "danger")
                return redirect(url_for("goals.hod_school_detail", school_id=school_id))
            t_obj = u.teacher_profile
            if t_obj not in school.teachers:
                school.teachers.append(t_obj)
                db.session.commit()
                flash("Teacher added to school.", "success")
            else:
                flash("Teacher already in this school.", "info")
            return redirect(url_for("goals.hod_school_detail", school_id=school_id))

        if action == "add_student":
            uname = (request.form.get("student_username") or "").strip()
            u = User.query.filter_by(username=uname, role="student").first()
            if not u or not u.student_profile:
                flash("Student username not found.", "danger")
                return redirect(url_for("goals.hod_school_detail", school_id=school_id))
            stu = u.student_profile
            if stu not in school.students:
                school.students.append(stu)
                db.session.commit()
                flash("Student added to school.", "success")
            else:
                flash("Student already in this school.", "info")
            return redirect(url_for("goals.hod_school_detail", school_id=school_id))

        if action == "assign":
            tid = request.form.get("teacher_id", type=int)
            sid = request.form.get("student_id", type=int)
            if not tid or not sid:
                flash("Select teacher and student.", "danger")
                return redirect(url_for("goals.hod_school_detail", school_id=school_id))
            if SchoolAssignment.query.filter_by(school_id=school.id, teacher_id=tid, student_id=sid).first():
                flash("Already assigned.", "info")
            else:
                db.session.add(SchoolAssignment(school_id=school.id, teacher_id=tid, student_id=sid))
                db.session.commit()
                flash("Assignment created.", "success")
            return redirect(url_for("goals.hod_school_detail", school_id=school_id))

    terms = SchoolTerm.query.filter_by(school_id=school.id).order_by(SchoolTerm.start_date.desc()).all()
    teachers_list = list(school.teachers)
    students_list = list(school.students)
    assignments = SchoolAssignment.query.filter_by(school_id=school.id).all()

    return render_template(
        "goals/hod_school_detail.html",
        school=school,
        terms=terms,
        teachers_list=teachers_list,
        students_list=students_list,
        assignments=assignments,
    )


@goals_bp.route("/hod/dashboard")
@login_required
def hod_dashboard():
    if current_user.role != "hod":
        flash("Access denied", "danger")
        return redirect(url_for("dashboard.dashboard"))
    schools = School.query.filter_by(hod_user_id=current_user.id).order_by(School.name).all()
    return render_template("goals/hod_dashboard.html", schools=schools)


@goals_bp.route("/hod/schools/<int:school_id>/lessons")
@login_required
def hod_school_lessons(school_id):
    """School-scoped lesson notes for HOD monitoring (SCHOOLS_SPEC)."""
    if current_user.role != "hod":
        flash("Access denied", "danger")
        return redirect(url_for("dashboard.dashboard"))
    school = School.query.get_or_404(school_id)
    if school.hod_user_id != current_user.id:
        abort(403)
    notes = (
        Note.query.options(
            joinedload(Note.teacher).joinedload(Teacher.user),
            joinedload(Note.student).joinedload(Student.user),
            joinedload(Note.school_term),
        )
        .filter_by(school_id=school_id)
        .order_by(Note.date.desc())
        .limit(300)
        .all()
    )
    lesson_groups = group_school_notes_by_teacher_student(notes)
    return render_template(
        "goals/hod_school_lessons.html",
        school=school,
        lesson_groups=lesson_groups,
    )
