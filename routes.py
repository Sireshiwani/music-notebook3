import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session, current_app, Flask
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse  # Fixed import
from models import db, User, Teacher, Student, Parent, Note, NoteSignature, StudentGoalSet, CalendarPeriod, SchoolTerm
from goal_service import (
    get_or_create_goal_set,
    ensure_goal_set_created_audit,
    note_context_valid,
    teacher_school_options,
    completion_percent,
)
from school_service import (
    teacher_can_access_student,
    teacher_accessible_students,
    teacher_school_rosters,
    teacher_student_badges,
    teacher_accessible_student_ids,
    hod_can_view_note,
)
from forms import LoginForm, StudentRegistrationForm, ParentRegistrationForm, TeacherRegistrationForm, HodRegistrationForm, NoteForm, \
    SignatureForm
from datetime import datetime
import os
from sqlalchemy import or_, func
from services import FileUploadService

# Blueprints
auth_bp = Blueprint('auth', __name__)
dashboard_bp = Blueprint('dashboard', __name__)
notes_bp = Blueprint('notes', __name__)



# Auth Routes
@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))

        if not user.is_active:
            flash('Account is disabled', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=form.remember.data)
        next_page = request.args.get('next')

        # Use urlparse instead of url_parse
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('dashboard.dashboard')

        flash('Login successful!', 'success')
        return redirect(next_page)

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    form = StudentRegistrationForm()
    if form.validate_on_submit():
        # Check if username or email exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('auth.register_student'))

        if User.query.filter_by(email=form.email.data).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('auth.register_student'))

        # Create user
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            phone=form.phone.data,
            role='student'
        )
        user.set_password(form.password.data)

        # Create student profile
        student = Student(
            user=user,
            date_of_birth=form.date_of_birth.data,
            grade_level=form.grade_level.data
        )

        db.session.add(user)
        db.session.add(student)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register_student.html', form=form)


@auth_bp.route('/register/parent', methods=['GET', 'POST'])
def register_parent():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    form = ParentRegistrationForm()
    if form.validate_on_submit():
        # Check if username or email exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('auth.register_parent'))

        if User.query.filter_by(email=form.email.data).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('auth.register_parent'))

        # Find student
        student_user = User.query.filter_by(username=form.student_username.data, role='student').first()
        if not student_user:
            flash('Student not found. Please check the username.', 'danger')
            return redirect(url_for('auth.register_parent'))

        # Create user
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            phone=form.phone.data,
            role='parent'
        )
        user.set_password(form.password.data)

        # Create parent profile
        parent = Parent(
            user=user,
            occupation=form.occupation.data,
            relationship=form.relationship.data
        )

        # Link parent to student
        parent.children.append(student_user.student_profile)

        db.session.add(user)
        db.session.add(parent)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register_parent.html', form=form)


@auth_bp.route('/register/teacher', methods=['GET', 'POST'])
def register_teacher():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    form = TeacherRegistrationForm()
    if form.validate_on_submit():
        # Check if username or email exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('auth.register_teacher'))

        if User.query.filter_by(email=form.email.data).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('auth.register_teacher'))

        # Create user
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            phone=form.phone.data,
            role='teacher'
        )
        user.set_password(form.password.data)

        # Create teacher profile
        teacher = Teacher(
            user=user,
            qualifications=form.qualifications.data,
            subjects=form.subjects.data
        )

        db.session.add(user)
        db.session.add(teacher)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register_teacher.html', form=form)


@auth_bp.route('/register/hod', methods=['GET', 'POST'])
def register_hod():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    form = HodRegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('auth.register_hod'))
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('auth.register_hod'))

        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            phone=form.phone.data,
            role='hod',
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register_hod.html', form=form)


