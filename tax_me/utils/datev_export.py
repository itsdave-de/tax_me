import csv
import io

import frappe
from frappe.utils import now_datetime


def generate_datev_buchungsstapel(company: str, from_date: str, to_date: str,
                                  export_type: str = "Purchase Invoices",
                                  export_name: str | None = None) -> str:
    """Erzeugt eine DATEV-Buchungsstapel-CSV für den gegebenen Zeitraum.

    Gibt die file_url des erzeugten File-Docs zurück.
    """

    # 1) Datenquelle: erst einmal nur Purchase Invoices
    invoices = frappe.get_all(
        "Purchase Invoice",
        filters={
            "docstatus": 1,
            "company": company,
            "posting_date": ["between", [from_date, to_date]],
        },
        fields=[
            "name",
            "posting_date",
            "bill_date",
            "supplier",
            "bill_no",
            "company",
            "base_net_total",
            "base_total_taxes_and_charges",
            "base_grand_total",
            "custom_datev_account", 
        ],
        order_by="posting_date asc, name asc",
        limit_page_length=10000,
    )

    # Supplier-Daten (USt-ID, Land, etc.) sammeln
    supplier_names = list({r["supplier"] for r in invoices if r.get("supplier")})
    supplier_map: dict[str, dict] = {}

    if supplier_names:
        suppliers = frappe.get_all(
            "Supplier",
            filters={"name": ["in", supplier_names]},
            fields=["name", "tax_id", "country"],
        )
        for s in suppliers:
            supplier_map[s["name"]] = s

    # 2) CSV im Speicher erzeugen
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")

    # 2.1 DATEV-Kopfzeile (Dummywerte – später mit Steuerberater abstimmen)
    # Format: DTVF;700;21;Buchungsstapel;...
    export_timestamp = now_datetime().strftime("%Y%m%d%H%M%S")
    writer.writerow([
        "DTVF",                # Kennung
        "700",                 # Versionsnummer
        "21",                  # Format-Variante
        "Buchungsstapel",      # Datenart
        company,               # Mandant / frei nutzbar
        export_timestamp,      # Erstellungsdatum/-zeit
        "", "", "", "", "",    # Restliche Felder der Kopfzeile vorerst leer
        "", "", "", "", "",
        "", "", "", "", "",
        "", "", "", "", "",
    ])

    # 2.2 Spaltenüberschriften – vereinfacht; später an Musterdatei anpassen
    header = [
        "Umsatz (ohne Soll/Haben-Kz)",      # 1
        "Soll/Haben-Kennzeichen",           # 2
        "Konto",                            # 3
        "Gegenkonto (ohne BU-Schlüssel)",   # 4
        "BU-Schlüssel",                     # 5
        "Belegdatum",                       # 6
        "Belegfeld 1",                      # 7
        "Belegfeld 2",                      # 8
        "Buchungstext",                     # 9
        "EU-Land u. UStID (Ursprung)",      # ...
        "Land",
        # … hier kannst du später alle restlichen DATEV-Spalten auffüllen,
        # bis du auf deine 100+ Spalten aus der Musterdatei kommst.
    ]
    writer.writerow(header)

    # 2.3 Buchungszeilen: zunächst 1 Zeile pro Rechnung (später feiner)
    for inv in invoices:
        sup = supplier_map.get(inv.get("supplier")) or {}
        supplier_country = sup.get("country")
        supplier_vat_id = sup.get("tax_id")

        amount_raw = float(inv.get("base_grand_total") or 0)

        # Soll/Haben-Logik nach DATEV:
        # positive Rechnung → Haben
        # negative Rechnung (Gutschrift) → Soll
        if amount_raw >= 0:
            soll_haben = "H"
            amount = amount_raw
        else:
            soll_haben = "S"
            amount = abs(amount_raw)

        konto = "1600"             # Kreditorenkonto SKR04

        # Standard-Gegenkonto: Wareneingang 19% Vorsteuer (SKR04: 5400)
        standard_gegenkonto = "5400"

        # Custom-Konto aus der Purchase Invoice (Data-Feld oder später Link)
        datev_account = (inv.get("custom_datev_account") or "").strip()

        # Wenn custom gesetzt → nehmen, sonst Default 5400
        gegenkonto = datev_account if datev_account else standard_gegenkonto

        # Steuerbetrag
        steuer = float(inv.get("base_total_taxes_and_charges") or 0)

        # BU-Schlüssel: "9" wenn Steuer > 0, sonst leer
        bu_key = "9" if steuer != 0 else ""



        belegdatum = inv.get("bill_date") or inv.get("posting_date")
        belegdatum_str = belegdatum.strftime("%d%m%Y") if belegdatum else ""

        row = [
            _amount_to_datev_str(amount),             # Umsatz
            soll_haben,                              # Soll/Haben
            konto,                                   # Konto
            gegenkonto,                              # Gegenkonto
            bu_key,                                  # BU-Schlüssel
            belegdatum_str,                          # Belegdatum
            inv.get("bill_no") or "",                # Belegfeld 1
            inv.get("name") or "",                   # Belegfeld 2
            _build_booking_text(inv, sup),           # Buchungstext
            _build_eu_vat_field(supplier_country, supplier_vat_id),
            supplier_country or "",
            # … restliche Spalten bleiben vorerst leer
        ]

        writer.writerow(row)

    data = buf.getvalue()
    buf.close()

    # 3) Datei in ERPNext speichern
    file_name = f"DATEV_Buchungsstapel_{company}_{from_date or ''}_{to_date or ''}.csv"

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": file_name,
        "content": data,
        "is_private": 1,
        "attached_to_doctype": "DATEV Export",
        "attached_to_name": export_name or "",
    }).insert(ignore_permissions=True)

    return file_doc.file_url



def _amount_to_datev_str(amount: float) -> str:
    """DATEV will typischerweise Dezimal-Komma, z. B. 1234,56."""
    return f"{amount:.2f}".replace(".", ",")


def _build_booking_text(inv: dict, supplier: dict) -> str:
    parts: list[str] = []
    if inv.get("bill_no"):
        parts.append("Re-Nr. " + inv["bill_no"])
    if inv.get("supplier"):
        parts.append("Lieferant: " + inv["supplier"])
    if inv.get("bill_date"):
        parts.append("Re-Datum: " + str(inv["bill_date"]))
    return " | ".join(parts)


def _build_eu_vat_field(country: str | None, vat_id: str | None) -> str:
    """Platzhalter für EU-Land + UStID – später für Amazon/eBay verfeinern."""
    if not country or not vat_id:
        return ""
    # Wenn VAT schon mit Ländercode beginnt, so lassen, sonst präfixen:
    if vat_id.upper().startswith(country.upper()):
        return vat_id
    return country.upper() + vat_id
