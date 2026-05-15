"""DocVerify Flask server — CA DL AAMVA Tool"""
import random, string, threading, webbrowser, base64
from datetime import datetime, date
from io import BytesIO
from flask import Flask, request, jsonify, send_from_directory
from aamva_validator import validate_aamva

try:
    from pdf417gen import encode, render_image
    PDF417_OK = True
except ImportError:
    PDF417_OK = False

try:
    from barcode import Code128
    from barcode.writer import ImageWriter
    CODE128_OK = True
except ImportError:
    CODE128_OK = False

import sys, os
_sig_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'signature_gen')
if _sig_path not in sys.path:
    sys.path.insert(0, _sig_path)
try:
    from signature_generator import SignatureGenerator, STYLES
    from export_engine import to_base64_png, to_base64_transparent_png
    SIG_OK = True
except Exception as _sig_err:
    SIG_OK = False

app = Flask(__name__, static_folder="static")
PORT = 5555

def rand_dl():
    L = "ABCDEFGHJKLMNPRSTUVWXY"
    return random.choice(L) + "".join(random.choices(string.digits, k=7))

def rand_inv():
    # CA DCK format (AAMVA v9): 5 digits + 1 uppercase letter + 11 digits = 17 chars
    # Real example: 20311B84189220401
    d5  = "".join(random.choices(string.digits, k=5))
    l1  = random.choice("ABCDEFGHJKLMNPRSTUVWXY")
    d11 = "".join(random.choices(string.digits, k=11))
    return d5 + l1 + d11

def add_yrs(d, n):
    try:    return d.replace(year=d.year+n)
    except: return d.replace(year=d.year+n, day=28)

def pdate(s):
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()

def fmt(d):
    return d.strftime("%m%d%Y")

def fmt_zip(z):
    d = z.replace("-","").replace(" ","")
    return (d[:9] if len(d)>=9 else d).ljust(11)

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/validate", methods=["POST"])
def api_validate():
    raw = request.get_json().get("barcode","").strip()
    if not raw: return jsonify({"error":"empty"}), 400
    raw = raw.replace("\\n","\n").replace("\\r","\r").replace("\\x1e","\x1e")
    r = validate_aamva(raw)
    return jsonify({
        "status":r.overall_status,"confidence":r.confidence,
        "issuer":r.issuer,"aamva_version":r.aamva_version,
        "is_california":r.is_california,"is_expired":r.is_expired,
        "extracted":r.extracted_fields,
        "checks":[{"name":c.name,"passed":c.passed,"detail":c.detail} for c in r.checks],
        "errors":r.errors,"warnings":r.warnings,
    })