# Teacher Management Routes
@notes_bp.route('/teacher/students')
@login_required
def teacher_students():
    """View teacher's students"""
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    teacher = current_user.teacher_profile
    students = teacher_accessible_students(teacher) if teacher else []
    school_rosters = teacher_school_rosters(teacher) if teacher else []
    private_ids = {s.id for s in teacher.students} if teacher else set()
    note_counts = {}
    if teacher:
        note_counts = dict(
            db.session.query(Note.student_id, func.count(Note.id))
            .filter(Note.teacher_id == teacher.id)
            .group_by(Note.student_id)
            .all()
        )
    total_notes = Note.query.filter_by(teacher_id=teacher.id).count() if teacher else 0
    signed_notes = (
        Note.query.join(NoteSignature).filter(Note.teacher_id == teacher.id).count() if teacher else 0
    )
    student_badges = teacher_student_badges(teacher) if teacher else {}

    return render_template(
        'teacher/students.html',
        students=students,
        school_rosters=school_rosters,
        private_student_ids=private_ids,
        teacher_student_note_counts=note_counts,
        student_badges=student_badges,
        total_notes=total_notes,
        signed_notes=signed_notes,
        teacher=teacher,
    )


@notes_bp.route('/teacher/add-student', methods=['GET', 'POST'])
@login_required
def add_student():
    """Add student to teacher's class"""
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    teacher = current_user.teacher_profile

    if request.method == 'POST':
        username = request.form.get('username')

        if not username:
            flash('Username is required', 'danger')
            return redirect(url_for('notes.add_student'))

        # Find student by username
        student_user = User.query.filter_by(username=username, role='student').first()

        if not student_user:
            flash('Student not found. Please check the username.', 'danger')
            return redirect(url_for('notes.add_student'))

        student = student_user.student_profile

        # Check if student is already assigned
        if student in teacher.students:
            flash('Student is already in your class', 'warning')
            return redirect(url_for('notes.teacher_students'))

        # Add student to teacher
        teacher.students.append(student)
        db.session.commit()

        flash(f'Student {student.user.full_name} added successfully!', 'success')
        return redirect(url_for('notes.teacher_students'))

    # Get available students (not already assigned to this teacher)
    all_students = Student.query.join(User).filter(User.role == 'student').all()
    available_students = [s for s in all_students if s not in teacher.students]

    return render_template('teacher/add_student.html',
                           available_students=available_students,
                           teacher=teacher)


