from django.contrib import admin
from .models import Claim, Note
from django.http import HttpResponse
import csv
from django.contrib.admin.sites import NotRegistered
from .models import Note

try:
    admin.site.unregister(Note)
except NotRegistered:
    pass

class NoteInline(admin.TabularInline):
    model = Note
    extra = 0
    readonly_fields = ("created_at", "created_by")
    fields = ("kind", "body", "created_by", "created_at")


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = (
        "claim_id", "patient_name", "insurer", "status",
        "billed_amount", "paid_amount", "discharge_date",
    )
    list_filter = ("status", "insurer", "discharge_date")
    search_fields = ("claim_id", "patient_name", "insurer")
    date_hierarchy = "discharge_date"
    ordering = ("-discharge_date", "-claim_id")
    list_per_page = 50
    inlines = [NoteInline]
    readonly_fields = ("created_at",)
    fieldsets = (
        (None, {"fields": ("claim_id", "patient_name", "insurer", "status")}),
        ("Amounts & Dates", {"fields": ("billed_amount", "paid_amount", "discharge_date")}),
        ("Clinical", {"fields": ("cpt_codes", "denial_reason")}),
        ("Meta", {"fields": ("created_at",)}),
    )

    # Bulk export selected claims to CSV
    actions = ["export_selected"]

    def export_selected(self, request, queryset):
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = "attachment; filename=claims_export.csv"
        w = csv.writer(resp)
        w.writerow(["claim_id","patient_name","insurer","status","billed","paid","discharge","cpt_codes","denial"])
        for c in queryset:
            w.writerow([
                c.claim_id, c.patient_name, c.insurer, c.get_status_display(),
                c.billed_amount, c.paid_amount, c.discharge_date, c.cpt_codes, c.denial_reason
            ])
        return resp
    export_selected.short_description = "Export selected claims to CSV"


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("claim", "kind", "created_by", "created_at")
    list_filter = ("kind",)
    search_fields = ("claim__claim_id", "claim__patient_name", "body")


admin.site.site_header = "Claims Admin"
admin.site.site_title = "Claims Admin"
admin.site.index_title = "Administration"
