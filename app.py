from flask import Flask, render_template
from flask_login import LoginManager
from config import Config
from models import db
from routes import auth_bp, notes_bp, dashboard_bp
import os
from flask_wtf import CSRFProtect
from services import FileUploadService


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    csrf = CSRFProtect(app)

    # Initialize extensions
    db.init_app(app)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(dashboard_bp)

    # Custom Jinja2 filter for nl2br
    @app.template_filter('nl2br')
    def nl2br_filter(value):
        """Convert newlines to <br> tags"""
        if not value:
            return ''
        # First escape any HTML, then convert newlines to <br>
        return value.replace('\n', '<br>\n')

    # User loader
    from models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Create tables
    with app.app_context():
        db.create_all()
        Config.init_app(app)

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    app.file_upload_service = FileUploadService(app)

    return app



if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)