@app.route("/api/autofill", methods=["GET"])
def api_autofill():
    names=[("SMITH","JOHN","MICHAEL"),("JOHNSON","SARAH","MARIE"),
           ("DAVIS","ROBERT","JAMES"),("GARCIA","MARIA","ELENA"),
           ("WILSON","DAVID","LEE"),("MARTINEZ","JESSICA","ANN")]
    streets=["1508 CARLISLE AVE","2301 K ST","845 BROADWAY","120 MAIN ST","3300 IMPERIAL AVE"]
    cities=["MODESTO","SACRAMENTO","FRESNO","BAKERSFIELD","STOCKTON"]
    zips=["953540000","958140000","937020000","932010000","952020000"]
    idx=random.randrange(len(streets))
    fam,fst,mid=random.choice(names)
    dob=date(random.randint(1960,2002),random.randint(1,12),random.randint(1,28))
    today=date.today()
    # Issue date: 1-4 years ago, must produce future expiry
    iss_year=today.year-random.randint(1,4)
    iss=date(iss_year,random.randint(1,12),random.randint(1,28))
    # CA real logic: Expiry = DOB month/day + (issue_year + 5)
    # e.g. DOB=11/04/1980, Issue=11/06/2020 → Expiry=11/04/2025
    try:
        exp=date(iss.year+5, dob.month, dob.day)
    except ValueError:
        exp=date(iss.year+5, dob.month, 28)
    # Ensure expiry is in future (if not, push issue year forward)
    if exp <= today:
        try:
            exp=date(today.year+1, dob.month, dob.day)
        except ValueError:
            exp=date(today.year+1, dob.month, 28)
    # Card revision date: fixed 08/29/2017 per user spec
    rev=date(2017,8,29)
    dl=rand_dl(); inv=rand_inv()
    dcf=exp.strftime("%m/%d/%Y")+inv[:13]
    return jsonify({
        "family_name":fam,"first_name":fst,"middle_name":mid,
        "street":streets[idx],"city":cities[idx],"zip_code":zips[idx],
        "sex":str(random.choice([1,2])),
        "height_in":str(random.randint(60,76)),
        "weight_lbs":str(random.randint(110,230)),
        "eye_color":random.choice(["BRO","BLU","GRN","GRY","HAZ","BLK"]),
        "hair_color":random.choice(["BRO","BLK","BLN","GRY","RED","SDY","WHI"]),
        "dob":dob.strftime("%Y-%m-%d"),
        "issue_date":iss.strftime("%Y-%m-%d"),
        "expiry_date":exp.strftime("%Y-%m-%d"),
        "card_revision":rev.strftime("%Y-%m-%d"),
        "dl_number":dl,"inventory_ctrl":inv,"dcf":dcf,
        "dde":"N","ddf":"N","ddg":"N",
        "vehicle_class":"C","restrictions":"NONE","endorsements":"NONE",
        "compliance":"F","organ_donor":"1",
    })

