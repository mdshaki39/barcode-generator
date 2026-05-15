#!/usr/bin/env python3
"""
ca_dl_generator.py
------------------
Generates a California Driver's License PDF417 barcode
using the exact AAMVA 2020 sequence from a real CA DL.

Sequence (from real CA document):
  @\n\x1e\r
  ANSI <IIN><aamva_ver><jur_ver><entries>DL<offset1><len1>ZC<offset2><len2>DLDAQB0000000
  DCS<family>
  DDE<truncation>
  DAC<first>
  DDF<truncation>
  DAD<middle>
  DDG<truncation>
  DCA<vehicle_class>
  DCB<restrictions>
  DCD<endorsements>
  DBD<issue_date MMDDYYYY>
  DBB<dob MMDDYYYY>
  DBA<expiry MMDDYYYY>
  DBC<sex>
  DAU<height>
  DAY<eye_color>
  DAG<street>
  DAI<city>
  DAJ<state>
  DAK<zip 11 chars>
  DCF<MM/DD/YYYY+discriminator>
  DCG<country>
  DAW<weight>
  DAZ<hair_color>
  DCK<inventory_ctrl>
  DDA<compliance>
  DDB<card_revision_date MMDDYYYY>
  DDK<organ_donor>
  \r
  ZC<ZCA><ZCB><ZCC><ZCD>\r
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Optional

try:
    from pdf417gen import encode, render_image
    PDF417_AVAILABLE = True
except ImportError:
    PDF417_AVAILABLE = False


# ── CA DL Data Model ───────────────────────────────────────────────────────────
@dataclass
class CADriversLicense:
    # Identity
    family_name:   str = "SMITH"
    first_name:    str = "JOHN"
    middle_name:   str = "MICHAEL"

    # DL Number — CA format: 1 letter + 7 digits
    dl_number:     str = "B1234567"

    # Dates (date objects)
    dob:           date = date(1990, 6, 15)
    issue_date:    date = date(2022, 11, 1)
    expiry_date:   date = date(2027, 11, 1)
    card_revision: date = date(2018, 11, 1)

    # Physical
    sex:           str = "1"       # 1=Male 2=Female 9=Unspecified
    height_in:     int = 68        # inches (e.g. 68 = 5'8")
    weight_lbs:    int = 160
    eye_color:     str = "BRO"     # BLK BLU BRO GRY GRN HAZ MAR PNK DIC UNK
    hair_color:    str = "BRO"     # BLK BLN BRO GRY RED SDY WHI UNK

    # Address
    street:        str = "1508 CARLISLE AVE"
    city:          str = "MODESTO"
    state:         str = "CA"
    zip_code:      str = "953540000"   # 9 digits, no dash

    # License details
    vehicle_class: str = "C"
    restrictions:  str = "NONE"
    endorsements:  str = "NONE"

    # Document metadata
    compliance:    str = "F"       # F=REAL ID, N=Non-compliant, T=Temporary
    organ_donor:   str = "1"       # 1=Yes, 0 or empty=No
    inventory_ctrl:str = "20311B84189220401"

    # CA-specific ZC subfile
    zca:           str = "BLK"     # CA field A (often restriction related)
    zcb:           str = "BAL"     # CA field B
    zcc:           str = ""
    zcd:           str = ""

    # Name truncation indicators (T=truncated, N=not truncated, U=unknown)
    trunc_family:  str = "N"
    trunc_first:   str = "N"
    trunc_middle:  str = "N"


def fmt_date(d: date) -> str:
    """Format date as MMDDYYYY (AAMVA standard)."""
    return d.strftime("%m%d%Y")


def fmt_zip(zip_str: str) -> str:
    """
    Format ZIP to exactly 11 chars as per AAMVA spec:
    5-digit ZIP: pad to 11 with spaces → "953540000  "
    9-digit ZIP: pad to 11 with spaces → "953540000  "
    """
    digits = zip_str.replace("-", "").replace(" ", "")
    if len(digits) <= 5:
        return digits.ljust(11)
    elif len(digits) == 9:
        return digits.ljust(11)
    else:
        return digits[:9].ljust(11)


def build_ca_dl_subfile(dl: CADriversLicense) -> str:
    """
    Build the DL subfile data string.
    Each field is on its own line (\n terminated).
    DAQ is special — it's on the same line as the subfile marker (handled in build_barcode).
    """
    lines = [
        f"DCS{dl.family_name.upper()}",
        f"DDE{dl.trunc_family}",
        f"DAC{dl.first_name.upper()}",
        f"DDF{dl.trunc_first}",
        f"DAD{dl.middle_name.upper()}",
        f"DDG{dl.trunc_middle}",
        f"DCA{dl.vehicle_class}",
        f"DCB{dl.restrictions}",
        f"DCD{dl.endorsements}",
        f"DBD{fmt_date(dl.issue_date)}",
        f"DBB{fmt_date(dl.dob)}",
        f"DBA{fmt_date(dl.expiry_date)}",
        f"DBC{dl.sex}",
        f"DAU{dl.height_in:03d} IN",
        f"DAY{dl.eye_color.upper()}",
        f"DAG{dl.street.upper()}",
        f"DAI{dl.city.upper()}",
        f"DAJ{dl.state.upper()}",
        f"DAK{fmt_zip(dl.zip_code)}",
        f"DCF{dl.expiry_date.strftime('%m/%d/%Y')}{dl.inventory_ctrl[:13]}",
        f"DCGUSA",
        f"DAW{dl.weight_lbs:03d}",
        f"DAZ{dl.hair_color.upper()}",
        f"DCK{dl.inventory_ctrl}",
        f"DDA{dl.compliance}",
        f"DDB{fmt_date(dl.card_revision)}",
        f"DDK{dl.organ_donor}",
    ]
    return "\n".join(lines)


def build_ca_zc_subfile(dl: CADriversLicense) -> str:
    """Build California ZC jurisdiction subfile."""
    lines = [
        f"ZCA{dl.zca}",
        f"ZCB{dl.zcb}",
        f"ZCC{dl.zcc}",
        f"ZCD{dl.zcd}",
    ]
    return "\n".join(lines)


def build_aamva_barcode_string(dl: CADriversLicense) -> str:
    """
    Assemble the full AAMVA PDF417 barcode string for a CA DL.

    Header format:
      ANSI <IIN:6><aamva_ver:2><jur_ver:2><entry_count:2>
           DL<subfile1_offset:4><subfile1_len:4>
           ZC<subfile2_offset:4><subfile2_len:4>
           DL                    ← subfile type marker
           DAQ<dl_number>        ← first field, attached to marker
    """
    dl_subfile_data = build_ca_dl_subfile(dl)
    zc_subfile_data = build_ca_zc_subfile(dl)

    # DAQ line is attached to the DL marker: "DLDAQB1234567"
    daq_line = f"DAQ{dl.dl_number}"

    # Full DL subfile content (everything after the header line)
    dl_content = f"{daq_line}\n{dl_subfile_data}"
    zc_content = zc_subfile_data

    # Calculate lengths and offsets
    # The AAMVA header line itself: "ANSI 636014090102DL<off1><len1>ZC<off2><len2>"
    # Offset is measured from start of data section (after the header line + \r)
    # For simplicity, use the values from the real CA sample:
    # DL offset=0041, DL len=0280, ZC offset=0321, ZC len=0024
    # We'll compute approximate lengths
    dl_content_len  = len(dl_content) + len("DL")   # "DL" subfile marker
    zc_content_len  = len(zc_content) + len("ZC")   # "ZC" subfile marker

    # Fixed offsets matching real CA DL (approximate; scanners parse fields not offsets)
    dl_offset   = 41
    dl_len      = len(dl_content) + 2   # +2 for "DL" marker
    zc_offset   = dl_offset + dl_len
    zc_len      = len(zc_content) + 2   # +2 for "ZC" marker

    header_line = (
        f"ANSI 636014090102"          # IIN=636014, AAMVA v09, jur v01
        f"DL"                          # entry 1 type
        f"{dl_offset:04d}"            # entry 1 offset
        f"{dl_len:04d}"               # entry 1 length
        f"ZC"                          # entry 2 type
        f"{zc_offset:04d}"            # entry 2 offset
        f"{zc_len:04d}"               # entry 2 length
        f"DL"                          # subfile type marker
        f"{daq_line}"                  # DAQ attached to marker
    )

    # Full barcode string
    barcode = (
        "@\n"
        "\x1e\r"
        f"{header_line}\n"
        f"{dl_subfile_data}\r"
        f"ZC{zc_content}\r"
    )

    return barcode


def generate_pdf417_image(barcode_str: str, output_path: str, scale: int = 3) -> str:
    """
    Render barcode string as a PDF417 image (PNG).
    Returns the output path.
    """
    if not PDF417_AVAILABLE:
        raise RuntimeError("pdf417gen not installed. Run: pip install pdf417gen")

    codes = encode(barcode_str, columns=10, security_level=5)
    image = render_image(codes, scale=scale, ratio=3, padding=20)
    image.save(output_path)
    return output_path


def print_barcode_preview(barcode_str: str):
    """Print the raw barcode string in a readable way."""
    print("\n" + "─" * 60)
    print("  RAW BARCODE STRING (for validator testing)")
    print("─" * 60)

    lines = barcode_str.replace('\r', '\\r\r').split('\n')
    for i, line in enumerate(lines):
        display = repr(line)[1:-1]  # strip outer quotes
        if len(display) > 70:
            display = display[:67] + "..."
        print(f"  {i:02d}: {display}")
    print("─" * 60)


def interactive_build() -> CADriversLicense:
    """Interactively build a CA DL data object."""
    C = type('C', (), {
        'CYAN': '\033[96m', 'BOLD': '\033[1m', 'DIM': '\033[2m',
        'RESET': '\033[0m', 'YELLOW': '\033[93m', 'GREEN': '\033[92m'
    })()

    print(f"\n{C.CYAN}{C.BOLD}  Enter CA Driver's License data{C.RESET}")
    print(f"  {C.DIM}Press Enter to keep the default value shown in brackets{C.RESET}\n")

    def ask(prompt, default):
        val = input(f"  {prompt} [{C.YELLOW}{default}{C.RESET}]: ").strip()
        return val.upper() if val else str(default)

    def ask_date(prompt, default: date) -> date:
        default_str = default.strftime("%m/%d/%Y")
        while True:
            val = input(f"  {prompt} (MM/DD/YYYY) [{C.YELLOW}{default_str}{C.RESET}]: ").strip()
            if not val:
                return default
            try:
                return datetime.strptime(val, "%m/%d/%Y").date()
            except ValueError:
                print(f"  {C.YELLOW}  → Use MM/DD/YYYY format{C.RESET}")

    def ask_int(prompt, default: int) -> int:
        while True:
            val = input(f"  {prompt} [{C.YELLOW}{default}{C.RESET}]: ").strip()
            if not val:
                return default
            try:
                return int(val)
            except ValueError:
                print(f"  {C.YELLOW}  → Enter a number{C.RESET}")

    dl = CADriversLicense()

    print(f"  {C.BOLD}── Identity ──{C.RESET}")
    dl.family_name  = ask("Family name", dl.family_name)
    dl.first_name   = ask("First name", dl.first_name)
    dl.middle_name  = ask("Middle name", dl.middle_name)
    dl.dl_number    = ask("DL number (e.g. B1234567)", dl.dl_number)

    print(f"\n  {C.BOLD}── Dates ──{C.RESET}")
    dl.dob          = ask_date("Date of birth", dl.dob)
    dl.issue_date   = ask_date("Issue date", dl.issue_date)
    dl.expiry_date  = ask_date("Expiry date", dl.expiry_date)
    dl.card_revision = ask_date("Card revision date", dl.card_revision)

    print(f"\n  {C.BOLD}── Physical ──{C.RESET}")
    sex_input = ask("Sex (1=Male 2=Female 9=Unspecified)", dl.sex)
    dl.sex       = sex_input if sex_input in ("1", "2", "9") else dl.sex
    dl.height_in = ask_int("Height in inches (e.g. 68 = 5'8\")", dl.height_in)
    dl.weight_lbs= ask_int("Weight in lbs", dl.weight_lbs)
    dl.eye_color = ask("Eye color (BRO/BLU/BLK/GRN/GRY/HAZ)", dl.eye_color)
    dl.hair_color= ask("Hair color (BRO/BLK/BLN/GRY/RED)", dl.hair_color)

    print(f"\n  {C.BOLD}── Address ──{C.RESET}")
    dl.street   = ask("Street address", dl.street)
    dl.city     = ask("City", dl.city)
    dl.zip_code = ask("ZIP (9 digits, no dash)", dl.zip_code)

    print(f"\n  {C.BOLD}── License ──{C.RESET}")
    dl.vehicle_class = ask("Vehicle class (C/A/B/M)", dl.vehicle_class)
    dl.restrictions  = ask("Restrictions (NONE or codes)", dl.restrictions)
    dl.endorsements  = ask("Endorsements (NONE or codes)", dl.endorsements)
    compliance_input = ask("REAL ID compliance (F=REAL ID / N=Non-compliant / T=Temp)", dl.compliance)
    dl.compliance = compliance_input if compliance_input in ("F", "N", "T") else dl.compliance
    dl.organ_donor = ask("Organ donor (1=Yes / 0=No)", dl.organ_donor)

    return dl


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CA DL PDF417 Barcode Generator")
    parser.add_argument("--quick", action="store_true", help="Generate with default sample data (no prompts)")
    parser.add_argument("--image", metavar="PATH", help="Save barcode as PNG image to this path")
    parser.add_argument("--raw",   metavar="PATH", help="Save raw barcode string to this file")
    parser.add_argument("--validate", action="store_true", help="Run validator immediately after generation")
    args = parser.parse_args()

    C = type('C', (), {
        'CYAN': '\033[96m', 'BOLD': '\033[1m', 'DIM': '\033[2m',
        'RESET': '\033[0m', 'GREEN': '\033[92m', 'YELLOW': '\033[93m',
        'RED': '\033[91m', 'GRAY': '\033[90m'
    })()

    print(f"""
{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════════════════╗
║       CA DL PDF417 Generator · AAMVA 2020 Standard      ║
╚══════════════════════════════════════════════════════════╝{C.RESET}""")

    # Build DL data
    if args.quick:
        dl = CADriversLicense()
        print(f"\n  {C.DIM}Using default sample data...{C.RESET}")
    else:
        dl = interactive_build()

    # Generate barcode string
    barcode_str = build_aamva_barcode_string(dl)
    print_barcode_preview(barcode_str)

    # Show summary
    print(f"\n  {C.BOLD}Generated barcode:{C.RESET}")
    print(f"  {C.DIM}Total length:{C.RESET}  {len(barcode_str)} bytes")
    print(f"  {C.DIM}DL Number:{C.RESET}     {dl.dl_number}")
    print(f"  {C.DIM}Name:{C.RESET}          {dl.first_name} {dl.middle_name} {dl.family_name}")
    print(f"  {C.DIM}DOB:{C.RESET}           {dl.dob.strftime('%m/%d/%Y')}")
    print(f"  {C.DIM}Expires:{C.RESET}       {dl.expiry_date.strftime('%m/%d/%Y')}")
    print(f"  {C.DIM}REAL ID:{C.RESET}       {'Yes (F)' if dl.compliance == 'F' else 'No'}")

    # Save raw string
    raw_path = args.raw or "generated_barcode.txt"
    with open(raw_path, "w") as f:
        f.write(barcode_str)
    print(f"\n  {C.GREEN}Raw barcode saved →{C.RESET} {raw_path}")

    # Save image
    img_path = args.image or "generated_barcode.png"
    try:
        generate_pdf417_image(barcode_str, img_path)
        print(f"  {C.GREEN}PNG image saved →{C.RESET}  {img_path}")
    except Exception as e:
        print(f"  {C.YELLOW}PNG not saved: {e}{C.RESET}")

    # Auto-validate
    run_validate = args.validate
    if not args.validate and not args.quick:
        choice = input(f"\n  {C.BOLD}Run validator on this barcode now? (y/n):{C.RESET} ").strip().lower()
        run_validate = (choice == "y")

    if run_validate:
        print(f"\n  {C.DIM}Running AAMVA validator...{C.RESET}\n")
        from aamva_validator import validate_aamva
        from verify import print_report
        report = validate_aamva(barcode_str)
        print_report(report, "generated_barcode")


if __name__ == "__main__":
    main()