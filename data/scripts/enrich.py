import re, csv, collections, openpyxl, sys, os, json, hashlib, datetime
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as CL
from openpyxl.comments import Comment

# AutoBrain data pipeline. Usage (from repo root):
#   python data/scripts/enrich.py data/master/AutoBrain_EV_Data.xlsx data/releases/<release-name>
# Reads the master spreadsheet's source tabs (Variants, Features, Accessories), rebuilds the decision tabs
# inside the spreadsheet, writes 4 validated CSVs + manifest.json to the release folder, and exits non-zero
# if any validation check fails. Requires Python 3.10+ and openpyxl. Never edit the CSVs by hand.
OUT = sys.argv[1] if len(sys.argv) > 1 else "data/master/AutoBrain_EV_Data.xlsx"
REL = sys.argv[2] if len(sys.argv) > 2 else "data/releases/" + datetime.date.today().isoformat()
os.makedirs(REL, exist_ok=True)
vals = openpyxl.load_workbook(OUT, data_only=True)
wb = openpyxl.load_workbook(OUT)

F_ = "Arial"
HF = Font(name=F_, bold=True, color="FFFFFF"); HFILL = PatternFill("solid", fgColor="1F3A5F")
thin = Side(style="thin", color="BFBFBF"); BRD = Border(left=thin, right=thin, top=thin, bottom=thin)
BLUE = Font(name=F_, color="0000FF"); BLACK = Font(name=F_); YEL = PatternFill("solid", fgColor="FFFF00")

# ---------- read data ----------
V = [r for r in vals["Variants"].iter_rows(min_row=2, values_only=True) if r[0]]
F = collections.defaultdict(dict)
for r in vals["Features"].iter_rows(min_row=2, values_only=True):
    if r[0]: F[r[0]][r[2]] = (r[3], r[6])

def fv(vid, k):
    x = F[vid].get(k); return None if x is None else x[0]
def num(x):
    if x is None: return None
    if isinstance(x, (int, float)): return x
    m = re.search(r"\d+(\.\d+)?", str(x).replace(",", ""))
    return float(m.group()) if m else None
def unknown(x): return x is None or str(x).lower().startswith(("not stated", "not found", "not yet", "check"))

def slug(*p): return "-".join(re.sub(r"[^A-Z0-9]+", "", str(x).upper().replace("+", "PLUS")) for x in p if x not in (None, ""))

