"""Представления заявок: отдача приложенных файлов."""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header

from apps.leads.models import LeadAttachment


def _content_disposition(filename: str) -> str:
    """Заголовок скачивания с именем файла.

    Собирается средствами Django, а не вручную: имя приходит от посетителя, и
    кавычка в нём разорвала бы заголовок на два параметра `filename`. Парсер,
    берущий последний из них, сохранил бы файл под чужим расширением.
    """
    return content_disposition_header(as_attachment=True, filename=filename)


@staff_member_required
@permission_required("leads.view_lead", raise_exception=True)
def lead_attachment(request, pk: int):
    """Отдаёт файл, приложенный к заявке.

    Мало проверить, что человек сотрудник: у контент-менеджера, которому дали
    доступ только к новостям, признак сотрудника тоже стоит — и перебором
    номеров он выкачал бы документы всех клиентов. Поэтому требуется право на
    просмотр заявок: в файлах лежат карточка предприятия, баланс и налоговая
    декларация.

    Когда задан внутренний путь nginx, файл отдаёт он сам по
    `X-Accel-Redirect`: Django проверяет права и освобождает рабочий процесс,
    вместо того чтобы качать многомегабайтный файл через себя.
    """
    attachment = get_object_or_404(LeadAttachment.objects.select_related("lead"), pk=pk)

    internal_url = getattr(settings, "PRIVATE_MEDIA_INTERNAL_URL", "")
    if internal_url:
        response = HttpResponse()
        response["X-Accel-Redirect"] = f"{internal_url.rstrip('/')}/{attachment.file.name}"
        # Content-Type пустой: nginx определит его сам по расширению.
        del response["Content-Type"]
        response["Content-Disposition"] = _content_disposition(attachment.original_name)
        return response

    try:
        handle = attachment.file.open("rb")
    except FileNotFoundError as exc:  # pragma: no cover
        raise Http404("Файл не найден на диске") from exc

    return FileResponse(handle, as_attachment=True, filename=attachment.original_name)
