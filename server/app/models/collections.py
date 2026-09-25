"""MongoDB collection names and accessors.

CAREVERSE uses exactly five collections (spec section 12). Anything beyond
these belongs inside a document, not in a new collection.
"""

from pymongo.database import Database

USERS = "users"
PATIENT_PROFILES = "patient_profiles"
MEDICAL_DOCUMENTS = "medical_documents"
PATIENT_ACCESS = "patient_access"
PATIENT_SUMMARIES = "patient_summaries"

ALL_COLLECTIONS = (
    USERS,
    PATIENT_PROFILES,
    MEDICAL_DOCUMENTS,
    PATIENT_ACCESS,
    PATIENT_SUMMARIES,
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