rows = []
for r in V:
    vid, brand, model, body, yr, trim, kwh, vname, ptype, price, rng, rstd, src, status = r[:14]
    g = lambda k: fv(vid, k)
    awd = "AWD" if ("QWD" in str(trim) or "AWD" in str(vname)) else ""
    drive_txt = str(g("drive_type") or "")
    drive = "AWD" if awd or "AWD" in drive_txt else ("RWD" if "RWD" in drive_txt else ("FWD" if "FWD" in drive_txt else "Not stated"))
    seat_txt = str(g("seating") or "")
    seats = 6 if "6-seater" in str(vname) else (int(num(seat_txt)) if num(seat_txt) else None)
    seat_opt = "6 or 7" if "captain" in seat_txt and "seater" not in str(vname) else (str(seats) if seats else "Not stated")
    # ADAS / camera / sunroof / ESP / ventilation enums
    a = str(g("adas_level") or "").upper()
    adas = "L2+" if "L2+" in a else ("L2" if "L2" in a else ("None" if a.startswith("NONE") else "Not stated"))
    c = str(g("surround_camera") or "").lower()
    cam = "540°" if "540" in c else ("360°" if "360" in c else ("Rear camera" if "camera" in c else ("Sensors only" if "sensor" in c else "Not stated")))
    sr = str(g("sunroof") or "").lower()
    sun = ("Openable panoramic" if "openable" in sr else "Panoramic" if "panoramic" in sr else "Sunroof" if ("sunroof" in sr or "single pane" in sr)
           else "None" if sr.startswith("none") else "Not stated")
    e = str(g("esp") or "").lower()
    esp = "Yes" if e.startswith("yes") else ("Not listed" if e.startswith("not listed") else "Not stated")
    vt = str(g("ventilated_front_seats") or "").lower()
    vent = "Yes" if vt.startswith("yes") else ("Passive only" if vt.startswith("passive") else ("No" if vt.startswith("no") else "Not stated"))
    asx = str(g("adaptive_suspension") or "").lower()
    adsusp = "Yes" if asx.startswith("yes") else ("No" if asx.startswith("no") else "Not stated")
    # charging
    dckw = num(g("dc_fast_charge_max_kw"))
    win = None
    for k, w in (("dc_charge_time_20_80_min", 0.6), ("dc_charge_time_10_80_min", 0.7), ("dc_charge_time_0_80_min", 0.8)):
        if num(g(k)): win = (num(g(k)), w, k); break
    avg_dc = round(kwh * win[1] / (win[0] / 60), 1) if (win and kwh) else None
    ac7 = num(g("ac_charge_time_0_100_h_7kw"))
    ac_basis = "0-100%"
    if ac7 is None and num(g("ac_charge_time_10_100_h_7kw")):
        ac7 = round(num(g("ac_charge_time_10_100_h_7kw")) / 0.9, 1); ac_basis = "scaled from 10-100%"
    obc = num(g("onboard_ac_charger_kw"))
    # range
    rw = str(g("realworld_range_maker_claim") or "")
    rw_lo = num(rw)
    ind = str(g("realworld_range_independent") or "")
    m = re.search(r"(\d+) km combined", ind)
    if m: tested = int(m.group(1))
    else:
        ns = [int(x) for x in re.findall(r"(\d+) km", ind)]
        tested = round(sum(ns) / len(ns)) if ns else None
    eff_t = num(g("efficiency_km_per_kwh_tested"))
    rtv = g("range_test_vehicle") if (tested or eff_t) else None
    range_test_vehicle = rtv if rtv in ("Same model", "Earlier version") else ("Not tested" if not (tested or eff_t) else "Same model")
    range_test_note = (g("range_test_note") or "") if range_test_vehicle != "Not tested" else ""
    eff_est = round(rw_lo / kwh, 2) if (rw_lo and kwh) else None
    eff = eff_t or eff_est
    eff_basis = "Independent test" if eff_t else ("Maker real-world claim (estimate)" if eff_est else "None")
    # charger
    wci = str(g("wall_charger_included") or "")
    wco = str(g("wall_charger_option") or "")
    if brand == "Mahindra":
        ch_inc, ch_cost, ch_basis = "No", 60000, "7.2 kW wall box ₹60,000 (Mahindra XEV 9e/9S pages)" + ("; BE 6 price assumed same" if model == "BE 6 SPORTEQ" else "")
        if model == "XUV 3XO EV": ch_cost, ch_basis = 60000, "Assumed ₹60,000 (not published for XUV 3XO EV); 6.6 kW onboard charger limits benefit"
    elif "7.2 kw" in wci.lower(): ch_inc, ch_cost, ch_basis = "Yes (7.2 kW)", 0, "Included per Tata"
    elif "3.3 kw" in wci.lower(): ch_inc, ch_cost, ch_basis = "Yes (3.3 kW)", 0, "3.3 kW box included; 7.2 kW optional"
    elif "+₹" in wco: ch_inc, ch_cost, ch_basis = "No", int(num(wco.split("+₹")[1])), "Tata 'ACFC' option price"
    elif "conflicting" in str(F[vid].get("wall_charger_included", ("", ""))[1]): ch_inc, ch_cost, ch_basis = "Unclear", 50000, "Brochure vs website disagree; ₹50,000 assumed"
    else: ch_inc, ch_cost, ch_basis = "Not stated", 50000, "Not stated; ₹50,000 assumed (Tata ACFC price)"
    if model == "Punch.ev": ch_inc, ch_cost, ch_basis = "Yes (3.3 kW)", 0, "3.3 kW wall box included (brochure)"
    # warranty / ncap
    bw = str(g("battery_warranty") or "")
    bwt = "Lifetime (1st owner)" if "lifetime" in bw.lower() else ("8 yrs / 1.6L km" if "8 yr" in bw.lower() else "Not stated")
    na = str(g("bncap_rating_applies") or "")
    ncs = F[vid].get("bncap_rating_applies", (None, ""))[1]
    ncap = ("Not tested" if na.lower().startswith(("not tested", "ev not listed")) else
            "Rated, applies" if ncs == "verified" and num(g("bncap_adult_score")) else "Rated, coverage unconfirmed" if num(g("bncap_adult_score")) else "Not stated")
    adult = num(g("bncap_adult_score")); child = num(g("bncap_child_score"))
    # misc
    terr = num(g("terrain_modes")) if not unknown(g("terrain_modes")) else None
    wading = num(g("water_crossing_guidance")) if "wading depth" in str(g("water_crossing_guidance") or "").lower() else None
    rows.append(dict(
        variant_key=slug(brand, model, trim, kwh, drive if drive == "AWD" else "", "6S" if seats == 6 and "6-seater" in str(vname) else "", "BAAS" if ptype == "BaaS" else ""),
        sheet_id=vid, brand=brand, model=model, body_type=body, variant=vname, pricing_type=ptype,
        price_inr=price, price_status=status, battery_kwh=kwh, drive=drive, seats=seats, seat_options=seat_opt,
        range_claimed_km=rng, range_standard=rstd, range_maker_realworld_km=rw_lo, range_tested_km=tested,
        range_test_vehicle=range_test_vehicle, range_test_note=range_test_note,
        tested_vs_claim_pct=round(tested / rng * 100) if (tested and rng) else None,
        efficiency_km_per_kwh=eff, efficiency_basis=eff_basis,
        boot_l=num(g("boot_space_l")) if not unknown(g("boot_space_l")) else None,
        ground_clearance_mm=num(g("ground_clearance_mm")) if not unknown(g("ground_clearance_mm")) else None,
        battery_clearance_mm=num(g("battery_clearance_mm")) if not unknown(g("battery_clearance_mm")) else None,
        airbags=num(g("airbags")), esp=esp, adas=adas, camera=cam, sunroof=sun, ventilated_front=vent, adaptive_suspension=adsusp,
        dc_max_kw=dckw, dc_avg_kw_est=avg_dc, ac_full_hours_7kw=ac7, ac_hours_basis=ac_basis if ac7 else None, onboard_ac_kw=obc,
        charger_included=ch_inc, charger_cost_inr=ch_cost, charger_basis=ch_basis,
        battery_warranty=bwt, ncap_status=ncap, ncap_adult_32=adult, ncap_child_49=child,
        terrain_modes=int(terr) if terr else None, wading_mm=wading,
        body=body, trim=trim))

