"""Separate public and private editorial routes for mythology entities."""

from rest_framework.routers import DefaultRouter

from mythology.views import EntityViewSet, PrivateEntityViewSet

router = DefaultRouter()
router.register("entities", EntityViewSet, basename="entity")
router.register("manage/entities", PrivateEntityViewSet, basename="managed-entity")

urlpatterns = router.urls
