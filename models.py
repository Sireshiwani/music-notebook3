import os
from datetime import datetime
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import uuid
from services import FileUploadService

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'teacher', 'student', 'parent', 'hod'
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False, cascade='all, delete-orphan')
    student_profile = db.relationship('Student', backref='user', uselist=False, cascade='all, delete-orphan')
    parent_profile = db.relationship('Parent', backref='user', uselist=False, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Teacher(db.Model):
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    qualifications = db.Column(db.Text)
    subjects = db.Column(db.String(200))

    # Relationships
    students = db.relationship('Student', secondary='teacher_student', back_populates='teachers')
    notes = db.relationship('Note', back_populates='teacher', cascade='all, delete-orphan')


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date)
    grade_level = db.Column(db.String(20))

    # Relationships
    teachers = db.relationship('Teacher', secondary='teacher_student', back_populates='students')
    parents = db.relationship('Parent', secondary='student_parent', back_populates='children')
    notes = db.relationship('Note', back_populates='student', cascade='all, delete-orphan')
    signatures = db.relationship('NoteSignature', back_populates='student', cascade='all, delete-orphan')


class Parent(db.Model):
    __tablename__ = 'parents'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    occupation = db.Column(db.String(100))
    relationship = db.Column(db.String(50))  # 'mother', 'father', 'guardian'

    # Relationships
    children = db.relationship('Student', secondary='student_parent', back_populates='parents')


# Association Tables
teacher_student = db.Table('teacher_student',
                           db.Column('teacher_id', db.Integer, db.ForeignKey('teachers.id'), primary_key=True),
                           db.Column('student_id', db.Integer, db.ForeignKey('students.id'), primary_key=True),
                           db.Column('assigned_date', db.DateTime, default=datetime.utcnow)
                           )

student_parent = db.Table('student_parent',
                          db.Column('student_id', db.Integer, db.ForeignKey('students.id'), primary_key=True),
                          db.Column('parent_id', db.Integer, db.ForeignKey('parents.id'), primary_key=True),
                          db.Column('relationship_type', db.String(50))
                          )


class Note(db.Model):
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    homework = db.Column(db.Text)

    # File attachments
    audio_filename = db.Column(db.String(200))
    document_filename = db.Column(db.String(200))
    image_filename = db.Column(db.String(200))

    # Metadata
    file_size = db.Column(db.Integer)  # Total size in bytes
    file_count = db.Column(db.Integer, default=0)  # Number of attachments

    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Period / school context (nullable for legacy rows; new notes should set one track)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)
    school_term_id = db.Column(db.Integer, db.ForeignKey('school_terms.id'), nullable=True)
    calendar_period_id = db.Column(db.Integer, db.ForeignKey('calendar_periods.id'), nullable=True)

    # Foreign Keys
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

    # Relationships
    teacher = db.relationship('Teacher', back_populates='notes')
    student = db.relationship('Student', back_populates='notes')
    school = db.relationship('School', backref='notes')
    school_term = db.relationship('SchoolTerm', backref='notes')
    calendar_period = db.relationship('CalendarPeriod', backref='notes')
    signature = db.relationship('NoteSignature', back_populates='note', uselist=False, cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Calculate file size and count after files are set
        self._calculate_file_info()

    def _calculate_file_info(self):
        """Calculate total file size and count"""
        total_size = 0
        count = 0

        file_service = FileUploadService(current_app) if current_app else None

        if self.audio_filename and file_service:
            path = file_service.get_file_path(self.audio_filename)
            if path and os.path.exists(path):
                total_size += os.path.getsize(path)
                count += 1

        if self.document_filename and file_service:
            path = file_service.get_file_path(self.document_filename)
            if path and os.path.exists(path):
                total_size += os.path.getsize(path)
                count += 1

        if self.image_filename and file_service:
            path = file_service.get_file_path(self.image_filename)
            if path and os.path.exists(path):
                total_size += os.path.getsize(path)
                count += 1

        self.file_size = total_size
        self.file_count = count

    def get_attachments(self):
        """Get all attachments as a list"""
        attachments = []
        file_service = FileUploadService(current_app) if current_app else None

        if self.audio_filename and file_service:
            attachments.append({
                'type': 'audio',
                'filename': self.audio_filename,
                'url': file_service.get_file_url(self.audio_filename),
                'icon': 'bi-mic'
            })

        if self.document_filename and file_service:
            attachments.append({
                'type': 'document',
                'filename': self.document_filename,
                'url': file_service.get_file_url(self.document_filename),
                'icon': 'bi-file-earmark-text'
            })

        if self.image_filename and file_service:
            attachments.append({
                'type': 'image',
                'filename': self.image_filename,
                'url': file_service.get_file_url(self.image_filename),
                'icon': 'bi-image'
            })

        return attachments

class NoteSignature(db.Model):
    __tablename__ = 'note_signatures'

    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('notes.id'), unique=True, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    signature_data = db.Column(db.Text, nullable=False)  # Base64 encoded signature
    signed_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))

    # Relationships
    note = db.relationship('Note', back_populates='signature')
    student = db.relationship('Student', back_populates='signatures')