# ---------- watch-outs ----------
def watch(d):
    w = []
    if d["esp"] != "Yes": w.append("ESP not listed")
    if d["ncap_status"] == "Not tested": w.append("No Bharat NCAP crash test")
    if d["ncap_status"] == "Rated, coverage unconfirmed": w.append("Crash rating may not cover this version")
    if d["battery_warranty"].startswith("8"): w.append("Battery warranty 8 yrs/1.6L km (not lifetime)")
    if d["range_test_vehicle"] == "Earlier version": w.append("Range/efficiency test was on an earlier version of this car")
    if d["tested_vs_claim_pct"] and d["tested_vs_claim_pct"] < 70: w.append(f"Tested range only {d['tested_vs_claim_pct']}% of claim")
    if d["onboard_ac_kw"] and d["onboard_ac_kw"] < 7: w.append(f"Onboard charger {d['onboard_ac_kw']:g} kW: a 7.2 kW wall box won't charge faster")
    if d["charger_included"] in ("No", "Not stated", "Unclear") and d["pricing_type"] != "BaaS": w.append(f"Wall charger not in price (~₹{d['charger_cost_inr']:,})")
    if d["pricing_type"] == "BaaS": w.append("BaaS: battery paid via separate loan (up to 8 yrs); not pay-per-km")
    if d["price_status"] != "verified": w.append(f"Price {d['price_status']}, confirm before buying")
    if d["dc_avg_kw_est"] and d["dc_avg_kw_est"] < 40: w.append("Slow DC fast-charging")
    if not d["seats"]: w.append("Seating not stated by maker")
    return "; ".join(w) if w else "None flagged"
for d in rows: d["watch_outs"] = watch(d)

# ---------- Assumptions sheet ----------
if "Assumptions" in wb.sheetnames: del wb["Assumptions"]
A = wb.create_sheet("Assumptions", 1)
A.append(["Assumption", "Value", "Unit", "Why this default / source"])
assum = [("Home electricity tariff", 8, "₹/kWh", "Typical Delhi residential slab; change for your city/DISCOM"),
         ("Public DC fast-charging tariff", 22, "₹/kWh", "Typical Indian public DC rate (Tata Power, Statiq, ChargeZone range ~₹18-25); verify locally"),
         ("Share of charging done on public DC", 0.10, "fraction", "Most private owners charge at home"),
         ("Daily driving", 40, "km/day", "Change to buyer's actual use"),
         ("Ownership period", 5, "years", "Typical first-owner horizon"),
         ("Annual electricity price increase", 0.0, "fraction", "Kept 0 for simplicity; not yet used in formulas")]
for a in assum: A.append(list(a))
for c in A[1]: c.font = HF; c.fill = HFILL; c.border = BRD
for r_ in range(2, A.max_row + 1):
    for c in range(1, 5): A.cell(r_, c).border = BRD; A.cell(r_, c).font = BLACK
    A.cell(r_, 2).font = BLUE; A.cell(r_, 2).fill = YEL
A.append([]); A.append(["Edit the yellow cells. Engine_Variants running-cost and 5-year cost columns recalculate from these."])
A.append(["5-year cost INCLUDES: ex-showroom price + home wall charger (if not included) + electricity."])
A.append(["EXCLUDES: registration, insurance, service, tyres, financing, resale value, discounts. Not a full TCO."])
for w_, c in zip((38, 10, 10, 80), "ABCD"): A.column_dimensions[c].width = w_
A.freeze_panes = "A2"

# ---------- Engine_Variants ----------
if "Engine_Variants" in wb.sheetnames: del wb["Engine_Variants"]
E = wb.create_sheet("Engine_Variants", 2)
cols = ["variant_key", "sheet_id", "brand", "model", "body_type", "variant", "pricing_type", "price_inr", "price_status", "battery_kwh", "drive",
        "seats", "seat_options", "range_claimed_km", "range_standard", "range_maker_realworld_km", "range_tested_km", "range_test_vehicle", "range_test_note", "tested_vs_claim_pct",
        "efficiency_km_per_kwh", "efficiency_basis", "running_cost_inr_per_km", "energy_cost_period_inr", "charger_included", "charger_cost_inr",
        "charger_basis", "cost_to_own_period_inr", "boot_l", "ground_clearance_mm", "battery_clearance_mm", "airbags", "esp", "adas", "camera",
        "sunroof", "ventilated_front", "adaptive_suspension", "dc_max_kw", "dc_avg_kw_est", "minutes_dc_per_100km", "ac_full_hours_7kw", "onboard_ac_kw", "battery_warranty",
        "ncap_status", "ncap_adult_32", "ncap_child_49", "terrain_modes", "wading_mm", "watch_outs"]
E.append(cols)
ci = {c: i + 1 for i, c in enumerate(cols)}
L = {c: CL(i) for c, i in ci.items()}
for d in sorted(rows, key=lambda x: (x["brand"], x["model"], x["pricing_type"] != "battery included", x["price_inr"] or 9e9)):
    r_ = E.max_row + 1
    for c in cols:
        if c in ("running_cost_inr_per_km", "energy_cost_period_inr", "cost_to_own_period_inr", "minutes_dc_per_100km"): continue
        E.cell(r_, ci[c], d.get(c))
    eff, rc, en = f"{L['efficiency_km_per_kwh']}{r_}", f"{L['running_cost_inr_per_km']}{r_}", f"{L['energy_cost_period_inr']}{r_}"
    E.cell(r_, ci["running_cost_inr_per_km"], f'=IF({eff}="","",((1-Assumptions!$B$4)*Assumptions!$B$2+Assumptions!$B$4*Assumptions!$B$3)/{eff})')
    E.cell(r_, ci["energy_cost_period_inr"], f'=IF({rc}="","",{rc}*Assumptions!$B$5*365*Assumptions!$B$6)')
    pr, ch, pt = f"{L['price_inr']}{r_}", f"{L['charger_cost_inr']}{r_}", f"{L['pricing_type']}{r_}"
    E.cell(r_, ci["cost_to_own_period_inr"], f'=IF(OR({pt}<>"battery included",{pr}="",{en}=""),"",{pr}+{ch}+{en})')
    av = f"{L['dc_avg_kw_est']}{r_}"
    E.cell(r_, ci["minutes_dc_per_100km"], f'=IF(OR({eff}="",{av}=""),"",100/{eff}/{av}*60)')
