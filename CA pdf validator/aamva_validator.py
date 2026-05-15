"""
aamva_validator.py
------------------
California DL PDF417 AAMVA format validator.
Based on actual CA DL barcode structure + AAMVA 2020/2025 Annex D.

Actual CA sequence (verified from real document):
  Line 0: @
  Line 1: \x1e
  Line 2: ANSI 636014<aamva_ver><jur_ver><entries>DL<offsets>DLDAQB0000000  ← DAQ attached here
  Line 3+: one field per line (DCS, DDE, DAC, DDF, DAD, DDG, DCA, DCB, DCD,
            DBD, DBB, DBA, DBC, DAU, DAY, DAG, DAI, DAJ, DAK, DCF, DCG,
            DAW, DAZ, DCK, DDA, DDB, DDK)
  ZC subfile: ZCA, ZCB, ZCC, ZCD (California-specific)
"""

import re
from datetime import datetime, date
from dataclasses import dataclass
from typing import Optional


# ── Constants ──────────────────────────────────────────────────────────────────
CA_ISSUER_ID   = "636014"
CA_DL_PATTERN  = re.compile(r'^[A-Z]\d{7}$')  # e.g. B1234567

# AAMVA date format is MMDDCCYY (8 digits), e.g. 06151990
DATE_8         = re.compile(r'^\d{8}$')

# CA-mandatory fields (must be present and non-empty)
CA_MANDATORY = {
    "DAQ": "DL Number",
    "DCS": "Family Name",
    "DAC": "First Name",
    "DCA": "Vehicle Class",
    "DCB": "Restriction Codes",
    "DCD": "Endorsement Codes",
    "DBD": "Issue Date",
    "DBB": "Date of Birth",
    "DBA": "Expiry Date",
    "DBC": "Sex",
    "DAU": "Height",
    "DAY": "Eye Color",
    "DAG": "Street Address",
    "DAI": "City",
    "DAJ": "State",
    "DAK": "Postal Code",
    "DCF": "Document Discriminator",
    "DCG": "Country",
}

VALID_SEX        = {"1", "2", "9"}
VALID_EYE_COLORS = {"BLK","BLU","BRO","GRY","GRN","HAZ","MAR","PNK","DIC","UNK"}
VALID_STATES     = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC","PR","GU","VI","AS","MP"
}
# CA DL compliance type codes
VALID_DDA = {"F", "N", "T"}  # F=REAL ID, N=Non-compliant, T=Temporary


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class ValidationReport:
    overall_status: str       # VALID | WARNING | INVALID
    confidence: int
    issuer: str
    aamva_version: str
    subfile_type: str
    extracted_fields: dict
    checks: list
    errors: list
    warnings: list
    is_california: bool
    is_expired: bool


