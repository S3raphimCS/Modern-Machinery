"""Корневая схема URL проекта."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import healthcheck
from apps.leads.views import lead_attachment
from apps.seo.sitemaps import SITEMAPS
from apps.seo.views import robots_txt

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthcheck, name="healthcheck"),
    # Файлы заявок отдаются только сотрудникам, публичного адреса у них нет.
    path("zayavki/vlozhenie/<int:pk>/", lead_attachment, name="lead-attachment"),
    # API
    path("api/v1/", include("config.api_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # SEO
    path(
        "sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="django.contrib.sitemaps.views.sitemap"
    ),
    path("robots.txt", robots_txt, name="robots"),
    # Публичные разделы. ЧПУ на латинице — под региональные геозапросы.
    path("zapchasti/", include("apps.parts.urls", namespace="parts")),
    path("uslugi/", include("apps.services.urls", namespace="services")),
    path("lizing/", include("apps.financing.urls", namespace="financing")),
    path("dostavka/", include("apps.company.urls", namespace="company")),
    # Каталог техники смонтирован в корень: он же главная страница сайта,
    # а карточки живут на /tehnika/<slug>/.
    path("", include("apps.catalog.urls", namespace="catalog")),
    # Контент подключается последним: у него есть перехватывающий маршрут
    # произвольных страниц, который иначе съел бы разделы выше.
    path("", include("apps.content.urls", namespace="content")),
]

if settings.DEBUG:  # pragma: no cover
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar
    except ImportError:
        pass
    else:
        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