for c in E[1]: c.font = HF; c.fill = HFILL; c.border = BRD; c.alignment = Alignment(wrap_text=True, vertical="center")
for row in E.iter_rows(min_row=2):
    for c in row: c.border = BRD; c.font = BLACK
for r_ in range(2, E.max_row + 1):
    for c in ("price_inr", "energy_cost_period_inr", "charger_cost_inr", "cost_to_own_period_inr"): E.cell(r_, ci[c]).number_format = "₹#,##0"
    E.cell(r_, ci["running_cost_inr_per_km"]).number_format = "₹0.00"
    E.cell(r_, ci["minutes_dc_per_100km"]).number_format = "0"
    E.cell(r_, ci["efficiency_km_per_kwh"]).number_format = "0.00"
widths = {"variant_key": 34, "variant": 30, "watch_outs": 90, "charger_basis": 40, "efficiency_basis": 26, "range_standard": 22, "model": 14}
for c, i in ci.items(): E.column_dimensions[CL(i)].width = widths.get(c, 13)
E.row_dimensions[1].height = 45; E.freeze_panes = "G2"; E.auto_filter.ref = f"A1:{CL(len(cols))}{E.max_row}"
E["U1"].comment = Comment("Cost per km = blended tariff (Assumptions) / efficiency. Efficiency = independent test where available, else maker real-world claim (see efficiency_basis).", "AutoBrain")
E["Z1"].comment = Comment("Price + wall charger (if not included) + electricity over the ownership period. Excludes insurance, registration, service, resale. Battery-included rows only.", "AutoBrain")
E["AL1"].comment = Comment("Estimated minutes of DC fast-charging to add 100 km = 100 / efficiency / average DC power. Average DC power derived from maker's charge time and window.", "AutoBrain")

# ---------- Variant_Ladder ----------
if "Variant_Ladder" in wb.sheetnames: del wb["Variant_Ladder"]
LD = wb.create_sheet("Variant_Ladder", 3)
LD.append(["model", "from_variant", "to_variant", "from_price_inr", "to_price_inr", "extra_cost_inr", "what_you_gain", "what_does_not_change", "factory_only_gains", "note"])
CMP = [("battery_kwh", "Battery kWh"), ("range_claimed_km", "Range km"), ("drive", "Drive"), ("seats", "Seats"), ("airbags", "Airbags"), ("esp", "ESP"),
       ("adas", "ADAS"), ("camera", "Camera"), ("sunroof", "Sunroof"), ("ventilated_front", "Vent. seats"), ("terrain_modes", "Terrain modes"),
       ("charger_included", "Charger in box"), ("battery_warranty", "Battery warranty"), ("ncap_status", "Crash test")]
FEAT_X = [("audio", "Audio"), ("screen_setup", "Screens"), ("wheels", "Wheels"), ("hud", "HUD"), ("auto_park_assist", "Auto park"), ("power_tailgate", "Power tailgate"),
          ("upholstery", "Upholstery"), ("climate_control", "Climate"), ("powered_driver_seat_memory", "Powered seat"), ("cruise_control", "Cruise"),
          ("passive_keyless_entry", "Keyless"), ("wireless_charger", "Wireless charger"), ("in_car_app_suite", "App suite"), ("adaptive_suspension", "Adaptive suspension")]
FACTORY_ONLY = {"Battery kWh", "Range km", "Drive", "Airbags", "ESP", "ADAS", "Sunroof", "Vent. seats", "Terrain modes", "HUD", "Adaptive suspension", "Battery warranty", "Seats"}
LADDER = []
bymodel = collections.defaultdict(list)
for d in rows:
    if d["pricing_type"] == "battery included" and d["price_inr"]: bymodel[d["model"]].append(d)
for model in sorted(bymodel):
    lst = sorted(bymodel[model], key=lambda x: x["price_inr"])
    for a, b in zip(lst, lst[1:]):
        gain, same, fo = [], [], []
        for k, lab in CMP:
            va, vb = a.get(k), b.get(k)
            if va != vb: gain.append(f"{lab}: {va} → {vb}"); (fo.append(lab) if lab in FACTORY_ONLY else None)
        for k, lab in FEAT_X:
            va, vb = fv(a["sheet_id"], k), fv(b["sheet_id"], k)
            if va != vb and vb not in (None,):
                gain.append(f"{lab}: {va if va is not None else '—'} → {vb}"); (fo.append(lab) if lab in FACTORY_ONLY else None)
        note = "Same price" if b["price_inr"] == a["price_inr"] else ""
        if b["seats"] == 6 and a["seats"] != 6: note = "Captain-seat version"
        LADDER.append(dict(model=model, from_variant_key=a["variant_key"], to_variant_key=b["variant_key"], from_variant=a["variant"], to_variant=b["variant"],
                           from_price_inr=a["price_inr"], to_price_inr=b["price_inr"], extra_cost_inr=b["price_inr"] - a["price_inr"],
                           what_you_gain="; ".join(gain) if gain else "No difference in tracked fields", factory_only_gains="|".join(sorted(set(fo))), note=note,
                           price_status_from=a["price_status"], price_status_to=b["price_status"]))
        LD.append([model, a["variant"], b["variant"], a["price_inr"], b["price_inr"], None, "; ".join(gain) if gain else "No difference in tracked fields",
                   "", ", ".join(sorted(set(fo))) if fo else "None (accessories may cover some)", note])
        r_ = LD.max_row
        LD.cell(r_, 6, f"=E{r_}-D{r_}")
