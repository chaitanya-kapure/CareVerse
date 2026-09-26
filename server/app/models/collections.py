"""MongoDB collection names and accessors.

CAREVERSE uses five clinical collections (spec section 12) plus
`password_reset_otps`. Anything beyond these belongs inside a document, not
a new collection.

`password_reset_otps` is the one addition to the spec's set. It is not
clinical data -- it holds a short-lived, single-use reset credential with a
TTL index -- and keeping it out of `users` is what allows expired records
to be reclaimed by the database instead of accumulating on the account.
"""

from pymongo.database import Database

USERS = "users"
PATIENT_PROFILES = "patient_profiles"
MEDICAL_DOCUMENTS = "medical_documents"
PATIENT_ACCESS = "patient_access"
PATIENT_SUMMARIES = "patient_summaries"
PASSWORD_RESET_OTPS = "password_reset_otps"

ALL_COLLECTIONS = (
    USERS,
    PATIENT_PROFILES,
    MEDICAL_DOCUMENTS,
    PATIENT_ACCESS,
    PATIENT_SUMMARIES,
    PASSWORD_RESET_OTPS,
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
