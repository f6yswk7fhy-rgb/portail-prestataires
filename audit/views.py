from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from comptes.roles import Role, role_requis

from .models import EntreeAudit, verifier_chaine


@login_required
@role_requis(Role.RSSI, Role.DSI)
def journal(request):
    page = Paginator(EntreeAudit.objects.select_related("acteur"), 50).get_page(request.GET.get("page"))
    return render(request, "audit/journal.html", {"page": page, "anomalies": verifier_chaine()})