for c in LD[1]: c.font = HF; c.fill = HFILL; c.border = BRD
for row in LD.iter_rows(min_row=2):
    for c in row: c.border = BRD; c.font = BLACK; c.alignment = Alignment(wrap_text=True, vertical="top")
for r_ in range(2, LD.max_row + 1):
    for c in (4, 5, 6): LD.cell(r_, c).number_format = "₹#,##0"
for w_, c in zip((12, 28, 28, 12, 12, 12, 95, 4, 30, 18), "ABCDEFGHIJ"): LD.column_dimensions[c].width = w_
LD.column_dimensions["H"].hidden = True
LD.freeze_panes = "B2"; LD.auto_filter.ref = f"A1:J{LD.max_row}"

# ---------- Test_Cases (computed at default assumptions) ----------
tariff = (1 - 0.10) * 8 + 0.10 * 22
def cto(d):
    if d["pricing_type"] != "battery included" or not d["price_inr"] or not d["efficiency_km_per_kwh"]: return None
    return d["price_inr"] + d["charger_cost_inr"] + tariff / d["efficiency_km_per_kwh"] * 40 * 365 * 5
P = [("First EV, city commute, tight budget", dict(budget=1000000, seats=4, must=lambda d: True, prefer="cost")),
     ("Family of 5, safety first, ₹16L", dict(budget=1600000, seats=5, must=lambda d: d["esp"] == "Yes" and d["airbags"] and d["airbags"] >= 6 and d["ncap_status"] == "Rated, applies", prefer="cost")),
     ("Long highway trips, ₹25L, wants real range 400+ km", dict(budget=2500000, seats=5, must=lambda d: (d["range_tested_km"] or 0) >= 400 or (d["range_maker_realworld_km"] or 0) >= 450, prefer="range")),
     ("Big family, 7 seats, ₹27L", dict(budget=2700000, seats=7, must=lambda d: True, prefer="cost")),
     ("Weekend off-road / bad roads, ₹27L", dict(budget=2700000, seats=5, must=lambda d: d["drive"] == "AWD" or (d["terrain_modes"] or 0) >= 4, prefer="cost")),
     ("Wants ADAS + 360 camera, ₹18L", dict(budget=1800000, seats=5, must=lambda d: d["adas"] in ("L2", "L2+") and d["camera"] in ("360°", "540°"), prefer="cost"))]
if "Test_Cases" in wb.sheetnames: del wb["Test_Cases"]
TC = wb.create_sheet("Test_Cases", 4)
TC.append(["buyer_profile", "rank", "variant", "price_inr", f"5yr_cost_inr (40 km/day, ₹{tariff:.1f}/kWh)", "why_it_fits", "watch_outs", "cheaper_alternative_note"])
for name, p in P:
    pool = [d for d in rows if d["pricing_type"] == "battery included" and d["price_inr"] and d["price_inr"] <= p["budget"]
            and (d["seats"] or 5) >= p["seats"] and p["must"](d)]
    if p["prefer"] == "range":
        pool.sort(key=lambda d: (0 if d["range_tested_km"] else 1, -((d["range_tested_km"] or d["range_maker_realworld_km"] or 0))))
    else:
        pool.sort(key=lambda d: (cto(d) or d["price_inr"] * 1.2))
    if not pool:
        TC.append([name, "-", "No match in Mahindra/Tata within budget", None, None, "Engine should say so plainly and show nearest option above budget", "", ""]); continue
    top = pool[:3]
    cheapest = min(pool, key=lambda d: d["price_inr"])
    for i, d in enumerate(top, 1):
        why = f"{d['model']} {d['body_type']}, {d['seats'] or '?'} seats, claimed {d['range_claimed_km']} km" + \
              (f", tested {d['range_tested_km']} km" if d['range_tested_km'] else (f", maker real-world {int(d['range_maker_realworld_km'])}+ km" if d['range_maker_realworld_km'] else "")) + \
              f", ESP {d['esp']}, ADAS {d['adas']}, camera {d['camera']}, NCAP {d['ncap_status']}"
        alt = ""
        if i == 1 and cheapest is not d:
            alt = f"Cheapest that still meets must-haves: {cheapest['model']} {cheapest['variant']} at ₹{cheapest['price_inr']:,} (saves ₹{d['price_inr'] - cheapest['price_inr']:,}); see Variant_Ladder for what you give up"
        c5 = cto(d)
        TC.append([name if i == 1 else "", i, f"{d['model']} {d['variant']}", d["price_inr"], round(c5) if c5 else None, why, d["watch_outs"], alt])
for c in TC[1]: c.font = HF; c.fill = HFILL; c.border = BRD; c.alignment = Alignment(wrap_text=True)
for row in TC.iter_rows(min_row=2):
    for c in row: c.border = BRD; c.font = BLACK; c.alignment = Alignment(wrap_text=True, vertical="top")
for r_ in range(2, TC.max_row + 1):
    for c in (4, 5): TC.cell(r_, c).number_format = "₹#,##0"
