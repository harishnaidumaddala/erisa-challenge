from django.db import models
from django.conf import settings


class Claim(models.Model):
    class Status(models.TextChoices):
        DENIED = "denied", "Denied"
        PAID = "paid", "Paid"
        UNDER_REVIEW = "review", "Under Review"

    claim_id = models.PositiveIntegerField(unique=True)  # e.g., 30001
    patient_name = models.CharField(max_length=120)
    billed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNDER_REVIEW)
    insurer = models.CharField(max_length=120)
    discharge_date = models.DateField()
    cpt_codes = models.CharField(max_length=120, help_text="Comma-separated codes, e.g. 99204,82947,99406")
    denial_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def paid_delta(self):
        return self.paid_amount - self.billed_amount

    def cpt_list(self):
        return [c.strip() for c in self.cpt_codes.split(",") if c.strip()]

    def __str__(self):
        return f"{self.claim_id} - {self.patient_name}"


class Note(models.Model):
    class Kind(models.TextChoices):
        ADMIN = "admin", "Admin Note"
        SYSTEM = "system", "System Flag"

    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='notes')
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.ADMIN)
    body = models.TextField()
    created_by = models.ForeignKey(  # <-- add
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_notes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_kind_display()}: {self.body[:40]}"
