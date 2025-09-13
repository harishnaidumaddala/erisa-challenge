import csv
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from claims.models import Claim

STATUS_MAP = {
    'denied': 'denied', 'deny': 'denied',
    'paid': 'paid',
    'under review': 'review', 'review': 'review', 'in review': 'review'
}

# ---------- helpers ----------
def to_decimal(v, default="0"):
    s = "" if v is None else str(v)
    s = s.replace("$", "").replace(",", "").strip()
    if s == "":
        s = default
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal(default)

def to_date(v):
    s = (v or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognized date: {v!r}")

def normalize_headers(headers):
    return [h.strip().lower() for h in headers]

def get_first(row_dict, *keys):
    for k in keys:
        if k in row_dict and row_dict[k] not in (None, ""):
            return row_dict[k]
    return None

def reader_as_dicts(path: Path, delimiter="|"):
    """
    Robust reader:
    - Always use csv.reader to tolerate header in one cell.
    - Build Dicts from header row (split by delimiter).
    """
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter=delimiter)
        headers = next(r, [])
        # If Excel saved strangely, headers may be a single cell like "a|b|c".
        # csv.reader with delimiter='|' still splits correctly, so headers is fine.
        headers_norm = normalize_headers(headers)
        for row in r:
            # pad/truncate to header length
            if len(row) < len(headers_norm):
                row = row + [""] * (len(headers_norm) - len(row))
            elif len(row) > len(headers_norm):
                # keep extras (we'll join later only for details)
                pass
            yield headers_norm, row

# ---------- command ----------
class Command(BaseCommand):
    help = "Import/merge claims from a pipe-delimited list file and an optional details file"

    def add_arguments(self, parser):
        parser.add_argument("--list", required=True, help="Path to claim_list_data.csv (| delimited)")
        parser.add_argument("--detail", required=False, help="Path to claim_detail_data.csv (| delimited)")

    def handle(self, *args, **opts):
        list_path = Path(opts["list"])
        if not list_path.exists():
            raise CommandError(f"List file not found: {list_path}")

        # details (optional)
        details = {}
        detail_path = opts.get("detail")
        if detail_path:
            detail_path = Path(detail_path)
            if not detail_path.exists():
                raise CommandError(f"Detail file not found: {detail_path}")
            details = self._read_details(detail_path)
            self.stdout.write(self.style.NOTICE(f"Loaded {len(details)} detail rows"))

        # list rows
        list_rows = self._read_list(list_path)
        self.stdout.write(self.style.NOTICE(f"Loaded {len(list_rows)} list rows"))

        created = updated = 0
        for rd in list_rows:
            claim_id = rd["claim_id"]
            status_raw = (rd.get("status") or "review").strip().lower()
            status = STATUS_MAP.get(status_raw, "review")

            d = details.get(str(claim_id)) or details.get(int(claim_id)) or {}
            cpt_codes = d.get("cpt_codes", "")
            denial = d.get("denial_reason", "")

            obj, is_created = Claim.objects.update_or_create(
                claim_id=claim_id,
                defaults={
                    "patient_name": rd.get("patient_name", ""),
                    "billed_amount": to_decimal(rd.get("billed_amount")),
                    "paid_amount": to_decimal(rd.get("paid_amount")),
                    "status": status,
                    "insurer": rd.get("insurer", ""),
                    "discharge_date": to_date(rd.get("discharge_date")),
                    "cpt_codes": cpt_codes,
                    "denial_reason": denial,
                },
            )
            created += int(is_created)
            updated += int(not is_created)

        self.stdout.write(self.style.SUCCESS(f"Imported. Created: {created}, Updated: {updated}"))

    # -------- readers for each file type --------
    def _read_list(self, path: Path):
        """
        Expect columns (aliases accepted):
        - claim_id / Claim ID / claimid / id
        - patient_name / Patient / patient
        - billed_amount / billed / billed amount
        - paid_amount / paid
        - status
        - insurer
        - discharge_date / discharge date
        """
        rows = []
        for headers_norm, row in reader_as_dicts(path, delimiter="|"):
            row_dict = {headers_norm[i]: row[i] if i < len(row) else "" for i in range(len(headers_norm))}
            # normalize values
            claim_id_val = get_first(row_dict, "claim_id", "claim id", "claimid", "claim_no", "id")
            if not claim_id_val:
                continue
            try:
                claim_id = int(str(claim_id_val).strip())
            except ValueError:
                continue

            patient = get_first(row_dict, "patient_name", "patient", "patient name", "name") or ""
            billed = get_first(row_dict, "billed_amount", "billed", "billed amount") or "0"
            paid = get_first(row_dict, "paid_amount", "paid") or "0"
            status = get_first(row_dict, "status") or "review"
            insurer = get_first(row_dict, "insurer", "payer", "insurance", "insurer name") or ""
            discharge = get_first(row_dict, "discharge_date", "discharge date", "date", "service date") or ""

            rows.append({
                "claim_id": claim_id,
                "patient_name": patient,
                "billed_amount": billed,
                "paid_amount": paid,
                "status": status,
                "insurer": insurer,
                "discharge_date": discharge,
            })
        return rows

    def _read_details(self, path: Path):
        """
        detail format (| delimited):
        id | claim_id | denial_reason | cpt_codes | [extra CPT columns...]
        Join columns 4..N as comma-separated CPT codes.
        """
        out = {}
        with path.open(newline="", encoding="utf-8") as f:
            r = csv.reader(f, delimiter="|")
            headers = next(r, [])
            for row in r:
                if not row or len(row) < 2:
                    continue
                claim_id = row[1].strip()
                denial = row[2].strip() if len(row) > 2 else ""
                cpts = [x.strip() for x in row[3:] if x and x.strip()]
                out[claim_id] = {"denial_reason": denial, "cpt_codes": ",".join(cpts)}
        return out