for w_, c in zip((30, 6, 34, 12, 16, 60, 70, 60), "ABCDEFGH"): TC.column_dimensions[c].width = w_
TC.freeze_panes = "C2"
TC.append([]); TC.append(["Static snapshot computed with default assumptions by the build script, to sanity-check engine logic. Ranking: lowest 5-yr cost among variants meeting budget, seats and must-haves (range profile ranks by real-world range)."])

# ---------- Engine_Rules ----------
if "Engine_Rules" in wb.sheetnames: del wb["Engine_Rules"]
R = wb.create_sheet("Engine_Rules", 5)
rules = [
 ("ROLE SPLIT", "LLM: understand the buyer and explain results. Code: filter, rank and compute from Engine_Variants. The LLM never invents a number."),
 ("STEP 1  Hard filters", "Budget (price_inr + charger_cost_inr if no charger), seats, body_type, must-have features. Treat 'Not stated' as unknown: never silently pass or fail it; ask or flag."),
 ("STEP 2  Usage fit", "Daily km vs range_tested_km, else range_maker_realworld_km (never range_claimed_km alone). Home charging: if none, weight dc_avg_kw_est and minutes_dc_per_100km."),
 ("STEP 3  Rank", "Default: lowest cost_to_own_period_inr. Range-led buyers: real-world range. Safety-led: ncap_adult_32, then ESP/airbags/ADAS."),
 ("STEP 4  Always show", "Top 2-3 picks + one cheaper alternative (Variant_Ladder: what you give up) + watch_outs for each pick + price_status."),
 ("STEP 5  Accessories", "Only suggest genuine accessories with equivalence 'same' or 'close' to fill a gap, with price. Never aftermarket. Never present a lower variant + accessories as equal to a higher variant."),
 ("NEVER", "Apply a petrol/diesel crash rating to an EV. Quote BaaS price as the car's price without the battery loan. Present maker 'real-world' range as independent. Use a 'pending' value without saying so."),
 ("CONFIDENCE", "verified = official; corroborated = 2+ independent sources; pending = say 'unconfirmed'. Independent test data always labelled as such."),
 ("WHEN NOTHING FITS", "Say so plainly, show the nearest option above budget and what extra it costs. Don't stretch filters silently."),
 ("DATA SCOPE", "Mahindra (BE 6 SPORTEQ, XEV 9e, XEV 9S, XUV 3XO EV) and Tata (Tiago.ev, Tigor.ev, Punch.ev, Nexon.ev, Curvv.ev, Harrier.ev, Sierra.ev). Tell users other brands aren't covered yet."),
 ("COSTS NOT INCLUDED", "Registration, insurance, service, financing, resale, current offers/discounts (Tata running offers Oct 2026, see Q067)."),
]
R.append(["rule", "detail"])
for a, b in rules: R.append([a, b])
for c in R[1]: c.font = HF; c.fill = HFILL
for row in R.iter_rows(min_row=2):
    for c in row: c.border = BRD; c.font = BLACK; c.alignment = Alignment(wrap_text=True, vertical="top")
R.column_dimensions["A"].width = 24; R.column_dimensions["B"].width = 130

# README pointer
RD = wb["README"]
RD.insert_rows(3, 6)
for i, t in enumerate(["DECISION LAYER (new):",
                       "Assumptions: editable tariffs, daily km, years (yellow cells). Engine_Variants: one clean row per variant, numeric fields, running cost and 5-year cost formulas, watch-outs.",
                       "Variant_Ladder: every price step within a model, with exactly what you gain and which gains are factory-only. Engine_Rules: how the engine/LLM must use the data.",
                       "Test_Cases: 6 buyer profiles run through the logic as a sanity check. Range-led ranking puts independently tested range ahead of maker claims.", "", ""]):
    RD.cell(3 + i, 1, t).font = Font(name=F_, bold=(i == 0))

wb.save(OUT)

if False:
  with open("/dev/null", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); keep = [c for c in cols]
    w.writerow(keep + ["running_cost_inr_per_km_default", "cost_to_own_5yr_default"])
    for d in rows:
        rc = round(tariff / d["efficiency_km_per_kwh"], 2) if d["efficiency_km_per_kwh"] else ""
        c5 = cto(d)
        w.writerow([d.get(c, "") if d.get(c) is not None else "" for c in keep] + [rc, round(c5) if c5 else ""])

# ===================== consistent CSV exports + validation =====================
OUTD = REL.rstrip("/") + "/"
NUMERIC = ["price_inr","battery_kwh","seats","range_claimed_km","range_maker_realworld_km","range_tested_km","tested_vs_claim_pct","efficiency_km_per_kwh",
           "charger_cost_inr","boot_l","ground_clearance_mm","battery_clearance_mm","airbags","dc_max_kw","dc_avg_kw_est","ac_full_hours_7kw","onboard_ac_kw",
           "ncap_adult_32","ncap_child_49","terrain_modes","wading_mm"]
