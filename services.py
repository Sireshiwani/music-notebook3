import os
import uuid
import base64
import shutil
from datetime import datetime
from werkzeug.utils import secure_filename
from pydub import AudioSegment
import mimetypes
from pathlib import Path
from flask import current_app


class FileUploadService:
    def __init__(self, app):
        self.app = app
        self.logger = app.logger

    def save_audio(self, audio_data, compress=True):
        """Save audio recording with optional compression"""
        try:
            # Validate audio data
            if not audio_data or not isinstance(audio_data, str):
                raise ValueError('Invalid audio data')

            # Check if it's base64 encoded
            if not audio_data.startswith('data:audio/'):
                raise ValueError('Invalid audio format')

            # Extract mime type and base64 data
            header, encoded = audio_data.split(',', 1)
            mime_type = header.split(':')[1].split(';')[0]

            # Decode base64
            audio_bytes = base64.b64decode(encoded)

            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_id = str(uuid.uuid4().hex)[:8]

            # Save original file temporarily
            temp_dir = os.path.join(self.app.config['UPLOAD_FOLDER'], 'temp')
            os.makedirs(temp_dir, exist_ok=True)

            # Determine file extension from mime type
            ext = self._get_extension_from_mime(mime_type) or 'webm'
            temp_filename = f"audio_raw_{timestamp}_{unique_id}.{ext}"
            temp_path = os.path.join(temp_dir, temp_filename)

            # Save raw audio
            with open(temp_path, 'wb') as f:
                f.write(audio_bytes)

            # Compress if enabled and file is large
            final_filename = None
            if compress and self.app.config.get('AUDIO_COMPRESSION_ENABLED', True):
                try:
                    final_filename = self._compress_audio(temp_path, timestamp, unique_id)
                except Exception as e:
                    self.logger.warning(f"Audio compression failed: {str(e)}")
                    final_filename = self._save_as_mp3(temp_path, timestamp, unique_id)
            else:
                final_filename = self._save_as_mp3(temp_path, timestamp, unique_id)

            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

            return final_filename

        except Exception as e:
            self.logger.error(f"Audio save error: {str(e)}")
            raise

    def _compress_audio(self, input_path, timestamp, unique_id):
        """Compress audio file using pydub"""
        try:
            # Load audio file
            sound = AudioSegment.from_file(input_path)

            # Apply compression settings
            sound = sound.set_frame_rate(self.app.config.get('AUDIO_COMPRESSION_SAMPLE_RATE', 22050))
            sound = sound.set_channels(1)  # Convert to mono

            # Export as MP3 with compression
            output_filename = f"audio_{timestamp}_{unique_id}.mp3"
            output_path = os.path.join(self.app.config['AUDIO_UPLOAD_FOLDER'], output_filename)

            sound.export(
                output_path,
                format="mp3",
                bitrate=self.app.config.get('AUDIO_COMPRESSION_BITRATE', '64k'),
                parameters=["-ac", "1"]  # Force mono
            )

            return output_filename

        except Exception as e:
            self.logger.error(f"Audio compression error: {str(e)}")
            raise

    def _save_as_mp3(self, input_path, timestamp, unique_id):
        """Convert any audio file to MP3"""
        try:
            sound = AudioSegment.from_file(input_path)
            output_filename = f"audio_{timestamp}_{unique_id}.mp3"
            output_path = os.path.join(self.app.config['AUDIO_UPLOAD_FOLDER'], output_filename)

            sound.export(output_path, format="mp3", bitrate="128k")
            return output_filename
        except Exception as e:
            # If conversion fails, save as original format
            self.logger.warning(f"MP3 conversion failed: {str(e)}")
            ext = os.path.splitext(input_path)[1][1:] or 'webm'
            output_filename = f"audio_{timestamp}_{unique_id}.{ext}"
            output_path = os.path.join(self.app.config['AUDIO_UPLOAD_FOLDER'], output_filename)
            shutil.copy2(input_path, output_path)
            return output_filename

    def save_uploaded_file(self, file, file_type=None):
        """Save uploaded file (PDF, image, etc.)"""
        if not file or file.filename == '':
            return None

        # Get original filename and extension
        original_filename = secure_filename(file.filename)
        ext = os.path.splitext(original_filename)[1].lower().replace('.', '')

        # Validate file type
        if not self._allowed_file(ext, file_type):
            raise ValueError(f'File type .{ext} not allowed')

        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4().hex)[:8]
        filename = f"{file_type}_{timestamp}_{unique_id}.{ext}"

        # Determine upload directory based on file type
        if ext in self.app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'jpg', 'jpeg', 'png', 'gif', 'bmp'}):
            upload_dir = self.app.config['IMAGE_UPLOAD_FOLDER']
        elif ext in self.app.config.get('ALLOWED_DOCUMENT_EXTENSIONS', {'pdf', 'doc', 'docx', 'txt', 'rtf'}):
            upload_dir = self.app.config['DOCUMENT_UPLOAD_FOLDER']
        else:
            upload_dir = self.app.config['UPLOAD_FOLDER']

        # Create directory if it doesn't exist
        os.makedirs(upload_dir, exist_ok=True)

        # Save file
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        # Note: Image optimization removed since Pillow is not available
        # You can add it back later if you install Pillow

        # Verify file was saved
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            if os.path.exists(filepath):
                os.remove(filepath)
            raise ValueError('File failed to save')

        return filename

    def _allowed_file(self, filename, file_type=None):
        """Check if file extension is allowed"""
        ext = filename.lower() if '.' not in filename else filename.rsplit('.', 1)[1].lower()

        # Get allowed extensions from config with defaults
        allowed_audio = self.app.config.get('ALLOWED_AUDIO_EXTENSIONS', {'webm', 'mp3', 'wav', 'ogg', 'm4a'})
        allowed_docs = self.app.config.get('ALLOWED_DOCUMENT_EXTENSIONS', {'pdf', 'doc', 'docx', 'txt', 'rtf'})
        allowed_images = self.app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'jpg', 'jpeg', 'png', 'gif', 'bmp'})

        if file_type == 'audio':
            return ext in allowed_audio
        elif file_type == 'document':
            return ext in allowed_docs
        elif file_type == 'image':
            return ext in allowed_images
        else:
            return ext in (allowed_audio | allowed_docs | allowed_images)

    def _get_extension_from_mime(self, mime_type):
        """Get file extension from mime type"""
        mime_to_ext = {
            'audio/webm': 'webm',
            'audio/mp3': 'mp3',
            'audio/mpeg': 'mp3',
            'audio/wav': 'wav',
            'audio/x-wav': 'wav',
            'audio/ogg': 'ogg',
            'audio/m4a': 'm4a',
            'audio/x-m4a': 'm4a'
        }
        return mime_to_ext.get(mime_type)

    def get_file_path(self, filename):
        """Get full path for a filename"""
        # Check in all upload directories
        directories = [
            self.app.config['AUDIO_UPLOAD_FOLDER'],
            self.app.config['DOCUMENT_UPLOAD_FOLDER'],
            self.app.config['IMAGE_UPLOAD_FOLDER'],
            self.app.config['UPLOAD_FOLDER']
        ]

        for directory in directories:
            path = os.path.join(directory, filename)
            if os.path.exists(path):
                return path

        return None

    def get_file_url(self, filename):
        """Get URL for a file"""
        if not filename:
            return None

        # Determine file type from extension
        ext = os.path.splitext(filename)[1].lower().replace('.', '')

        allowed_audio = self.app.config.get('ALLOWED_AUDIO_EXTENSIONS', {'webm', 'mp3', 'wav', 'ogg', 'm4a'})
        allowed_images = self.app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'jpg', 'jpeg', 'png', 'gif', 'bmp'})
        allowed_docs = self.app.config.get('ALLOWED_DOCUMENT_EXTENSIONS', {'pdf', 'doc', 'docx', 'txt', 'rtf'})

        if ext in allowed_audio:
            folder = 'audio'
        elif ext in allowed_images:
            folder = 'images'
        elif ext in allowed_docs:
            folder = 'documents'
        else:
            folder = 'uploads'

        return f'/static/uploads/{folder}/{filename}'