# Dashboard Routes
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'hod':
        return redirect(url_for('goals.hod_dashboard'))

    if current_user.role == 'teacher':
        teacher = current_user.teacher_profile
        students = teacher_accessible_students(teacher) if teacher else []
        school_rosters = teacher_school_rosters(teacher) if teacher else []
        student_note_counts = {}
        if teacher:
            student_note_counts = dict(
                db.session.query(Note.student_id, func.count(Note.id))
                .filter(Note.teacher_id == teacher.id)
                .group_by(Note.student_id)
                .all()
            )
        recent_notes = Note.query.filter_by(teacher_id=teacher.id).order_by(Note.date.desc()).limit(
            10).all() if teacher else []
        signed_notes_count = (
            Note.query.filter(Note.teacher_id == teacher.id).filter(Note.signature.has()).count()
            if teacher
            else 0
        )
        pending_notes_count = (
            Note.query.filter(Note.teacher_id == teacher.id).filter(~Note.signature.has()).count()
            if teacher
            else 0
        )
        student_badges = teacher_student_badges(teacher) if teacher else {}

        return render_template(
            'dashboard/teacher.html',
            students=students,
            school_rosters=school_rosters,
            student_note_counts=student_note_counts,
            student_badges=student_badges,
            recent_notes=recent_notes,
            signed_notes_count=signed_notes_count,
            pending_notes_count=pending_notes_count,
        )

    elif current_user.role == 'student':
        student = current_user.student_profile
        teachers = student.teachers if student else []
        recent_notes = Note.query.filter_by(student_id=student.id).order_by(Note.date.desc()).limit(
            10).all() if student else []

        student_goal_summary = []
        if student:
            for gs in (
                StudentGoalSet.query.filter_by(student_id=student.id)
                .order_by(StudentGoalSet.updated_at.desc())
                .all()
            ):
                pct = completion_percent(gs)
                items = sorted(gs.rubric_items, key=lambda x: (x.sort_order, x.id))
                student_goal_summary.append(
                    {
                        "goal_set": gs,
                        "percent": pct,
                        "done_count": sum(1 for i in items if i.is_completed),
                        "total_count": len(items),
                        "slots": gs.five_slots(),
                    }
                )

        return render_template(
            'dashboard/student.html',
            teachers=teachers,
            recent_notes=recent_notes,
            student_goal_summary=student_goal_summary,
        )

    elif current_user.role == 'parent':
        parent = current_user.parent_profile
        children = parent.children if parent else []
        notes = []
        for child in children:
            child_notes = Note.query.filter_by(student_id=child.id).order_by(Note.date.desc()).limit(5).all()
            notes.extend(child_notes)

        children_goal_summaries = []
        for child in children:
            summaries = []
            for gs in (
                StudentGoalSet.query.filter_by(student_id=child.id)
                .order_by(StudentGoalSet.updated_at.desc())
                .all()
            ):
                pct = completion_percent(gs)
                items = sorted(gs.rubric_items, key=lambda x: (x.sort_order, x.id))
                summaries.append(
                    {
                        "goal_set": gs,
                        "percent": pct,
                        "done_count": sum(1 for i in items if i.is_completed),
                        "total_count": len(items),
                        "slots": gs.five_slots(),
                    }
                )
            children_goal_summaries.append({"child": child, "summaries": summaries})

        return render_template(
            "dashboard/parent.html",
            children=children,
            notes=notes[:10],
            children_goal_summaries=children_goal_summaries,
        )


# Notes Routes
@notes_bp.route('/student/<int:student_id>/notes')
@login_required
def student_notes(student_id):
    # Authorization check
    if current_user.role == 'teacher':
        teacher = current_user.teacher_profile
        student = Student.query.get_or_404(student_id)

        if not teacher_can_access_student(teacher, student):
            flash('Not authorized to view this student\'s notes', 'danger')
            return redirect(url_for('dashboard.dashboard'))

        cp_open = request.args.get('calendar_period_id', type=int)
        st_open = request.args.get('school_term_id', type=int)
        if cp_open:
            gs, cr = get_or_create_goal_set(student.id, teacher.id, calendar_period_id=cp_open)
            if cr:
                ensure_goal_set_created_audit(gs, current_user.id)
            db.session.commit()
        elif st_open:
            gs, cr = get_or_create_goal_set(student.id, teacher.id, school_term_id=st_open)
            if cr:
                ensure_goal_set_created_audit(gs, current_user.id)
            db.session.commit()

        notes = Note.query.filter_by(student_id=student_id, teacher_id=teacher.id).order_by(Note.date.desc()).all()
        goal_sets = StudentGoalSet.query.filter_by(
            student_id=student_id, teacher_id=teacher.id
        ).order_by(StudentGoalSet.updated_at.desc()).all()
        goal_meta = [(gs, completion_percent(gs)) for gs in goal_sets]
        calendar_periods = CalendarPeriod.query.order_by(CalendarPeriod.start_date.desc()).all()
        school_options = teacher_school_options(teacher.id)

        return render_template('notes/student_notes.html',
                               student=student,
                               notes=notes,
                               goal_sets_meta=goal_meta,
                               calendar_periods=calendar_periods,
                               school_options=school_options)

    elif current_user.role == 'student':
        if current_user.student_profile.id != student_id:
            flash('Not authorized', 'danger')
            return redirect(url_for('dashboard.dashboard'))

        student = current_user.student_profile
        notes = Note.query.filter_by(student_id=student_id).order_by(Note.date.desc()).all()
        goal_sets = StudentGoalSet.query.filter_by(student_id=student_id).order_by(
            StudentGoalSet.updated_at.desc()
        ).all()
        goal_meta = [(gs, completion_percent(gs)) for gs in goal_sets]

        return render_template('notes/student_notes.html',
                               student=student,
                               notes=notes,
                               goal_sets_meta=goal_meta,
                               calendar_periods=[],
                               school_options=[])

    elif current_user.role == 'parent':
        parent = current_user.parent_profile
        student = Student.query.get_or_404(student_id)

        # Check if parent has access to this student
        if student not in parent.children:
            flash('Not authorized to view this student\'s notes', 'danger')
            return redirect(url_for('dashboard.dashboard'))

        notes = Note.query.filter_by(student_id=student_id).order_by(Note.date.desc()).all()
        goal_sets = StudentGoalSet.query.filter_by(student_id=student_id).order_by(
            StudentGoalSet.updated_at.desc()
        ).all()
        goal_meta = [(gs, completion_percent(gs)) for gs in goal_sets]

        return render_template('notes/student_notes.html',
                               student=student,
                               notes=notes,
                               goal_sets_meta=goal_meta,
                               calendar_periods=[],
                               school_options=[])


