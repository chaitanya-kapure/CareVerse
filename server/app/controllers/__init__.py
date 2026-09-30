"""Controller layer.

Handlers live here rather than inline in the router so that each route file
stays a readable table of endpoints, and so the layering matches the spec:

    route  ->  controller  ->  service  ->  model
"""

from app.controllers.access_controller import AccessController
from app.controllers.auth_controller import AuthController
from app.controllers.document_controller import DocumentController
from app.controllers.doctor_controller import DoctorController
from app.controllers.health_controller import HealthController
from app.controllers.patient_controller import PatientController

__all__ = [
    "AccessController",
    "AuthController",
    "DocumentController",
    "DoctorController",
    "HealthController",
    "PatientController",
]
