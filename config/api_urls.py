"""Маршруты публичного API версии 1."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.catalog.api.views import BrandViewSet, CategoryViewSet, MachineTypeViewSet, MachineViewSet
from apps.company.api.views import BranchViewSet
from apps.content.api.views import NewsViewSet, PageViewSet, VacancyViewSet
from apps.leads.api.views import LeadViewSet, TcoViewSet
from apps.parts.api.views import PartCategoryViewSet, PartViewSet
from apps.services.api.views import ServiceCategoryViewSet, ServiceViewSet

router = DefaultRouter()
router.register("machines", MachineViewSet, basename="machine")
router.register("brands", BrandViewSet, basename="brand")
router.register("categories", CategoryViewSet, basename="category")
router.register("machine-types", MachineTypeViewSet, basename="machinetype")
router.register("parts", PartViewSet, basename="part")
router.register("part-categories", PartCategoryViewSet, basename="partcategory")
router.register("services", ServiceViewSet, basename="service")
router.register("service-categories", ServiceCategoryViewSet, basename="servicecategory")
router.register("branches", BranchViewSet, basename="branch")
router.register("pages", PageViewSet, basename="page")
router.register("news", NewsViewSet, basename="news")
router.register("vacancies", VacancyViewSet, basename="vacancy")
router.register("leads", LeadViewSet, basename="lead")
router.register("tco", TcoViewSet, basename="tco")

app_name = "api"

urlpatterns = [
    path("", include(router.urls)),
]
