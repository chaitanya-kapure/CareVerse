"""Controller layer.

Handlers live here rather than inline in the router so that each route file
stays a readable table of endpoints, and so the layering matches the spec:

    route  ->  controller  ->  service  ->  model
"""

from app.controllers.auth_controller import AuthController
from app.controllers.health_controller import HealthController

__all__ = ["AuthController", "HealthController"]
