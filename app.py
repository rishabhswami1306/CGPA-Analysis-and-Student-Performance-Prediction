import os
import logging
from flask import Flask, jsonify, render_template, redirect, url_for, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt, get_jwt_identity
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_socketio import SocketIO, join_room, leave_room
from flasgger import Swagger

from config import config_by_name
from utils.db import get_db, get_cache

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

jwt = JWTManager()
bcrypt = Bcrypt()
cors = CORS()
socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
def _get_limiter_storage_uri():
    redis_url = os.getenv("REDIS_URL", "memory://")
    if redis_url.startswith("redis://"):
        try:
            import redis
            r = redis.from_url(redis_url, socket_timeout=1.0)
            r.ping()
            return redis_url
        except Exception:
            logger.warning("Redis not reachable for Flask-Limiter; falling back to in-memory rate limiting ('memory://').")
            return "memory://"
    return redis_url


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["500 per day", "100 per hour"],
    storage_uri=_get_limiter_storage_uri()
)



def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app_config = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(app_config)

    # Initialize Extensions
    jwt.init_app(app)
    bcrypt.init_app(app)
    cors.init_app(app, origins=[app.config.get("CORS_ORIGIN", "*")], supports_credentials=True)
    limiter.init_app(app)
    socketio.init_app(app)

    # Security Headers with Talisman (configured safely for CDNs & Chart.js)
    csp = {
        'default-src': ["'self'", 'https:', 'data:'],
        'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'", 'https://cdn.tailwindcss.com', 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com'],
        'style-src': ["'self'", "'unsafe-inline'", 'https://fonts.googleapis.com', 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com'],
        'font-src': ["'self'", 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
        'img-src': ["'self'", 'data:', 'https:'],
        'connect-src': ["'self'", 'ws:', 'wss:', 'http:', 'https:']
    }
    Talisman(
        app,
        content_security_policy=csp,
        content_security_policy_nonce_in=['script-src'],
        force_https=False,  # Set to False for local demo compatibility
        session_cookie_secure=app.config.get("JWT_COOKIE_SECURE", False)
    )

    # Flasgger Swagger Documentation
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/"
    }
    Swagger(app, config=swagger_config)

    # Connect DB & Indexes
    with app.app_context():
        try:
            get_db(app.config["MONGO_URI"], app.config["MONGO_DB_NAME"])
            get_cache(app.config.get("REDIS_URL"))
        except Exception as e:
            logger.warning(f"Database initialization note: {e}")

    # Register Blueprints
    from routes.auth_routes import auth_bp
    from routes.admin_routes import admin_bp
    from routes.faculty_routes import faculty_bp
    from routes.student_routes import student_bp
    from routes.api_routes import api_bp
    from routes.attendance_routes import attendance_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(attendance_bp)

    # JWT Error Handlers
    @jwt.unauthorized_loader
    def unauthorized_callback(callback):
        if request.headers.get("Accept", "").find("text/html") != -1 or not request.is_json:
            return redirect(url_for("auth.login_view"))
        return jsonify({"error": "Authorization token missing or invalid."}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        if request.headers.get("Accept", "").find("text/html") != -1 or not request.is_json:
            return redirect(url_for("auth.login_view"))
        return jsonify({"error": "Session token has expired. Please refresh or re-login."}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        if request.headers.get("Accept", "").find("text/html") != -1 or not request.is_json:
            return redirect(url_for("auth.login_view"))
        return jsonify({"error": "Invalid authentication token."}), 401

    # Global Route Handlers
    @app.route("/")
    def index():
        try:
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
            if identity:
                claims = get_jwt()
                role = claims.get("role")
                if role == "admin":
                    return redirect(url_for("admin.dashboard_view"))
                elif role == "faculty":
                    return redirect(url_for("faculty.dashboard_view"))
                else:
                    return redirect(url_for("student.dashboard_view"))
        except Exception:
            pass
        return redirect(url_for("auth.login_view"))

    # Generic Error Handlers
    @app.errorhandler(404)
    def not_found_handler(e):
        if request.is_json:
            return jsonify({"error": "Resource not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden_handler(e):
        if request.is_json:
            return jsonify({"error": "Access forbidden"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error_handler(e):
        logger.error(f"Internal Server Error: {e}")
        if request.is_json:
            return jsonify({"error": "Internal Server Error"}), 500
        return render_template("errors/500.html"), 500

    # Global Context Processor for Navigation & User Session
    @app.context_processor
    def inject_current_user():
        try:
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
            if identity:
                claims = get_jwt()
                db = get_db()
                u = db.users.find_one({"prn_roll": identity})
                return {
                    "auth_user": u,
                    "auth_prn": identity,
                    "auth_role": claims.get("role", "student"),
                }
        except Exception:
            pass
        return {"auth_user": None, "auth_prn": None, "auth_role": None}

    return app


# SocketIO Event Handlers
@socketio.on("connect")
def handle_connect():
    logger.info("Real-time WebSocket client connected.")


@socketio.on("join_student_room")
def handle_join_student_room(data):
    prn = data.get("student_prn")
    if prn:
        room = f"student_{prn}"
        join_room(room)
        logger.info(f"Client joined room: {room}")


@socketio.on("leave_student_room")
def handle_leave_student_room(data):
    prn = data.get("student_prn")
    if prn:
        room = f"student_{prn}"
        leave_room(room)
        logger.info(f"Client left room: {room}")


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting Intelligent Academic Analytics Server on port {port}...")
    socketio.run(app, host="0.0.0.0", port=port, debug=True, allow_unsafe_werkzeug=True)

