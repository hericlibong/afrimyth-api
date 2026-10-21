"""Technical, non-domain views of the project."""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthSerializer(serializers.Serializer[None]):
    """Shape of the health endpoint response.

    Declared only so the schema can describe the response precisely. The view
    builds its payload directly and never uses this class to serialize.
    """

    status = serializers.CharField(help_text="Always `ok` when the process answers.")


class HealthView(APIView):
    """Public health endpoint.

    Does not touch the database: it only reports that the application process
    is answering.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="health_check",
        tags=["service"],
        summary="Service health",
        description=(
            "Reports that the application process is answering. This endpoint "
            "does not query the database, so a successful response says "
            "nothing about database availability. Open to anonymous callers."
        ),
        responses={
            200: OpenApiResponse(
                response=HealthSerializer,
                description="The process is answering.",
                examples=[
                    OpenApiExample(
                        "Healthy", value={"status": "ok"}, response_only=True
                    )
                ],
            )
        },
        # Aucune authentification n'est requise : l'annoncer éviterait à un
        # client de croire qu'il doit s'identifier.
        auth=[],
    )
    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


health = HealthView.as_view()
