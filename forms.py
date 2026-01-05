from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, DateField, SelectField, BooleanField, FileField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Optional
from flask_wtf.file import FileAllowed,FileSize
import re


# Custom email validator
class EmailValidator:
    def __init__(self, message=None):
        if not message:
            message = 'Please enter a valid email address.'
        self.message = message

    def __call__(self, form, field):
        email = field.data
        if email:
            # Simple email regex pattern
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(pattern, email):
                raise ValidationError(self.message)


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')


class StudentRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), EmailValidator()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=120)])
    phone = StringField('Phone Number', validators=[DataRequired()])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    grade_level = StringField('Grade Level')


class ParentRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), EmailValidator()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=120)])
    phone = StringField('Phone Number', validators=[DataRequired()])
    occupation = StringField('Occupation')
    relationship = SelectField('Relationship to Student',
                               choices=[('', 'Select Relationship'),
                                        ('mother', 'Mother'),
                                        ('father', 'Father'),
                                        ('guardian', 'Guardian'),
                                        ('other', 'Other')],
                               validators=[DataRequired()])
    student_username = StringField('Student Username', validators=[DataRequired()])


class TeacherRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), EmailValidator()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=120)])
    phone = StringField('Phone Number', validators=[DataRequired()])
    qualifications = TextAreaField('Qualifications')
    subjects = StringField('Subjects Taught')


class NoteForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=200)])
    content = TextAreaField('Lesson Notes', validators=[DataRequired()])
    homework = TextAreaField('Homework Assignment')

    # File uploads with size limits
    document_file = FileField('Document Attachment', validators=[
        FileAllowed(['pdf', 'doc', 'docx', 'txt', 'rtf'], 'Document files only!'),
        FileSize(max_size=50 * 1024 * 1024, message='File size must be less than 50MB')
    ])

    image_file = FileField('Image Attachment', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'bmp'], 'Image files only!'),
        FileSize(max_size=20 * 1024 * 1024, message='Image size must be less than 20MB')
    ])

class SignatureForm(FlaskForm):
    signature = StringField('Signature', validators=[DataRequired()])
    confirm_accuracy = BooleanField('I confirm this note accurately reflects our lesson',
                                    validators=[DataRequired()])