# --- Schools, terms, calendar periods, goals (SCHOOLS_SPEC + TERMS_AND_GOALS_SPEC) ---

school_teachers = db.Table(
    'school_teachers',
    db.Column('school_id', db.Integer, db.ForeignKey('schools.id'), primary_key=True),
    db.Column('teacher_id', db.Integer, db.ForeignKey('teachers.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=datetime.utcnow),
)

school_students = db.Table(
    'school_students',
    db.Column('school_id', db.Integer, db.ForeignKey('schools.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('students.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=datetime.utcnow),
)


class School(db.Model):
    __tablename__ = 'schools'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    hod_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    hod = db.relationship('User', foreign_keys=[hod_user_id], backref='managed_schools')
    terms = db.relationship('SchoolTerm', back_populates='school', cascade='all, delete-orphan')
    teachers = db.relationship('Teacher', secondary=school_teachers, backref='schools')
    students = db.relationship('Student', secondary=school_students, backref='schools_enrolled')


class SchoolTerm(db.Model):
    __tablename__ = 'school_terms'

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    school = db.relationship('School', back_populates='terms')


class CalendarPeriod(db.Model):
    __tablename__ = 'calendar_periods'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SchoolAssignment(db.Model):
    """Within a school, which teacher is assigned which student."""
    __tablename__ = 'school_assignments'

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

    school = db.relationship('School', backref='assignments')
    teacher = db.relationship('Teacher', backref='school_assignments')
    student = db.relationship('Student', backref='school_assignments')

    __table_args__ = (
        db.UniqueConstraint('school_id', 'teacher_id', 'student_id', name='uq_school_assignment'),
    )


class StudentGoalSet(db.Model):
    __tablename__ = 'student_goal_sets'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    school_term_id = db.Column(db.Integer, db.ForeignKey('school_terms.id'), nullable=True)
    calendar_period_id = db.Column(db.Integer, db.ForeignKey('calendar_periods.id'), nullable=True)
    scope_key = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('Student', backref='goal_sets')
    teacher = db.relationship('Teacher', backref='goal_sets')
    school_term = db.relationship('SchoolTerm', backref='goal_sets')
    calendar_period = db.relationship('CalendarPeriod', backref='goal_sets')
    rubric_items = db.relationship(
        'GoalRubricItem', back_populates='goal_set', cascade='all, delete-orphan',
        order_by='GoalRubricItem.sort_order',
    )
    audit_entries = db.relationship(
        'GoalAuditEntry', back_populates='goal_set', cascade='all, delete-orphan',
        order_by='GoalAuditEntry.created_at.desc()',
    )

    __table_args__ = (
        db.UniqueConstraint('student_id', 'teacher_id', 'scope_key', name='uq_goal_scope'),
    )

    GOAL_SLOT_COUNT = 5

    def five_slots(self):
        """Fixed slots 0–4 for the 5-tab UI; None means empty slot."""
        by_slot = {}
        for it in self.rubric_items:
            if it.sort_order is not None and 0 <= int(it.sort_order) < self.GOAL_SLOT_COUNT:
                by_slot[int(it.sort_order)] = it
        return [by_slot.get(i) for i in range(self.GOAL_SLOT_COUNT)]


class GoalRubricItem(db.Model):
    __tablename__ = 'goal_rubric_items'

    id = db.Column(db.Integer, primary_key=True)
    goal_set_id = db.Column(db.Integer, db.ForeignKey('student_goal_sets.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    goal_set = db.relationship('StudentGoalSet', back_populates='rubric_items')


class GoalAuditEntry(db.Model):
    __tablename__ = 'goal_audit_entries'

    id = db.Column(db.Integer, primary_key=True)
    goal_set_id = db.Column(db.Integer, db.ForeignKey('student_goal_sets.id'), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(64), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    detail_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    goal_set = db.relationship('StudentGoalSet', back_populates='audit_entries')
    actor = db.relationship('User', backref='goal_audit_actions')