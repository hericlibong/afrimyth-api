"""Routes du domaine mythologique."""

from rest_framework.routers import DefaultRouter

from mythology.views import EntityViewSet

router = DefaultRouter()
router.register("entities", EntityViewSet, basename="entity")

urlpatterns = router.urls