@app.route("/api/generate", methods=["POST"])
def api_generate():
    d=request.get_json()
    try:
        dob=pdate(d["dob"]); iss=pdate(d["issue_date"])
        exp=pdate(d["expiry_date"])
        rev=pdate(d.get("card_revision") or d["issue_date"])
    except Exception as e:
        return jsonify({"error":str(e)}),400

    inv=d.get("inventory_ctrl") or rand_inv()
    dl=d.get("dl_number") or rand_dl()
    family=d.get("family_name","SMITH").upper()
    first=d.get("first_name","JOHN").upper()
    middle=(d.get("middle_name","") or "NONE").upper()
    dde=d.get("dde","N"); ddf=d.get("ddf","N"); ddg=d.get("ddg","N")
    vclass=d.get("vehicle_class","C").upper()
    restr=(d.get("restrictions","") or "NONE").upper()
    endors=(d.get("endorsements","") or "NONE").upper()
    sex=d.get("sex","1")
    h=int(d.get("height_in",68)); w=int(d.get("weight_lbs",160))
    eye=d.get("eye_color","BRO").upper()
    hair=d.get("hair_color","BRO").upper()
    street=d.get("street","").upper()
    city=d.get("city","").upper()
    zipf=fmt_zip(d.get("zip_code","000000000"))
    compl=d.get("compliance","F").upper()
    donor=d.get("organ_donor","1")
    zca=d.get("zca","BLK").upper(); zcb=d.get("zcb","BAL").upper()
    zcc=d.get("zcc","").upper();    zcd=d.get("zcd","").upper()

    dcf=exp.strftime("%m/%d/%Y")+inv[:13]
    daq_line=f"DAQ{dl.upper()}"

    # Exact CA sequence
    dl_fields="\n".join([
        f"DCS{family}",f"DDE{dde}",
        f"DAC{first}", f"DDF{ddf}",
        f"DAD{middle}",f"DDG{ddg}",
        f"DCA{vclass}",f"DCB{restr}",f"DCD{endors}",
        f"DBD{fmt(iss)}",f"DBB{fmt(dob)}",f"DBA{fmt(exp)}",
        f"DBC{sex}",f"DAU{h:03d} IN",f"DAY{eye}",
        f"DAG{street}",f"DAI{city}",f"DAJCA",f"DAK{zipf}",
        f"DCF{dcf}",f"DCGUSA",
        f"DAW{w:03d}",f"DAZ{hair}",
        f"DCK{inv}",f"DDA{compl}",f"DDB{fmt(rev)}",f"DDK{donor}",
    ])
    zc_fields="\n".join([f"ZCA{zca}",f"ZCB{zcb}",f"ZCC{zcc}",f"ZCD{zcd}"])
    dl_content=f"{daq_line}\n{dl_fields}"
    dl_off=41; dl_len=len(dl_content)+2
    zc_off=dl_off+dl_len; zc_len=len(f"ZC{zc_fields}")
    header=(f"ANSI 636014090102"
            f"DL{dl_off:04d}{dl_len:04d}"
            f"ZC{zc_off:04d}{zc_len:04d}"
            f"DL{daq_line}")
    barcode_str=f"@\n\x1e\r{header}\n{dl_fields}\rZC{zc_fields}\r"

    img_b64=None
    if PDF417_OK:
        try:
            from PIL import Image as _PIL_Image
            import numpy as _np
            codes=encode(barcode_str,columns=10,security_level=5)
            image=render_image(codes,scale=4,ratio=3,padding=20)
            img_rgba=image.convert('RGBA')
            arr=_np.array(img_rgba)
            white=(arr[:,:,0]>240)&(arr[:,:,1]>240)&(arr[:,:,2]>240)
            arr[white,3]=0
            buf=BytesIO()
            _PIL_Image.fromarray(arr,'RGBA').save(buf,format="PNG")
            img_b64=base64.b64encode(buf.getvalue()).decode()
        except: pass

    # Generate Code128 barcode for DCK — transparent background
    code128_b64 = None
    if CODE128_OK:
        try:
            from PIL import Image as _PIL_Image
            import numpy as _np
            buf128 = BytesIO()
            Code128(inv, writer=ImageWriter()).write(buf128, options={
                'write_text': True,
                'module_height': 12.0,
                'module_width': 0.8,
                'font_size': 7,
                'text_distance': 2.5,
                'quiet_zone': 5.0,
                'dpi': 200,
            })
            buf128.seek(0)
            img128 = _PIL_Image.open(buf128).convert('RGBA')
            arr128 = _np.array(img128)
            white128 = (arr128[:,:,0]>240) & (arr128[:,:,1]>240) & (arr128[:,:,2]>240)
            arr128[white128, 3] = 0
            out128 = BytesIO()
            _PIL_Image.fromarray(arr128, 'RGBA').save(out128, format='PNG')
            code128_b64 = base64.b64encode(out128.getvalue()).decode()
        except Exception:
            pass

    return jsonify({
        "barcode_str":barcode_str,"dl_number":dl.upper(),
        "expiry":exp.strftime("%m/%d/%Y"),
        "png_b64":img_b64,"pdf417_available":PDF417_OK,
        "code128_b64":code128_b64,"code128_available":CODE128_OK,
    })

@app.route("/api/signature", methods=["POST"])
def api_signature():
    if not SIG_OK:
        return jsonify({"error":"Signature engine not available. pip install opencv-python numpy svgwrite"}), 500
    d = request.get_json()
    name       = (d.get("name") or "").strip()
    style_name = d.get("style", "Executive")
    randomness = float(d.get("randomness", 0.5))
    intensity  = float(d.get("intensity", 0.8))
    paper      = bool(d.get("paper_texture", False))
    if not name:
        return jsonify({"error":"Name is required"}), 400
    try:
        # Each call uses a different random seed → always unique signature
        gen  = SignatureGenerator(style_name, randomness, intensity, seed=None)
        bgr  = gen.generate(name, paper_texture=paper)
        bgra = gen.generate_transparent(name)
        return jsonify({
            "png_b64":         to_base64_png(bgr),
            "transparent_png_b64": to_base64_transparent_png(bgra),
            "style": style_name,
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


def open_browser():
    import time; time.sleep(1.2)
    webbrowser.open(f"http://127.0.0.1:{PORT}")

if __name__=="__main__":
    print(f"\n  DocVerify → http://127.0.0.1:{PORT}")
    print("  এই window বন্ধ করলে server বন্ধ হবে।\n")
    threading.Thread(target=open_browser,daemon=True).start()
    app.run(host="127.0.0.1",port=PORT,debug=False)