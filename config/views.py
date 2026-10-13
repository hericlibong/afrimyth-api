"""Vues techniques du projet (non métier)."""

from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Endpoint public de santé.

    Ne touche pas la base de données : il indique seulement que le processus
    applicatif répond.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


health = HealthView.as_view()