@notes_bp.route('/note/add/<int:student_id>', methods=['GET', 'POST'])
@login_required
def add_note(student_id):
    if current_user.role != 'teacher':
        flash('Only teachers can add notes', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    teacher = current_user.teacher_profile
    student = Student.query.get_or_404(student_id)

    if not teacher_can_access_student(teacher, student):
        flash('Not authorized to add notes for this student', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    form = NoteForm()

    calendar_periods = CalendarPeriod.query.order_by(CalendarPeriod.start_date.desc()).all()
    school_options = teacher_school_options(teacher.id)

    cp_q = request.args.get('calendar_period_id', type=int)
    st_q = request.args.get('school_term_id', type=int)

    if request.method == 'POST':
        try:
            lesson_track = (request.form.get('lesson_track') or 'private').strip()
            cal_id = request.form.get('calendar_period_id', type=int)
            school_term_id = request.form.get('school_term_id', type=int)
            school_id = request.form.get('school_id', type=int)

            if lesson_track == 'private':
                school_id = None
                school_term_id = None
                if not cal_id:
                    flash('Select a calendar period for private lessons.', 'danger')
                    return render_template(
                        'notes/add_note.html',
                        form=form,
                        student=student,
                        calendar_periods=calendar_periods,
                        school_options=school_options,
                        selected_calendar_id=cal_id,
                        selected_school_term_id=None,
                    )
            else:
                cal_id = None
                if not school_term_id:
                    flash('Select a school term for school lessons.', 'danger')
                    return render_template(
                        'notes/add_note.html',
                        form=form,
                        student=student,
                        calendar_periods=calendar_periods,
                        school_options=school_options,
                        selected_calendar_id=None,
                        selected_school_term_id=school_term_id,
                    )
                term = SchoolTerm.query.get(school_term_id)
                school_id = term.school_id if term else None

            ok_ctx, err_msg = note_context_valid(
                school_id=school_id,
                school_term_id=school_term_id,
                calendar_period_id=cal_id,
                teacher_id=teacher.id,
                student_id=student.id,
            )
            if not ok_ctx:
                flash(err_msg or 'Invalid lesson context.', 'danger')
                return render_template(
                    'notes/add_note.html',
                    form=form,
                    student=student,
                    calendar_periods=calendar_periods,
                    school_options=school_options,
                    selected_calendar_id=cal_id,
                    selected_school_term_id=school_term_id,
                )

            # Use app context explicitly
            with current_app.app_context():
                file_service = FileUploadService(current_app)

                audio_filename = None
                document_filename = None
                image_filename = None

                if 'audio_data' in request.form and request.form['audio_data']:
                    audio_filename = file_service.save_audio(request.form['audio_data'])

                if form.document_file.data:
                    document_filename = file_service.save_uploaded_file(
                        form.document_file.data,
                        file_type='document'
                    )

                if form.image_file.data:
                    image_filename = file_service.save_uploaded_file(
                        form.image_file.data,
                        file_type='image'
                    )

                note = Note(
                    title=form.title.data,
                    content=form.content.data,
                    homework=form.homework.data,
                    audio_filename=audio_filename,
                    document_filename=document_filename,
                    image_filename=image_filename,
                    teacher_id=teacher.id,
                    student_id=student.id,
                    date=datetime.utcnow(),
                    school_id=school_id,
                    school_term_id=school_term_id,
                    calendar_period_id=cal_id,
                )

                db.session.add(note)
                db.session.commit()

            flash('Note saved successfully with all attachments!', 'success')
            return redirect(url_for('notes.student_notes', student_id=student_id))

        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving note: {str(e)}', 'danger')
    return render_template(
        'notes/add_note.html',
        form=form,
        student=student,
        calendar_periods=calendar_periods,
        school_options=school_options,
        selected_calendar_id=cp_q,
        selected_school_term_id=st_q,
    )


@notes_bp.route('/note/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    if current_user.role != 'teacher':
        flash('Only teachers can edit notes', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    note = Note.query.get_or_404(note_id)
    teacher = current_user.teacher_profile

    if note.teacher_id != teacher.id:
        flash('Not authorized to edit this note', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    form = NoteForm(obj=note)

    if form.validate_on_submit():
        try:
            note.title = form.title.data
            note.content = form.content.data
            note.homework = form.homework.data

            # Handle new PDF upload
            if form.document_file.data:
                from services import FileUploadService
                file_service = FileUploadService(current_app)
                document_filename = file_service.save_uploaded_file(form.document_file.data)

                # Delete old PDF if exists
                if note.document_filename:
                    old_document = os.path.join(current_app.config['DOCUMENT_UPLOAD_FOLDER'],
                                           note.document_filename)
                    if os.path.exists(old_document):
                        os.remove(old_document)

                note.document_filename = document_filename

            db.session.commit()
            flash('Note updated successfully!', 'success')
            return redirect(url_for('notes.view_note', note_id=note_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating note: {str(e)}', 'danger')

    return render_template('notes/edit_note.html', form=form, note=note)


@notes_bp.route('/note/<int:note_id>')
@login_required
def view_note(note_id):
    note = Note.query.get_or_404(note_id)

    # Authorization check
    if current_user.role == 'teacher':
        if note.teacher_id != current_user.teacher_profile.id:
            flash('Not authorized to view this note', 'danger')
            return redirect(url_for('dashboard.dashboard'))

    elif current_user.role == 'hod':
        if not hod_can_view_note(current_user, note):
            flash('Not authorized to view this note', 'danger')
            return redirect(url_for('goals.hod_dashboard'))

    elif current_user.role == 'student':
        if note.student_id != current_user.student_profile.id:
            flash('Not authorized to view this note', 'danger')
            return redirect(url_for('dashboard.dashboard'))

    elif current_user.role == 'parent':
        parent = current_user.parent_profile
        student = note.student
        if student not in parent.children:
            flash('Not authorized to view this note', 'danger')
            return redirect(url_for('dashboard.dashboard'))

    return render_template('notes/view_note.html', note=note)


@notes_bp.route('/note/<int:note_id>/sign', methods=['GET', 'POST'])
@login_required
def sign_note(note_id):
    if current_user.role != 'student':
        flash('Only students can sign notes', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    note = Note.query.get_or_404(note_id)
    student = current_user.student_profile

    if note.student_id != student.id:
        flash('Not authorized to sign this note', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    # Check if already signed
    if note.signature:
        flash('This note has already been signed', 'info')
        return redirect(url_for('notes.view_note', note_id=note_id))

    form = SignatureForm()

    if request.method == 'POST':
        signature_data = request.form.get('signature')
        if not signature_data:
            flash('Signature is required', 'danger')
            return redirect(url_for('notes.sign_note', note_id=note_id))

        try:
            # Create signature
            signature = NoteSignature(
                note_id=note.id,
                student_id=student.id,
                signature_data=signature_data,
                ip_address=request.remote_addr
            )

            db.session.add(signature)
            db.session.commit()

            flash('Note signed successfully!', 'success')
            return redirect(url_for('notes.view_note', note_id=note_id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving signature: {str(e)}")
            flash('Error saving signature. Please try again.', 'danger')

    return render_template('notes/sign_note.html', note=note, form=form)


# API Routes for audio processing
@notes_bp.route('/api/save_audio', methods=['POST'])
@login_required
def save_audio():
    if 'audio_data' not in request.form:
        return jsonify({'success': False, 'error': 'No audio data provided'})

    try:
        # Use the existing FileUploadService instead of AudioProcessor
        file_service = current_app.file_upload_service  # Use the service attached to app
        filename = file_service.save_audio(request.form['audio_data'])
        # from services import AudioProcessor
        # audio_processor = AudioProcessor(current_app)
        # filename = audio_processor.save_audio(request.form['audio_data'])
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        current_app.logger.error(f"Error saving audio: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


# Additional Routes for Admin Functions
@auth_bp.route('/admin/manage_users')
@login_required
def manage_users():
    if current_user.role != 'teacher':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    teachers = Teacher.query.all()
    students = Student.query.all()
    parents = Parent.query.all()

    return render_template('admin/manage_users.html',
                           teachers=teachers,
                           students=students,
                           parents=parents)


# Student Search and Management API Routes
@notes_bp.route('/api/students/search', methods=['GET'])
@login_required
def search_students():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    search_term = request.args.get('q', '').strip()

    if not search_term or len(search_term) < 2:
        return jsonify({'success': False, 'error': 'Search term too short'})

    try:
        # Search for students not already assigned to this teacher
        teacher = current_user.teacher_profile

        # Get students that match search term
        search_pattern = f'%{search_term}%'

        # Query for students matching search term
        matching_students = Student.query.join(User).filter(
            or_(
                User.full_name.ilike(search_pattern),
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern)
            ),
            User.role == 'student'
        ).all()

        # Filter out students already assigned to this teacher
        available_students = []
        for student in matching_students:
            if student not in teacher.students:
                student_data = {
                    'id': student.id,
                    'username': student.user.username,
                    'email': student.user.email,
                    'full_name': student.user.full_name,
                    'phone': student.user.phone,
                    'grade_level': student.grade_level,
                    'date_of_birth': str(student.date_of_birth) if student.date_of_birth else None
                }
                available_students.append(student_data)

        return jsonify({
            'success': True,
            'students': available_students,
            'count': len(available_students)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@notes_bp.route('/api/students/add', methods=['POST'])
@login_required
def add_student_to_teacher():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    try:
        data = request.get_json()
        student_id = data.get('student_id')

        if not student_id:
            return jsonify({'success': False, 'error': 'Student ID is required'})

        teacher = current_user.teacher_profile
        student = Student.query.get_or_404(student_id)

        # Check if student is already assigned
        if student in teacher.students:
            return jsonify({'success': False, 'error': 'Student is already in your class'})

        # Add student to teacher
        teacher.students.append(student)
        db.session.commit()

        # Prepare response data
        student_data = {
            'id': student.id,
            'username': student.user.username,
            'full_name': student.user.full_name,
            'email': student.user.email
        }

        return jsonify({
            'success': True,
            'message': f'Student {student.user.full_name} added successfully',
            'student': student_data
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@notes_bp.route('/api/students/add_by_username', methods=['POST'])
@login_required
def add_student_by_username():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    try:
        data = request.get_json()
        username = data.get('username')

        if not username:
            return jsonify({'success': False, 'error': 'Username is required'})

        # Find student by username
        student_user = User.query.filter_by(username=username, role='student').first()
        if not student_user:
            return jsonify({'success': False, 'error': 'Student not found'})

        student = student_user.student_profile
        teacher = current_user.teacher_profile

        # Check if student is already assigned
        if student in teacher.students:
            return jsonify({'success': False, 'error': 'Student is already in your class'})

        # Add student to teacher
        teacher.students.append(student)
        db.session.commit()

        # Prepare response data
        student_data = {
            'id': student.id,
            'username': student.user.username,
            'full_name': student.user.full_name,
            'email': student.user.email
        }

        return jsonify({
            'success': True,
            'message': f'Student {student.user.full_name} added successfully',
            'student': student_data
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@notes_bp.route('/api/students/<int:student_id>/remove', methods=['POST'])
@login_required
def remove_student_from_teacher(student_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    try:
        teacher = current_user.teacher_profile
        student = Student.query.get_or_404(student_id)

        # Check if student is assigned to this teacher
        if student not in teacher.students:
            return jsonify({'success': False, 'error': 'Student not in your class'})

        # Remove student from teacher
        teacher.students.remove(student)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Student {student.user.full_name} removed successfully'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@notes_bp.route('/api/dashboard/stats')
@login_required
def get_dashboard_stats():
    if current_user.role == 'teacher':
        teacher = current_user.teacher_profile
        n_students = len(teacher_accessible_student_ids(teacher))

        # Count notes
        total_notes = Note.query.filter_by(teacher_id=teacher.id).count()
        signed_notes = Note.query.join(NoteSignature).filter(Note.teacher_id == teacher.id).count()

        return jsonify({
            'success': True,
            'stats': {
                'total_students': n_students,
                'total_notes': total_notes,
                'signed_notes': signed_notes,
                'pending_notes': total_notes - signed_notes
            }
        })

    return jsonify({'success': False, 'error': 'Invalid user role'}), 400


# Add to routes.py
@notes_bp.route('/api/note/<int:note_id>/signature')
@login_required
def get_note_signature(note_id):
    note = Note.query.get_or_404(note_id)

    # Authorization check
    if current_user.role == 'teacher':
        if note.teacher_id != current_user.teacher_profile.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    elif current_user.role == 'hod':
        if not hod_can_view_note(current_user, note):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    elif current_user.role == 'student':
        if note.student_id != current_user.student_profile.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    elif current_user.role == 'parent':
        parent = current_user.parent_profile
        if note.student not in parent.children:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    if not note.signature:
        return jsonify({'success': False, 'error': 'No signature'}), 404

    return jsonify({
        'success': True,
        'signature': note.signature.signature_data,
        'student_name': note.student.user.full_name,
        'signed_at': note.signature.signed_at.isoformat()
    })


@notes_bp.route('/api/student/<int:student_id>/request_signatures', methods=['POST'])
@login_required
def request_signatures(student_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    teacher = current_user.teacher_profile
    student = Student.query.get_or_404(student_id)

    if not teacher_can_access_student(teacher, student):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    # Get unsigned notes
    unsigned_notes = Note.query.filter_by(
        student_id=student_id,
        teacher_id=teacher.id
    ).filter(~Note.signature.has()).all()

    if not unsigned_notes:
        return jsonify({'success': False, 'error': 'No unsigned notes'})

    # Here you would typically send email notifications
    # For now, we'll just return a success message

    return jsonify({
        'success': True,
        'message': f'Signature request sent for {len(unsigned_notes)} note(s)',
        'count': len(unsigned_notes)
    })


# Add these routes to routes.py

@notes_bp.route('/note/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    if current_user.role != 'teacher':
        flash('Only teachers can delete notes', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    note = Note.query.get_or_404(note_id)

    if note.teacher_id != current_user.teacher_profile.id:
        flash('Not authorized to delete this note', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    try:
        # Delete associated files
        if note.audio_filename:
            audio_path = os.path.join(current_app.config['AUDIO_UPLOAD_FOLDER'], note.audio_filename)
            if os.path.exists(audio_path):
                os.remove(audio_path)

        if note.document_filename:
            document_path = os.path.join(current_app.config['PDF_UPLOAD_FOLDER'], note.document_filename)
            if os.path.exists(document_path):
                os.remove(document_path)

        # Delete from database
        db.session.delete(note)
        db.session.commit()

        flash('Note deleted successfully', 'success')
        return redirect(url_for('notes.student_notes', student_id=note.student_id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting note: {str(e)}', 'danger')
        return redirect(url_for('notes.view_note', note_id=note_id))


@notes_bp.route('/note/<int:note_id>/delete_audio', methods=['POST'])
@login_required
def delete_audio(note_id):
    if current_user.role != 'teacher':
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    note = Note.query.get_or_404(note_id)

    if note.teacher_id != current_user.teacher_profile.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    try:
        if note.audio_filename:
            audio_path = os.path.join(current_app.config['AUDIO_UPLOAD_FOLDER'], note.audio_filename)
            if os.path.exists(audio_path):
                os.remove(audio_path)

            note.audio_filename = None
            db.session.commit()
            flash('Audio recording deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting audio: {str(e)}', 'danger')

    return redirect(url_for('notes.edit_note', note_id=note_id))


@notes_bp.route('/note/<int:note_id>/delete_pdf', methods=['POST'])
@login_required
def delete_pdf(note_id):
    if current_user.role != 'teacher':
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    note = Note.query.get_or_404(note_id)

    if note.teacher_id != current_user.teacher_profile.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard.dashboard'))

    try:
        if note.pdf_filename:
            pdf_path = os.path.join(current_app.config['PDF_UPLOAD_FOLDER'], note.pdf_filename)
            if os.path.exists(pdf_path):
                os.remove(pdf_path)

            note.pdf_filename = None
            db.session.commit()
            flash('PDF attachment deleted', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting PDF: {str(e)}', 'danger')

    return redirect(url_for('notes.edit_note', note_id=note_id))


@notes_bp.route('/api/student/<int:student_id>/parents')
@login_required
def get_student_parents(student_id):
    student = Student.query.get_or_404(student_id)

    # Authorization check
    if current_user.role == 'teacher':
        if not teacher_can_access_student(current_user.teacher_profile, student):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    elif current_user.role == 'student':
        if student.id != current_user.student_profile.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    elif current_user.role == 'parent':
        if student not in current_user.parent_profile.children:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    parents = []
    for parent in student.parents:
        parents.append({
            'id': parent.id,
            'full_name': parent.user.full_name,
            'email': parent.user.email,
            'relationship': parent.relationship
        })

    return jsonify({
        'success': True,
        'parents': parents
    })


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile settings"""
    if request.method == 'POST':
        # Handle profile updates here
        current_user.full_name = request.form.get('full_name', current_user.full_name)
        current_user.email = request.form.get('email', current_user.email)
        current_user.phone = request.form.get('phone', current_user.phone)

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')


@notes_bp.route('/api/note/<int:note_id>/share', methods=['POST'])
@login_required
def share_note(note_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    note = Note.query.get_or_404(note_id)

    if note.teacher_id != current_user.teacher_profile.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    data = request.get_json()
    parent_id = data.get('parent_id')
    message = data.get('message', '')

    if not parent_id:
        return jsonify({'success': False, 'error': 'Parent ID required'})

    parent = Parent.query.get(parent_id)
    if not parent:
        return jsonify({'success': False, 'error': 'Parent not found'})

    # Check if parent has access to this student
    if note.student not in parent.children:
        return jsonify({'success': False, 'error': 'Parent does not have access to this student'})

    # Here you would typically send an email notification
    # For now, we'll just return success

    return jsonify({
        'success': True,
        'message': f'Note shared with {parent.user.full_name}'
    })


('/health')
def health():
    return()

# Error handlers
@auth_bp.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@auth_bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500