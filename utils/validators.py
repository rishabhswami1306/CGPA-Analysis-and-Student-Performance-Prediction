import re
from marshmallow import Schema, fields, validate, validates, ValidationError, pre_load


def sanitize_nosql_input(data):
    """
    Recursively check and reject any key starting with '$' to prevent NoSQL injection.
    """
    if isinstance(data, dict):
        for k, v in data.items():
            if str(k).startswith("$"):
                raise ValidationError(f"Invalid field name '{k}': keys cannot start with '$'.")
            sanitize_nosql_input(v)
    elif isinstance(data, list):
        for item in data:
            sanitize_nosql_input(item)
    return data


def validate_password_complexity(password: str):
    """Ensure password meets strength criteria: >= 8 chars, 1 uppercase, 1 lowercase, 1 number."""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", password):
        raise ValidationError("Password must contain at least one number.")


class BaseValidatedSchema(Schema):
    """Base schema that rejects NoSQL operators."""
    @pre_load
    def check_nosql_injection(self, data, **kwargs):
        return sanitize_nosql_input(data)


class UserLoginSchema(BaseValidatedSchema):
    email = fields.Email(required=True, error_messages={"required": "Email is required."})
    password = fields.String(required=True, validate=validate.Length(min=1), error_messages={"required": "Password is required."})


ALLOWED_BRANCHES = [
    "CSE-DS", "Computer Science and Engineering (Data Science)", "Computer Science and Engineering(Data Science)",
    "CSE", "IT", "EXTC", "AIDS", "MECH", "CIVIL"
]

class UserRegisterSchema(BaseValidatedSchema):
    prn_roll = fields.String(required=True, validate=validate.Length(min=3, max=30))
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate_password_complexity)
    role = fields.String(required=True, validate=validate.OneOf(["admin", "faculty", "student"]))
    name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    branch = fields.String(required=True, validate=validate.OneOf(ALLOWED_BRANCHES))
    admission_year = fields.Integer(required=True, validate=validate.Range(min=2000, max=2030))
    assigned_subjects = fields.List(fields.String(), required=False, load_default=[])


class UserUpdateSchema(BaseValidatedSchema):
    name = fields.String(validate=validate.Length(min=2, max=100))
    branch = fields.String(validate=validate.OneOf(ALLOWED_BRANCHES))
    assigned_subjects = fields.List(fields.String())
    is_active = fields.Boolean()


class SubjectScoreSchema(BaseValidatedSchema):
    subject_code = fields.String(required=True, validate=validate.Length(min=2, max=20))
    subject_name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    credits = fields.Integer(required=True, validate=validate.Range(min=1, max=6))
    tt1_score = fields.Float(required=True, validate=validate.Range(min=0.0, max=30.0))
    tt2_score = fields.Float(required=True, validate=validate.Range(min=0.0, max=30.0))
    aptitude_score = fields.Float(required=False, load_default=0.0, validate=validate.Range(min=0.0, max=5.0))
    skat_score = fields.Float(required=False, load_default=0.0, validate=validate.Range(min=0.0, max=5.0))
    teacher_assessment_score = fields.Float(required=False, load_default=0.0, validate=validate.Range(min=0.0, max=5.0))
    mock_interview_score = fields.Float(required=False, load_default=0.0, validate=validate.Range(min=0.0, max=5.0))
    presentation_score = fields.Float(required=False, load_default=0.0, validate=validate.Range(min=0.0, max=5.0))
    ese_score = fields.Float(required=True, validate=validate.Range(min=0.0, max=100.0))
    max_ese = fields.Float(required=False, load_default=60.0, validate=validate.Range(min=40.0, max=100.0))


class AcademicRecordCreateSchema(BaseValidatedSchema):
    student_prn = fields.String(required=True, validate=validate.Length(min=3, max=30))
    semester = fields.Integer(required=True, validate=validate.Range(min=1, max=8))
    subjects = fields.List(fields.Nested(SubjectScoreSchema), required=True, validate=validate.Length(min=1))
    attendance_percentage = fields.Float(required=True, validate=validate.Range(min=0.0, max=100.0))
    total_lectures_conducted = fields.Integer(required=False, load_default=100, validate=validate.Range(min=1))
    lectures_attended = fields.Integer(required=False, load_default=75, validate=validate.Range(min=0))


class MarksUpdateSchema(BaseValidatedSchema):
    student_prn = fields.String(required=True)
    semester = fields.Integer(required=True, validate=validate.Range(min=1, max=8))
    subject_code = fields.String(required=True)
    tt1_score = fields.Float(validate=validate.Range(min=0.0, max=30.0))
    tt2_score = fields.Float(validate=validate.Range(min=0.0, max=30.0))
    aptitude_score = fields.Float(validate=validate.Range(min=0.0, max=5.0))
    skat_score = fields.Float(validate=validate.Range(min=0.0, max=5.0))
    teacher_assessment_score = fields.Float(validate=validate.Range(min=0.0, max=5.0))
    mock_interview_score = fields.Float(validate=validate.Range(min=0.0, max=5.0))
    presentation_score = fields.Float(validate=validate.Range(min=0.0, max=5.0))
    ese_score = fields.Float(validate=validate.Range(min=0.0, max=100.0))
    attendance_percentage = fields.Float(validate=validate.Range(min=0.0, max=100.0))


class PasswordResetRequestSchema(BaseValidatedSchema):
    email = fields.Email(required=True)


class PasswordResetSchema(BaseValidatedSchema):
    token = fields.String(required=True)
    new_password = fields.String(required=True, validate=validate_password_complexity)


class ChangePasswordSchema(BaseValidatedSchema):
    old_password = fields.String(required=True)
    new_password = fields.String(required=True, validate=validate_password_complexity)


class WhatIfRequestSchema(BaseValidatedSchema):
    target_cgpa = fields.Float(required=True, validate=validate.Range(min=4.0, max=10.0))
    current_tt1 = fields.Float(required=True, validate=validate.Range(min=0.0, max=30.0))
    current_tt2 = fields.Float(required=True, validate=validate.Range(min=0.0, max=30.0))
    aptitude_score = fields.Float(required=False, load_default=0.0, validate=validate.Range(min=0.0, max=5.0))
    skat_score = fields.Float(required=False, load_default=0.0, validate=validate.Range(min=0.0, max=5.0))
    teacher_assessment_score = fields.Float(required=False, load_default=0.0, validate=validate.Range(min=0.0, max=5.0))
    mock_interview_score = fields.Float(required=False, load_default=0.0, validate=validate.Range(min=0.0, max=5.0))
    presentation_score = fields.Float(required=False, load_default=0.0, validate=validate.Range(min=0.0, max=5.0))
    max_ese = fields.Float(required=False, load_default=60.0, validate=validate.Range(min=40.0, max=100.0))
    subject_credits = fields.Integer(required=False, load_default=4, validate=validate.Range(min=1, max=6))