# ── Parser ─────────────────────────────────────────────────────────────────────
def parse_ca_barcode(raw: str) -> tuple[dict, dict]:
    """
    Parse CA DL PDF417 barcode string.

    Structure:
      @\n\x1e\r
      ANSI <IIN:6><aamva_ver:2><jur_ver:2><entry_count:2>DL<len><offset>...<subfile>DAQ<value>
      DCS<value>
      DAC<value>
      ...
      ZC<subfile fields>

    Returns (header_dict, fields_dict)
    """
    raw = raw.strip()

    if "@" not in raw:
        raise ValueError("Missing '@' start character")
    if "ANSI " not in raw:
        raise ValueError("Missing 'ANSI ' marker")

    # ── Header ──
    ansi_pos = raw.find("ANSI ")
    header_str = raw[ansi_pos + 5:]  # after "ANSI "

    if len(header_str) < 12:
        raise ValueError("Header too short")

    issuer_id      = header_str[0:6]
    aamva_version  = header_str[6:8]
    jur_version    = header_str[8:10]
    entry_count    = header_str[10:12]

    # Subfile type: look for "DL" or "ID" after the numeric entry data
    subfile_match = re.search(r'(DL|ID)(?=[A-Z]{3})', raw)
    subfile_type = subfile_match.group(1) if subfile_match else "UNKNOWN"

    header = {
        "issuer_id":      issuer_id,
        "aamva_version":  aamva_version,
        "jur_version":    jur_version,
        "entry_count":    entry_count,
        "subfile_type":   subfile_type,
    }

    # ── Fields ──
    # Split on \n and \r. Each line = one field (3-char code + value).
    # Exception: the header line ends with <subfile_type>DAQ<value>
    #   e.g. "...DLDAQB0000000" → DAQ = B0000000
    fields = {}
    lines = re.split(r'[\n\r]+', raw)

    for line in lines:
        line = line.strip()
        if not line or len(line) < 4:
            continue

        # Special: header line contains DAQ (and possibly other fields) at the end
        # Pattern: ...DL<3-char-code><value> or ...ID<3-char-code><value>
        m = re.search(r'(?:DL|ID)([A-Z]{2}[A-Z0-9])(.+)$', line)
        if m and "ANSI " in line:
            key   = m.group(1)
            value = m.group(2).strip()
            if key not in fields and value:
                fields[key] = value
            continue

        # Normal field line: first 3 chars = code, rest = value
        key   = line[:3]
        value = line[3:]
        # Valid field codes: 2 uppercase letters + 1 uppercase letter or digit
        if re.match(r'^[A-Z]{2}[A-Z0-9]$', key):
            fields[key] = value.strip()

    return header, fields


def parse_date(s: str) -> Optional[date]:
    """Parse MMDDCCYY (8-digit) → date. Returns None on failure."""
    s = s.strip()
    if not DATE_8.match(s):
        return None
    try:
        return datetime.strptime(s, "%m%d%Y").date()
    except ValueError:
        return None


