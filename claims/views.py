from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone
from .models import Claim, Note
from .forms import NoteForm
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, F, DecimalField, ExpressionWrapper
from django.contrib import messages
from .forms import CsvUploadForm
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path


@login_required
def add_note(request, pk):
    if request.method != 'POST':
        return HttpResponseBadRequest("POST only")
    claim = get_object_or_404(Claim, pk=pk)
    form = NoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.claim = claim
        note.created_by = request.user  # <-- who wrote this note
        note.save()
        html = render_to_string('claims/partials/note_item.html', {'n': note})
        return HttpResponse(html)
    return HttpResponseBadRequest("Invalid")



@staff_member_required
def admin_dashboard(request):
    qs = Claim.objects.all()
    under_expr = ExpressionWrapper(F('billed_amount') - F('paid_amount'),
                                   output_field=DecimalField(max_digits=12, decimal_places=2))
    total = qs.count()
    paid = qs.filter(status=Claim.Status.PAID).count()
    denied = qs.filter(status=Claim.Status.DENIED).count()
    review = qs.filter(status=Claim.Status.UNDER_REVIEW).count()
    avg_under = qs.annotate(u=under_expr).filter(u__gt=0).aggregate(Avg('u'))['u__avg'] or 0

    ctx = {
        'total': total,
        'paid': paid,
        'denied': denied,
        'review': review,         # flagged = under review
        'avg_under': avg_under,
        'top_under': qs.annotate(u=under_expr).filter(u__gt=0).order_by('-u')[:10],
    }
    return render(request, 'claims/admin_dashboard.html', ctx)

def claim_list(request):
    qs = Claim.objects.all().order_by('-discharge_date')
    term = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    insurer = request.GET.get('insurer', '')

    if term:
        qs = qs.filter(
            Q(claim_id__icontains=term) |
            Q(patient_name__icontains=term) |
            Q(insurer__icontains=term)
        )
    if status:
        qs = qs.filter(status=status)
    if insurer:
        qs = qs.filter(insurer__icontains=insurer)

    insurers = Claim.objects.order_by().values_list('insurer', flat=True).distinct()
    ctx = {'claims': qs[:50], 'insurers': insurers, 'term': term, 'status': status, 'insurer_val': insurer}
    return render(request, 'claims/claim_list.html', ctx)

def claim_search(request):
    # returns ONLY the <tbody> rows (HTMX swap)
    qs = Claim.objects.all().order_by('-discharge_date')
    term = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    insurer = request.GET.get('insurer', '')

    if term:
        qs = qs.filter(
            Q(claim_id__icontains=term) |
            Q(patient_name__icontains=term) |
            Q(insurer__icontains=term)
        )
    if status:
        qs = qs.filter(status=status)
    if insurer:
        qs = qs.filter(insurer__icontains=insurer)

    html = render_to_string('claims/partials/claim_rows.html', {'claims': qs[:50]})
    return HttpResponse(html)

def claim_detail(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    form = NoteForm()
    return render(request, 'claims/claim_detail.html', {'claim': claim, 'form': form})

def flag_for_review(request, pk):
    if request.method != 'POST':
        return HttpResponseBadRequest("POST only")
    claim = get_object_or_404(Claim, pk=pk)
    claim.status = Claim.Status.UNDER_REVIEW
    claim.save(update_fields=['status'])
    # return the updated badge snippet
    html = render_to_string('claims/partials/status_badge.html', {'claim': claim})
    return HttpResponse(html)


def generate_report(request, pk):
    """Return a tiny CSV of the selected claim as a demo 'report'."""
    claim = get_object_or_404(Claim, pk=pk)
    response = HttpResponse(content_type='text/csv')
    ts = timezone.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="claim_{claim.claim_id}_{ts}.csv"'
    w = csv.writer(response)
    w.writerow(['Claim ID', 'Patient', 'Insurer', 'Status', 'Billed', 'Paid', 'Discharge', 'CPT Codes', 'Denial Reason'])
    w.writerow([claim.claim_id, claim.patient_name, claim.insurer, claim.get_status_display(),
                claim.billed_amount, claim.paid_amount, claim.discharge_date, claim.cpt_codes, claim.denial_reason])
    return response


from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .forms import CsvUploadForm
from .models import Claim
import csv
from decimal import Decimal
from datetime import datetime


def _to_decimal(val):
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(str(val).strip() or "0")
    except (InvalidOperation, AttributeError):
        return Decimal("0")

def _to_date(val):
    s = (val or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

@staff_member_required
def csv_upload(request):
    """Upload claims from a pipe-delimited CSV file."""
    form = CsvUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if form.is_valid():
            mode = form.cleaned_data["mode"]
            list_file = form.cleaned_data["list_file"]

            # Read as UTF-8 text
            try:
                text = list_file.read().decode("utf-8")
            except Exception:
                return HttpResponseBadRequest("Could not decode file as UTF-8")

            reader = csv.DictReader(text.splitlines(), delimiter="|")

            if mode == "overwrite":
                Claim.objects.all().delete()

            created, updated = 0, 0
            for row in reader:
                claim_id = int(row.get("claim_id", 0))
                defaults = {
                    "patient_name": row.get("patient_name", ""),
                    "billed_amount": Decimal(row.get("billed_amount") or 0),
                    "paid_amount": Decimal(row.get("paid_amount") or 0),
                    "status": row.get("status") or Claim.Status.UNDER_REVIEW,
                    "insurer": row.get("insurer", ""),
                    "discharge_date": datetime.strptime(row.get("discharge_date"), "%Y-%m-%d").date(),
                    "cpt_codes": row.get("cpt_codes", ""),
                    "denial_reason": row.get("denial_reason", ""),
                }
                obj, created_flag = Claim.objects.update_or_create(
                    claim_id=claim_id, defaults=defaults
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1

            messages.success(request, f"Upload complete. Created {created}, Updated {updated}.")
            return redirect("claims:list")

    return render(request, "claims/csv_upload.html", {"form": form})