"""Служебные представления SEO-слоя."""

from django.http import HttpResponse
from django.views.decorators.cache import cache_control


@cache_control(max_age=60 * 60 * 24)
def robots_txt(request) -> HttpResponse:
    """Отдаёт robots.txt.

    Служебные разделы закрыты, карта сайта указана явно: без неё робот находит
    новые страницы заметно медленнее.
    """
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /healthz/",
        "Disallow: /*?page=",
        "Allow: /",
        "",
        f"Sitemap: {scheme}://{host}/sitemap.xml",
        f"Host: {host}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