# ── Validator ──────────────────────────────────────────────────────────────────
def validate_aamva(raw: str) -> ValidationReport:
    today   = date.today()
    checks  = []
    errors  = []
    warnings = []

    # ── Parse ──
    try:
        header, fields = parse_ca_barcode(raw)
    except ValueError as e:
        return ValidationReport(
            overall_status="INVALID", confidence=0,
            issuer="?", aamva_version="?", subfile_type="?",
            extracted_fields={}, checks=[Check("Barcode Parse", False, str(e))],
            errors=[str(e)], warnings=[], is_california=False, is_expired=False,
        )

    def chk(name, passed, detail):
        checks.append(Check(name, passed, detail))
        return passed

    # ── 1. Header ──
    has_ansi = "@" in raw and "ANSI " in raw
    chk("ANSI Header", has_ansi,
        "Valid ANSI header" if has_ansi else "Missing '@' or 'ANSI ' marker")
    if not has_ansi:
        errors.append("ANSI header missing or malformed")

    issuer = header.get("issuer_id", "")
    valid_issuer_fmt = bool(re.match(r'^\d{6}$', issuer))
    chk("Issuer ID Format (6 digits)", valid_issuer_fmt,
        f"Issuer ID: {issuer}" if valid_issuer_fmt else f"Bad issuer: '{issuer}'")
    if not valid_issuer_fmt:
        errors.append(f"Issuer ID '{issuer}' is not 6 digits")

    is_ca = (issuer == CA_ISSUER_ID)
    chk("California Issuer ID (636014)", is_ca,
        "Matches CA DMV (636014)" if is_ca
        else f"Issuer {issuer} is NOT California (expected 636014)")
    if not is_ca:
        warnings.append(f"Issuer {issuer} is not California DMV")

    aamva_ver = header.get("aamva_version", "")
    ver_ok = bool(re.match(r'^\d{2}$', aamva_ver)) and 1 <= int(aamva_ver) <= 12
    chk("AAMVA Version (01–12)", ver_ok,
        f"AAMVA version {aamva_ver}" if ver_ok else f"Invalid version '{aamva_ver}'")
    if not ver_ok:
        errors.append(f"AAMVA version '{aamva_ver}' is out of range")

    subfile = header.get("subfile_type", "?")
    subfile_ok = subfile in ("DL", "ID")
    chk("Subfile Type (DL or ID)", subfile_ok,
        f"Subfile: {subfile}" if subfile_ok else f"Unknown subfile '{subfile}'")
    if not subfile_ok:
        errors.append(f"Subfile type '{subfile}' is not DL or ID")

    # ── 2. Mandatory fields ──
    missing = [f"{c} ({n})" for c, n in CA_MANDATORY.items()
               if c not in fields or not fields[c].strip()]
    mand_ok = len(missing) == 0
    chk("All Mandatory Fields Present", mand_ok,
        "All mandatory CA fields found" if mand_ok
        else "Missing: " + ", ".join(missing))
    if not mand_ok:
        for m in missing:
            errors.append(f"Missing mandatory field: {m}")

    # ── 3. DL number ──
    daq = fields.get("DAQ", "").strip()
    if daq:
        if is_ca:
            dl_ok = bool(CA_DL_PATTERN.match(daq))
            chk("CA DL Number Format (Letter+7 digits)", dl_ok,
                f"'{daq}' ✓" if dl_ok
                else f"'{daq}' — CA requires 1 letter + 7 digits (e.g. B1234567)")
            if not dl_ok:
                errors.append(f"DL number '{daq}' does not match CA format")
        else:
            chk("DL Number Present", True, f"DL#: {daq} (non-CA, format not checked)")

    # ── 4. Dates ──
    is_expired = False

    # Expiry
    dba_raw = fields.get("DBA", "").strip()
    if dba_raw:
        dba_fmt = bool(DATE_8.match(dba_raw))
        dba_date = parse_date(dba_raw) if dba_fmt else None
        chk("Expiry Date Format (MMDDCCYY)", dba_fmt and dba_date is not None,
            f"Expiry: {dba_date.strftime('%m/%d/%Y')}" if dba_date
            else f"Bad expiry date: '{dba_raw}'")
        if dba_date:
            is_expired = dba_date < today
            chk("Not Expired", not is_expired,
                f"Valid until {dba_date.strftime('%m/%d/%Y')}" if not is_expired
                else f"EXPIRED on {dba_date.strftime('%m/%d/%Y')}")
            if is_expired:
                errors.append(f"Document expired on {dba_date.strftime('%m/%d/%Y')}")
        else:
            errors.append(f"Cannot parse expiry date '{dba_raw}'")

    # DOB
    dbb_raw = fields.get("DBB", "").strip()
    dbb_date = None
    if dbb_raw:
        dbb_date = parse_date(dbb_raw)
        chk("Date of Birth Format (MMDDCCYY)", dbb_date is not None,
            f"DOB: {dbb_date.strftime('%m/%d/%Y')}" if dbb_date
            else f"Bad DOB: '{dbb_raw}'")
        if not dbb_date:
            errors.append(f"Cannot parse DOB '{dbb_raw}'")

    # Issue date
    dbd_raw = fields.get("DBD", "").strip()
    dbd_date = None
    if dbd_raw:
        dbd_date = parse_date(dbd_raw)
        future_issue = dbd_date and dbd_date > today
        chk("Issue Date Format (MMDDCCYY)", dbd_date is not None and not future_issue,
            f"Issued: {dbd_date.strftime('%m/%d/%Y')}" if (dbd_date and not future_issue)
            else ("Future issue date — suspicious" if future_issue
                  else f"Bad issue date: '{dbd_raw}'"))
        if future_issue:
            errors.append("Issue date is in the future")
        elif not dbd_date:
            errors.append(f"Cannot parse issue date '{dbd_raw}'")

    # Card revision date (DDB) — optional, validate if present
    ddb_raw = fields.get("DDB", "").strip()
    if ddb_raw:
        ddb_date = parse_date(ddb_raw)
        chk("Card Revision Date Format (DDB)", ddb_date is not None,
            f"Revised: {ddb_date.strftime('%m/%d/%Y')}" if ddb_date
            else f"Bad revision date: '{ddb_raw}'")

    # ── 5. Field value checks ──

    # Sex
    sex = fields.get("DBC", "").strip()
    if sex:
        sex_ok = sex in VALID_SEX
        sex_label = {"1": "Male", "2": "Female", "9": "Unspecified"}.get(sex, sex)
        chk("Sex Code (1/2/9)", sex_ok,
            f"{sex_label} ({sex})" if sex_ok else f"Invalid sex code '{sex}'")
        if not sex_ok:
            errors.append(f"Sex code '{sex}' not valid AAMVA code (1/2/9)")

    # Eye color
    eye = fields.get("DAY", "").strip().upper()
    if eye:
        eye_ok = eye in VALID_EYE_COLORS
        chk("Eye Color Code (DAY)", eye_ok,
            f"Eye color: {eye}" if eye_ok
            else f"'{eye}' not a standard AAMVA eye color code")
        if not eye_ok:
            warnings.append(f"Eye color '{eye}' not in AAMVA standard set")

    # State — must be CA for CA-issued documents
    state = fields.get("DAJ", "").strip().upper()
    if state:
        state_valid = state in VALID_STATES
        chk("State Code (DAJ)", state_valid,
            f"State: {state}" if state_valid else f"Invalid state code '{state}'")
        if is_ca and state != "CA":
            errors.append(f"CA-issued document has non-CA address state '{state}'")
        elif not state_valid:
            errors.append(f"State '{state}' is not a valid US state code")

    # ZIP / postal code — CA format: 9 digits padded to 11 chars with spaces
    zip_raw = fields.get("DAK", "").strip()
    if zip_raw:
        zip_digits = re.sub(r'\s', '', zip_raw)
        zip_ok = bool(re.match(r'^\d{5}(\d{4})?$', zip_digits))
        chk("Postal Code Format (DAK)", zip_ok,
            f"ZIP: {zip_digits}" if zip_ok else f"Bad ZIP '{zip_raw}'")
        if not zip_ok:
            warnings.append(f"Postal code '{zip_raw}' not valid (need 5 or 9 digits)")

    # Height — CA format: "NNN IN" (3 digits + space + IN)
    height = fields.get("DAU", "").strip().upper()
    if height:
        h_ok = bool(re.match(r'^\d{3} (IN|CM)$', height))
        chk("Height Format (DAU)", h_ok,
            f"Height: {height}" if h_ok
            else f"'{height}' — expected '068 IN' or '175 CM'")
        if not h_ok:
            warnings.append(f"Height '{height}' not in expected AAMVA format")

    # Country
    country = fields.get("DCG", "").strip().upper()
    if country:
        c_ok = country in ("USA", "CAN", "MEX")
        chk("Country Code (DCG)", c_ok,
            f"Country: {country}" if c_ok else f"Unexpected country '{country}'")
        if not c_ok:
            warnings.append(f"Country code '{country}' unusual")

    # Document discriminator — CA uses "MM/DD/YYYY..." format
    dcf = fields.get("DCF", "").strip()
    if dcf:
        # CA DCF starts with MM/DD/YYYY (10 chars)
        ca_dcf_ok = bool(re.match(r'^\d{2}/\d{2}/\d{4}', dcf))
        chk("CA Document Discriminator Format (DCF)", ca_dcf_ok,
            f"DCF format OK: {dcf[:10]}..." if ca_dcf_ok
            else f"CA DCF should start with MM/DD/YYYY, got '{dcf[:15]}'")
        if not ca_dcf_ok and is_ca:
            warnings.append(f"CA Document Discriminator format unexpected: '{dcf[:20]}'")

    # REAL ID compliance (DDA field)
    dda = fields.get("DDA", "").strip().upper()
    if dda:
        dda_ok = dda in VALID_DDA
        label = {"F": "REAL ID Compliant (F)", "N": "Non-compliant (N)", "T": "Temporary (T)"}.get(dda, dda)
        chk("REAL ID Compliance (DDA)", dda_ok,
            label if dda_ok else f"Unknown compliance code '{dda}'")
        if not dda_ok:
            warnings.append(f"REAL ID compliance code '{dda}' unrecognized")

    # ZC subfile — California-specific, should be present on CA DLs
    has_zc = any(k.startswith("ZC") for k in fields)
    chk("California ZC Subfile Present", has_zc,
        "CA-specific ZC subfile found" if has_zc
        else "No ZC subfile — expected on CA documents")
    if not has_zc and is_ca:
        warnings.append("California ZC jurisdiction subfile not found")

    # ── 6. Cross-field sanity ──
    dba_date = parse_date(fields.get("DBA", ""))
    if dbb_date and dba_date and dbb_date >= dba_date:
        chk("DOB before Expiry", False, "DOB is on or after expiry — impossible")
        errors.append("DOB is on or after expiry date — data inconsistency")
    elif dbb_date and dba_date:
        chk("DOB before Expiry", True,
            f"DOB {dbb_date.strftime('%m/%d/%Y')} < Expiry {dba_date.strftime('%m/%d/%Y')}")

    if dbd_date and dba_date and dbd_date >= dba_date:
        chk("Issue before Expiry", False, "Issue date is on or after expiry — impossible")
        errors.append("Issue date is on or after expiry date — data inconsistency")
    elif dbd_date and dba_date:
        chk("Issue before Expiry", True, "Issue date is before expiry ✓")

    # ── 7. Score ──
    total   = len(checks)
    passed  = sum(1 for c in checks if c.passed)
    raw_pct = int(passed / total * 100) if total else 0
    confidence = max(0, raw_pct - len(errors) * 6 - len(warnings) * 2)

    if errors:
        status = "INVALID"
    elif warnings:
        status = "WARNING"
    else:
        status = "VALID"

    # ── 8. Human-readable field map ──
    label_map = {
        "DAQ": "DL Number",       "DCS": "Family Name",    "DAC": "First Name",
        "DAD": "Middle Name",     "DBB": "Date of Birth",  "DBA": "Expiry Date",
        "DBD": "Issue Date",      "DDB": "Card Revised",   "DAG": "Street Address",
        "DAI": "City",            "DAJ": "State",          "DAK": "Postal Code",
        "DBC": "Sex",             "DAU": "Height",         "DAY": "Eye Color",
        "DAZ": "Hair Color",      "DAW": "Weight (lbs)",   "DCG": "Country",
        "DCA": "Vehicle Class",   "DCF": "Doc Discriminator", "DCK": "Inventory Ctrl#",
        "DDA": "REAL ID Status",  "DDK": "Organ Donor",
        "ZCA": "CA Field A (ZCA)", "ZCB": "CA Field B (ZCB)",
    }
    extracted = {}
    for code, label in label_map.items():
        val = fields.get(code, "").strip()
        if val:
            if code in ("DBB", "DBA", "DBD", "DDB") and DATE_8.match(val):
                d = parse_date(val)
                val = d.strftime("%m/%d/%Y") if d else val
            if code == "DBC":
                val = {"1": "Male", "2": "Female", "9": "Unspecified"}.get(val, val)
            if code == "DDA":
                val = {"F": "REAL ID Compliant", "N": "Non-compliant", "T": "Temporary"}.get(val, val)
            extracted[label] = val

    return ValidationReport(
        overall_status=status,
        confidence=confidence,
        issuer=issuer,
        aamva_version=aamva_ver,
        subfile_type=subfile,
        extracted_fields=extracted,
        checks=checks,
        errors=errors,
        warnings=warnings,
        is_california=is_ca,
        is_expired=is_expired,
    )