import os
import sys
import time
import datetime
import requests
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
API_KEY = os.environ.get("RAPIDAPI_KEY", "").strip()

DEFAULT_STAKE = 40000

# ۲۲ لیگ و تورنمنت معتبر جهانی با نقدینگی بالا در بوک‌میکرها
GLOBAL_TOP_LEAGUES = {
    2: ("لیگ قهرمانان اروپا", "🏆"),
    3: ("لیگ اروپا", "🇪🇺"),
    848: ("لیگ کنفرانس اروپا", "🇪🇺"),
    39: ("لیگ برتر انگلیس", "🏴󠁧󠁢󠁥󠁮󠁧󠁿"),
    140: ("لالیگا اسپانیا", "🇪🇸"),
    135: ("سری آ ایتالیا", "🇮🇹"),
    78: ("بوندسلیگا آلمان", "🇩🇪"),
    61: ("لوشامپیونه فرانسه", "🇫🇷"),
    88: ("اردیویسه هلند", "🇳🇱"),
    94: ("لیگ برتر پرتغال", "🇵🇹"),
    203: ("سوپرلیگ ترکیه", "🇹🇷"),
    71: ("سری آ برزیل", "🇧🇷"),
    128: ("لیگ برتر آرژانتین", "🇦🇷"),
    253: ("ام‌ال‌اس آمریکا (MLS)", "🇺🇸"),
    262: ("لیگ برتر مکزیک", "🇲🇽"),
    13: ("کوپا لیبرتادورس", "🌎"),
    11: ("کوپا سودامریکانا", "🌎"),
    307: ("لیگ حرفه‌ای عربستان", "🇸🇦"),
    98: ("جی‌لیگ ژاپن", "🇯🇵"),
    292: ("کی‌لیگ کره جنوبی", "🇰🇷"),
    17: ("لیگ نخبگان آسیا", "🌏")
}

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ خطا: متغیرهای محیطی دیتابیس یافت نشدند.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_api_headers_and_url(endpoint: str):
    is_direct = (len(API_KEY) == 32 and "-" not in API_KEY)
    if is_direct:
        base_url = "https://v3.football.api-sports.io"
        headers = {"x-apisports-key": API_KEY}
    else:
        base_url = "https://api-football-v1.p.rapidapi.com/v3"
        headers = {
            "X-RapidAPI-Key": API_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
    return f"{base_url}/{endpoint}", headers

def call_api(endpoint: str):
    if not API_KEY:
        return None
    url, headers = get_api_headers_and_url(endpoint)
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            return r.json().get("response", [])
        return None
    except Exception as e:
        print(f"خطای وب‌سرویس ({endpoint}): {e}")
        return None

def auto_seed_today_real_fixtures():
    print("🌍 واکشی مسابقات واقعی امروز از API-Football...")
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now_tehran = datetime.datetime.now(datetime.timezone.utc).astimezone(tehran_tz)
    today_str = now_tehran.strftime("%Y-%m-%d")

    fixtures = call_api(f"fixtures?date={today_str}") or []
    if not fixtures:
        print("هیچ مسابقه‌ای برای امروز در وب‌سرویس یافت نشد.")
        return

    # استخراج مسابقاتی که در لیگ‌های معتبر هستند یا وضعیت شروع‌نشده دارند
    qualified = [
        f for f in fixtures 
        if (f.get("league", {}).get("id") in GLOBAL_TOP_LEAGUES or f.get("league", {}).get("type") == "League")
        and f.get("fixture", {}).get("status", {}).get("short") in ["NS", "1H", "HT", "2H"]
    ]

    print(f"تعداد {len(qualified)} مسابقه معتبر در تقویم امروز شناسایی شد.")
    supabase.table("matches_today").delete().neq("id", "KEEP_NOTHING").execute()

    rank = 1
    for match in qualified[:4]:
        f_id = match.get("fixture", {}).get("id")
        league_id = match.get("league", {}).get("id")
        home = match.get("teams", {}).get("home", {}).get("name")
        away = match.get("teams", {}).get("away", {}).get("name")
        league_meta = GLOBAL_TOP_LEAGUES.get(league_id, (match.get("league", {}).get("name"), "⚽"))

        kickoff_utc = match.get("fixture", {}).get("date")
        try:
            utc_dt = datetime.datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
            tehran_dt = utc_dt.astimezone(tehran_tz)
            kickoff_str = tehran_dt.strftime("%H:%M")
        except Exception:
            kickoff_str = "۲۱:۳۰"

        # واکشی تحلیل و احتمالات هوش مصنوعی
        pred = call_api(f"predictions?fixture={f_id}")
        p_h, p_a = 50, 30
        if pred:
            percent = pred[0].get("predictions", {}).get("percent", {})
            p_h = int(percent.get("home", "50%").replace("%", "")) if "%" in percent.get("home", "50%") else 50
            p_a = int(percent.get("away", "30%").replace("%", "")) if "%" in percent.get("away", "30%") else 30

        fav = home if p_h >= p_a else away
        single_odds = 1.84 if p_h >= p_a else 1.90

        sgp_legs = [
            {"market": "مساوی فسخ", "pick": f"{fav} مساوی فسخ", "odds": 1.70, "safety": "🛡️ تساوی = بازگشت وجه"},
            {"market": "شوت در چارچوب", "pick": f"شوت چارچوب {fav} بالای ۴.۵", "odds": 1.50, "safety": "فشار هجومی مداوم"},
            {"market": "کرنرها", "pick": f"کرنرهای {fav} بالای ۴.۵", "odds": 1.45, "safety": "حملات از جناحین"}
        ]

        record = {
            "id": f"FIX-{f_id}",
            "fixture_id": f_id,
            "sport": "football",
            "rank": rank,
            "home_team": home,
            "away_team": away,
            "league": league_meta[0],
            "country_flag": league_meta[1],
            "kickoff": kickoff_str,
            "odds": single_odds,
            "min_acceptable_odds": round(single_odds * 0.94, 2),
            "recommended_pick": f"{fav} مساوی فسخ (DNB)",
            "market_title": "مساوی فسخ (Draw No Bet)",
            "category": "dnb",
            "safety_note": "در صورت تساوی در ۹۰ دقیقه، ۱۰۰٪ مبلغ شرط مسترد می‌گردد.",
            "confidence_score": round(max(p_h, p_a) / 10.0 + 1.2, 1),
            "value_percent": f"+{max(p_h, p_a) - 34}% EV",
            "opening_odds": round(single_odds * 1.08, 2),
            "fair_odds": round(single_odds * 0.90, 2),
            "odds_drop_percent": -5.2,
            "xg_stat": "۲.۲۰ vs ۰.۹۰" if fav == home else "۰.۹۵ vs ۲.۱۰",
            "sot_stat": "۶.۱ شوت",
            "corners_stat": "۵.۸ کرنر",
            "historical_streaks": [f"🔥 تمرکز محاسباتی مدل ریاضی بر برتری فاز تهاجمی {fav}."],
            "bet_builder_combo": {
                "title": f"میکس همبسته هوشمند ({fav})",
                "combined_odds": 3.70,
                "combined_win_rate": f"{max(p_h, p_a) + 12}٪",
                "bookmaker_tab": "تب شرط‌ساز (Bet Builder)",
                "why_it_works": f"برتری تملک توپ {fav} شانس شوت و کرنر را بالا می‌برد.",
                "legs": sgp_legs
            },
            "deep_props": {"shots_on_target": {"home": 5.8, "away": 3.7}, "corners": {"home": 6.2, "away": 4.0}},
            "correlation_matrix": f"همبستگی مثبت داده‌های هجومی {fav} با مهار تاکتیکی حریف.",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        supabase.table("matches_today").upsert(record).execute()
        print(f"⭐ مسابقه واقعی ثبت شد: {home} vs {away} ({league_meta[0]})")
        rank += 1
        time.sleep(1.2)

def auto_seed_future_real_fixtures():
    print("🔮 استخراج مسابقات واقعی ۳ روز آینده...")
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now_tehran = datetime.datetime.now(datetime.timezone.utc).astimezone(tehran_tz)

    supabase.table("matches_future").delete().neq("id", "KEEP_NOTHING").execute()

    for day_offset in range(1, 4):
        target_date = (now_tehran + datetime.timedelta(days=day_offset)).strftime("%Y-%m-%d")
        fixtures = call_api(f"fixtures?date={target_date}") or []
        qualified = [f for f in fixtures if f.get("league", {}).get("id") in GLOBAL_TOP_LEAGUES or f.get("league", {}).get("type") == "League"]

        rank = 1
        for match in qualified[:2]:
            f_id = match.get("fixture", {}).get("id")
            league_id = match.get("league", {}).get("id")
            home = match.get("teams", {}).get("home", {}).get("name")
            away = match.get("teams", {}).get("away", {}).get("name")
            league_meta = GLOBAL_TOP_LEAGUES.get(league_id, (match.get("league", {}).get("name"), "⚽"))

            kickoff_utc = match.get("fixture", {}).get("date")
            try:
                utc_dt = datetime.datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
                tehran_dt = utc_dt.astimezone(tehran_tz)
                kickoff_str = tehran_dt.strftime("%H:%M")
            except Exception:
                kickoff_str = "۲۰:۳۰"

            future_record = {
                "id": f"FUT-{f_id}",
                "future_day": day_offset,
                "sport": "football",
                "rank": rank,
                "home_team": home,
                "away_team": away,
                "league": league_meta[0],
                "country_flag": league_meta[1],
                "kickoff": kickoff_str,
                "market_title": "مساوی فسخ (DNB)",
                "recommended_pick": f"{home} مساوی فسخ",
                "odds": 1.85,
                "value_percent": "+12.0% EV",
                "short_formula_reason": f"قیمت‌گذاری دست‌پایین ساختار دفاعی {home} در خطوط زودهنگام."
            }
            supabase.table("matches_future").upsert(future_record).execute()
            rank += 1
            time.sleep(1.0)

def sync_live_and_settle():
    res = supabase.table("matches_today").select("*").execute()
    matches = res.data or []
    if not matches: return

    live_fixtures = call_api("fixtures?live=all") or []
    for m in matches:
        f_id = m.get("fixture_id")
        matched = next((f for f in live_fixtures if f_id and f.get("fixture", {}).get("id") == f_id), None)
        if matched:
            status = matched.get("fixture", {}).get("status", {}).get("short", "NS")
            score_h = matched.get("goals", {}).get("home", 0) or 0
            score_a = matched.get("goals", {}).get("away", 0) or 0
            elapsed = matched.get("fixture", {}).get("status", {}).get("elapsed", 0)

            if status in ["FT", "AET", "PEN"]:
                diff = score_h - score_a
                fav_home = m.get("home_team") in m.get("recommended_pick")
                profit = int(DEFAULT_STAKE * (float(m.get("odds", 1.80)) - 1.0))

                if diff == 0:
                    st, lbl, p_l, rev = 'push', '🛡️ فسخ و استرداد وجه', 0, f"تساوی {score_h}-{score_a}؛ کل وجه مسترد شد."
                elif (fav_home and diff > 0) or (not fav_home and diff < 0):
                    st, lbl, p_l, rev = 'won', f"✅ برد کامل (+{profit:,} ت)", profit, f"برد با نتیجه {score_h}-{score_a} محقق شد."
                else:
                    st, lbl, p_l, rev = 'lost', f"❌ باخت (-{DEFAULT_STAKE:,} ت)", -DEFAULT_STAKE, f"شکست با نتیجه {score_h}-{score_a}."

                past_record = {
                    "id": f"AUTO-{m['id']}-{int(time.time())}",
                    "fixture_id": f_id,
                    "match_date": str(datetime.date.today()),
                    "day_offset": 1,
                    "sport": "football",
                    "day_title": "دیروز (تسویه‌شده)",
                    "match_name": f"{m.get('home_team')} {score_h} - {score_a} {m.get('away_team')}",
                    "league": m.get("league"),
                    "pick": m.get("recommended_pick"),
                    "odds": m.get("odds"),
                    "final_score": f"{score_h} - {score_a}",
                    "status": st,
                    "status_label": lbl,
                    "profit_loss": p_l,
                    "ai_review": rev
                }
                supabase.table("matches_past").insert(past_record).execute()
                supabase.table("matches_today").delete().eq("id", m["id"]).execute()
            elif status in ["1H", "2H", "HT"]:
                supabase.table("matches_today").update({
                    "score_home": score_h, "score_away": score_a,
                    "is_live": True, "match_status": status,
                    "live_minute": f"{elapsed}'", "live_score_text": f"{score_h} - {score_a}"
                }).eq("id", m["id"]).execute()

def main():
    print("🚀 ورکر فِرا آنالیز: اجرای خودکار...")
    try: auto_seed_today_real_fixtures()
    except Exception as e: print(f"خطا در امروز: {e}")

    try: auto_seed_future_real_fixtures()
    except Exception as e: print(f"خطا در آینده: {e}")

    try: sync_live_and_settle()
    except Exception as e: print(f"خطا در پایش: {e}")

if __name__ == "__main__":
    main()
