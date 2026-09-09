import logging
from datetime import datetime, timezone
from flask import request
from utils.db import get_db

logger = logging.getLogger(__name__)


def log_audit_event(actor_prn, actor_role, action, target_student_prn=None, before=None, after=None, details=None):
    """
    Log an auditable administrative or faculty event to MongoDB audit_logs collection.
    
    :param actor_prn: PRN/Roll/Username of the user executing the action
    :param actor_role: Role of the actor ('admin', 'faculty', 'system')
    :param action: Action string, e.g., 'EDIT_MARKS', 'BULK_UPLOAD', 'RESET_PASSWORD'
    :param target_student_prn: Target student's PRN if applicable
    :param before: Dict representing the state before change
    :param after: Dict representing the state after change
    :param details: Optional additional context string or dict
    """
    try:
        db = get_db()
        client_ip = request.remote_addr if request else "unknown"
        user_agent = request.user_agent.string if request and hasattr(request, 'user_agent') else "unknown"

        log_entry = {
            "actor_prn": actor_prn,
            "actor_role": actor_role,
            "action": action,
            "target_student_prn": target_student_prn,
            "before": before,
            "after": after,
            "details": details,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "timestamp": datetime.now(timezone.utc)
        }
        db.audit_logs.insert_one(log_entry)
        logger.info(f"Audit Log recorded: [{actor_role}] {actor_prn} -> {action} on {target_student_prn}")
        return True
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
        return False