ENUMS = {"pricing_type":{"battery included","BaaS"},"price_status":{"verified","corroborated","pending"},"drive":{"FWD","RWD","AWD","Not stated"},
         "esp":{"Yes","Not listed","Not stated"},"adas":{"None","L2","L2+","Not stated"},"camera":{"540°","360°","Rear camera","Sensors only","Not stated"},
         "sunroof":{"Openable panoramic","Panoramic","Sunroof","None","Not stated"},"ventilated_front":{"Yes","No","Passive only","Not stated"},"adaptive_suspension":{"Yes","No","Not stated"},"range_test_vehicle":{"Same model","Earlier version","Not tested"},
         "battery_warranty":{"Lifetime (1st owner)","8 yrs / 1.6L km","Not stated"},
         "ncap_status":{"Rated, applies","Rated, coverage unconfirmed","Not tested","Not stated"},
         "charger_included":{"Yes (7.2 kW)","Yes (3.3 kW)","No","Unclear","Not stated"},
         "body_type":{"Hatchback","Sedan","SUV","SUV coupé"},"efficiency_basis":{"Independent test","Maker real-world claim (estimate)","None"}}
errs = []
def clean(v):
    if v is None: return ""
    if isinstance(v,float) and v.is_integer(): return int(v)
    return v
# ---- engine
eng_cols = [c for c in cols if c not in ("running_cost_inr_per_km","energy_cost_period_inr","cost_to_own_period_inr","minutes_dc_per_100km")]
eng_cols += ["running_cost_inr_per_km_default","cost_to_own_5yr_default","minutes_dc_per_100km_default"]
keys=[d["variant_key"] for d in rows]
if len(keys)!=len(set(keys)): errs.append("Duplicate variant_key")
for d in rows:
    for c in NUMERIC:
        v=d.get(c)
        if v is not None and not isinstance(v,(int,float)): errs.append(f"{d['variant_key']}: {c} not numeric ({v!r})")
    for c,allowed in ENUMS.items():
        if d.get(c) not in allowed: errs.append(f"{d['variant_key']}: {c}={d.get(c)!r} not in allowed set")
    if d["pricing_type"]=="battery included" and not d["price_inr"]: errs.append(f"{d['variant_key']}: missing price")
    d["running_cost_inr_per_km_default"]=round(tariff/d["efficiency_km_per_kwh"],2) if d["efficiency_km_per_kwh"] else None
    c5=cto(d); d["cost_to_own_5yr_default"]=round(c5) if c5 else None
    d["minutes_dc_per_100km_default"]=round(100/d["efficiency_km_per_kwh"]/d["dc_avg_kw_est"]*60) if (d["efficiency_km_per_kwh"] and d["dc_avg_kw_est"]) else None
with open(OUTD+"autobrain_engine_variants.csv","w",newline="",encoding="utf-8") as fh:
    w=csv.writer(fh); w.writerow(eng_cols)
    for d in sorted(rows,key=lambda x:x["variant_key"]): w.writerow([clean(d.get(c)) for c in eng_cols])
# ---- ladder
keyset=set(keys); price={d["variant_key"]:d["price_inr"] for d in rows}
for l in LADDER:
    for k in ("from_variant_key","to_variant_key"):
        if l[k] not in keyset: errs.append(f"Ladder key missing in engine: {l[k]}")
    if price.get(l["to_variant_key"])-price.get(l["from_variant_key"])!=l["extra_cost_inr"]: errs.append(f"Ladder price mismatch {l['from_variant_key']}")
    l["ladder_key"]=l["from_variant_key"]+"__TO__"+l["to_variant_key"]
lcols=["ladder_key","model","from_variant_key","to_variant_key","from_variant","to_variant","from_price_inr","to_price_inr","extra_cost_inr",
       "what_you_gain","factory_only_gains","note","price_status_from","price_status_to"]
with open(OUTD+"autobrain_variant_ladder.csv","w",newline="",encoding="utf-8") as fh:
    w=csv.writer(fh); w.writerow(lcols)
    for l in LADDER: w.writerow([clean(l.get(c)) for c in lcols])
# ---- accessories
models=set(d["model"] for d in rows); acc=[]; seen=set()
for r in vals["Accessories"].iter_rows(min_row=2,values_only=True):
    if not r[0]: continue
    _,brand,model,name,catg,fits,subst,equiv,pr,psrc,inst,wsafe,lsrc,note=r
    applies="All variants (maker does not restrict)"
    if model=="XEV 9e (Cineluxe)": model,applies="XEV 9e","Cineluxe only"
    if model not in models: errs.append(f"Accessory model not in engine: {model}")
    k=slug(brand,model,name,"CINELUXE" if applies=="Cineluxe only" else "")
    if k in seen: continue   # identical listing repeated in source catalogue
    seen.add(k)
    if pr is not None and not isinstance(pr,(int,float)): errs.append(f"{k}: price not numeric")
    if equiv not in ("same","close","partial","cosmetic only","n/a"): errs.append(f"{k}: bad equivalence {equiv}")
    acc.append(dict(accessory_key=k,brand=brand,model=model,accessory=name,category=catg,applies_to=applies if applies!="All variants (maker does not restrict)" else fits,
                    substitutes_factory_feature=subst,equivalence=equiv,equivalence_basis="Analyst judgement (not maker data)" if equiv!="n/a" else "",
                    price_inr=pr,price_source=psrc,price_status=("verified" if pr is not None else "not published"),
                    installation=inst,warranty_safe=wsafe,usable_as_gap_filler="yes" if equiv in ("same","close") else "no",notes=note))
acols=list(acc[0].keys())
with open(OUTD+"autobrain_accessories.csv","w",newline="",encoding="utf-8") as fh:
    w=csv.writer(fh); w.writerow(acols)
    for a in sorted(acc,key=lambda x:x["accessory_key"]): w.writerow([clean(a.get(c)) for c in acols])
