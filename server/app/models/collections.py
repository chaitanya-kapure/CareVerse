"""MongoDB collection names and accessors."""

from pymongo.database import Database

USERS = "users"
PATIENT_PROFILES = "patient_profiles"
MEDICAL_DOCUMENTS = "medical_documents"
PATIENT_ACCESS = "patient_access"
PATIENT_SUMMARIES = "patient_summaries"
PASSWORD_RESET_OTPS = "password_reset_otps"
DOCTOR_PROFILES = "doctor_profiles"
CAREVERSE_IDS = "careverse_ids"
POSTS = "posts"
COMMENTS = "comments"
FOLLOWS = "follows"
CONVERSATIONS = "conversations"
MESSAGES = "messages"
NOTIFICATIONS = "notifications"
ACCESS_REQUESTS = "access_requests"

ALL_COLLECTIONS = (
    USERS,
    PATIENT_PROFILES,
    MEDICAL_DOCUMENTS,
    PATIENT_ACCESS,
    PATIENT_SUMMARIES,
    PASSWORD_RESET_OTPS,
    DOCTOR_PROFILES,
    CAREVERSE_IDS,
    POSTS,
    COMMENTS,
    FOLLOWS,
    CONVERSATIONS,
    MESSAGES,
    NOTIFICATIONS,
    ACCESS_REQUESTS,
)


def get_users(db: Database):
    return db[USERS]


def get_patient_profiles(db: Database):
    return db[PATIENT_PROFILES]


def get_medical_documents(db: Database):
    return db[MEDICAL_DOCUMENTS]


def get_patient_access(db: Database):
    return db[PATIENT_ACCESS]


def get_patient_summaries(db: Database):
    return db[PATIENT_SUMMARIES]


def get_password_reset_otps(db: Database):
    return db[PASSWORD_RESET_OTPS]


def get_doctor_profiles(db: Database):
    return db[DOCTOR_PROFILES]


def get_careverse_ids(db: Database):
    return db[CAREVERSE_IDS]


def get_posts(db: Database):
    return db[POSTS]


def get_comments(db: Database):
    return db[COMMENTS]


def get_follows(db: Database):
    return db[FOLLOWS]


def get_conversations(db: Database):
    return db[CONVERSATIONS]


def get_messages(db: Database):
    return db[MESSAGES]


def get_notifications(db: Database):
    return db[NOTIFICATIONS]


def get_access_requests(db: Database):
    return db[ACCESS_REQUESTS]
