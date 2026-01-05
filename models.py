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
    role = db.Column(db.String(20), nullable=False)  # 'teacher', 'student', 'parent'
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

    # Foreign Keys
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

    # Relationships
    teacher = db.relationship('Teacher', back_populates='notes')
    student = db.relationship('Student', back_populates='notes')
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