# ---- data dictionary
DD=[("autobrain_engine_variants.csv","variant_key","text","Permanent ID: BRAND-MODEL-TRIM-KWH[-AWD][-6S][-BAAS]. Join key for all files."),
    ("autobrain_engine_variants.csv","sheet_id","text","Row ID in the master XLSX (can change; do not join on it)."),
    ("autobrain_engine_variants.csv","price_inr","integer","Ex-showroom, without wall charger. BaaS rows = chassis price; battery is a separate loan."),
    ("autobrain_engine_variants.csv","price_status","enum","verified = official; corroborated = 2+ independent sources; pending = unconfirmed (say so to user)."),
    ("autobrain_engine_variants.csv","range_claimed_km","integer","Maker certified range; see range_standard. Never use alone for usage fit."),
    ("autobrain_engine_variants.csv","range_maker_realworld_km","number","Lower bound of maker's own real-world claim (Tata C75 / Mahindra 'real-world'). Not independent."),
    ("autobrain_engine_variants.csv","range_tested_km","integer","Independent test (Autocar India). Preferred for usage fit when present."),
    ("autobrain_engine_variants.csv","range_test_vehicle","enum","Whether range_tested_km / tested efficiency come from the exact version sold now ('Same model'), an earlier version ('Earlier version'), or no test ('Not tested'). Earlier-version tests must be labelled and must not earn High confidence."),
    ("autobrain_engine_variants.csv","range_test_note","text","Plain-language note on the test vehicle; show it next to tested figures when range_test_vehicle = 'Earlier version'."),
    ("autobrain_engine_variants.csv","efficiency_km_per_kwh","number","Tested if efficiency_basis='Independent test', else estimate from maker claim."),
    ("autobrain_engine_variants.csv","running_cost_inr_per_km_default","number",f"At default blended tariff ₹{tariff:.1f}/kWh. Recompute with user's tariff: tariff / efficiency."),
    ("autobrain_engine_variants.csv","cost_to_own_5yr_default","integer","price + charger (if not included) + electricity at 40 km/day for 5 years. Excludes insurance, registration, service, resale, offers."),
    ("autobrain_engine_variants.csv","dc_avg_kw_est","number","Average DC power derived from maker charge time and window. Comparable across brands."),
    ("autobrain_engine_variants.csv","minutes_dc_per_100km_default","integer","Minutes of DC charging to add 100 km."),
    ("autobrain_engine_variants.csv","charger_cost_inr","integer","Cost to add a 7.2 kW wall box if not included; see charger_basis for whether it's official or assumed."),
    ("autobrain_engine_variants.csv","ncap_status","enum","Bharat NCAP. 'Rated, coverage unconfirmed' = rating exists but may not cover this version."),
    ("autobrain_engine_variants.csv","watch_outs","text","Auto-generated warnings; must be shown with any recommendation."),
    ("autobrain_engine_variants.csv","adaptive_suspension","enum","Electronically adaptive dampers per maker. 'Not stated' is common: never infer ride quality from it."),
    ("autobrain_engine_variants.csv","ground_clearance_mm","integer","Unladen, as stated by maker. Blank = not stated."),
    ("autobrain_engine_variants.csv","battery_clearance_mm","integer","Clearance under the battery pack where the maker states it. Blank = not stated."),
    ("autobrain_engine_variants.csv","(all enums)","enum","Allowed values: "+"; ".join(f"{k}: {'/'.join(sorted(v))}" for k,v in ENUMS.items())),
    ("autobrain_engine_variants.csv","(blank cells)","-","Blank = not stated by any source. Treat as unknown: never pass or fail a filter on it silently."),
    ("autobrain_variant_ladder.csv","ladder_key","text","from_variant_key__TO__to_variant_key. Battery-included variants only, sorted by price within model."),
    ("autobrain_variant_ladder.csv","factory_only_gains","text (pipe-separated)","Gains no accessory can replace. Use for 'what you give up' wording."),
    ("autobrain_accessories.csv","accessory_key","text","BRAND-MODEL-NAME. Genuine accessories only; aftermarket excluded by policy."),
    ("autobrain_accessories.csv","usable_as_gap_filler","yes/no","Only 'yes' items may be suggested to cover a missing factory feature, and never as equal to the higher variant."),
    ("autobrain_accessories.csv","equivalence_basis","text","Equivalence ratings are analyst judgement, not maker data."),
    ("autobrain_accessories.csv","price_inr","integer","Blank = maker does not publish (most Mahindra). Tata prices from Tata.ev shop.")]
with open(OUTD+"autobrain_data_dictionary.csv","w",newline="",encoding="utf-8") as fh:
    w=csv.writer(fh); w.writerow(["file","column","type","meaning_and_rules"]); w.writerows(DD)
print("engine",len(rows),"ladder",len(LADDER),"accessories",len(acc),"errors",len(errs))
for e in errs[:40]: print("  ERR",e)
if errs:
    print("VALIDATION FAILED: release not valid. Fix the spreadsheet and rerun."); sys.exit(1)
man={"release":os.path.basename(REL.rstrip("/")),"built_at":datetime.datetime.now().isoformat(timespec="seconds"),
     "source":os.path.basename(OUT),"counts":{"variants":len(rows),"ladder_steps":len(LADDER),"accessories":len(acc),"dictionary_rows":len(DD)},"files":{}}
for f in ("autobrain_engine_variants.csv","autobrain_variant_ladder.csv","autobrain_accessories.csv","autobrain_data_dictionary.csv"):
    man["files"][f]=hashlib.sha256(open(OUTD+f,"rb").read()).hexdigest()
json.dump(man,open(OUTD+"manifest.json","w"),indent=2); print("manifest written:", OUTD+"manifest.json")

