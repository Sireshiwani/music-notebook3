import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///notebook.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload settings
    UPLOAD_FOLDER = 'static/uploads'
    AUDIO_UPLOAD_FOLDER = 'static/uploads/audio'
    DOCUMENT_UPLOAD_FOLDER = 'static/uploads/documents'
    IMAGE_UPLOAD_FOLDER = 'static/uploads/images'

    # Increased limits
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB total request size

    # Allowed file extensions
    ALLOWED_AUDIO_EXTENSIONS = {'webm', 'mp3', 'wav', 'ogg', 'm4a'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'rtf'}
    ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp'}
    ALLOWED_ALL_EXTENSIONS = ALLOWED_AUDIO_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS

    # Audio compression settings
    AUDIO_COMPRESSION_ENABLED = True
    AUDIO_COMPRESSION_BITRATE = '64k'  # 64kbps for voice recordings
    AUDIO_COMPRESSION_SAMPLE_RATE = 22050  # 22.05kHz for voice

    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)

    # Password reset email settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'shajaraplatform@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'shajaraplatform@gmail.com')
    PASSWORD_RESET_TOKEN_MAX_AGE = int(os.environ.get('PASSWORD_RESET_TOKEN_MAX_AGE', 3600))

    @staticmethod
    def init_app(app):
        # Create upload directories
        directories = [
            Config.UPLOAD_FOLDER,
            Config.AUDIO_UPLOAD_FOLDER,
            Config.DOCUMENT_UPLOAD_FOLDER,
            Config.IMAGE_UPLOAD_FOLDER,
            os.path.join(Config.UPLOAD_FOLDER, 'temp')
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)