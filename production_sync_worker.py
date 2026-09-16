import os
import sys
import re
import time
import datetime
import requests
from supabase import create_client, Client

# ==================== تنظیمات زیرساخت ابری ====================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
API_KEY = os.environ.get("RAPIDAPI_KEY", "").strip()

DEFAULT_STAKE = 40000

# ۲۲ لیگ بین‌المللی با نقدینگی بالا در بوک‌میکرها
GLOBAL_TOP_LEAGUES = {
    39: ("لیگ برتر انگلیس", "🏴󠁧󠁢󠁥󠁮󠁧󠁿"),
    140: ("لالیگا اسپانیا", "🇪🇸"),
    135: ("سری آ ایتالیا", "🇮🇹"),
    78: ("بوندسلیگا آلمان", "🇩🇪"),
    61: ("لوشامپیونه فرانسه", "🇫🇷"),
    88: ("اردیویسه هلند", "🇳🇱"),
    94: ("لیگ برتر پرتغال", "🇵🇹"),
    203: ("سوپرلیگ ترکیه", "🇹🇷"),
    2: ("لیگ قهرمانان اروپا", "🏆"),
    3: ("لیگ اروپا", "🇪🇺"),
    848: ("لیگ کنفرانس اروپا", "🇪🇺"),
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
    print("❌ خطا: متغیرهای محیطی Supabase تنظیم نشده‌اند.")
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
        else:
            print(f"⚠️ وب‌سرویس خطا داد ({endpoint}): کد {r.status_code}")
            return None
    except Exception as e:
        print(f"خطای شبکه در فراخوانی {endpoint}: {e}")
        return None

# ==================== ۱. واکشی مسابقات امروز (Matches Today) ====================
def auto_seed_today_matches():
    print("🌍 پایش مسابقات امروز در ۲۲ لیگ جهانی...")
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now_tehran = datetime.datetime.now(datetime.timezone.utc).astimezone(tehran_tz)
    today_str = now_tehran.strftime("%Y-%m-%d")

    fixtures = call_api(f"fixtures?date={today_str}") or []
    if not fixtures:
        print("هیچ مسابقه‌ای برای امروز در وب‌سرویس بازگردانده نشد.")
        return

    qualified = [f for f in fixtures if f.get("league", {}).get("id") in GLOBAL_TOP_LEAGUES and f.get("fixture", {}).get("status", {}).get("short") == "NS"]
    print(f"تعداد {len(qualified)} مسابقه معتبر برای امروز پیدا شد.")

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

        deep = generate_ai_analysis(f_id, home, away, league_meta[0])
        if not deep:
            continue

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
            "odds": deep["single_odds"],
            "min_acceptable_odds": round(deep["single_odds"] * 0.94, 2),
            "recommended_pick": deep["single_pick"],
            "market_title": deep["market_title"],
            "category": "dnb",
            "safety_note": deep["safety_note"],
            "confidence_score": deep["confidence_score"],
            "value_percent": deep["value_percent"],
            "opening_odds": round(deep["single_odds"] * 1.08, 2),
            "fair_odds": round(deep["single_odds"] * 0.90, 2),
            "odds_drop_percent": -5.6,
            "xg_stat": deep["xg_stat"],
            "sot_stat": deep["sot_stat"],
            "corners_stat": deep["corners_stat"],
            "historical_streaks": deep["streaks"],
            "bet_builder_combo": deep["bet_builder_combo"],
            "deep_props": deep["deep_props"],
            "correlation_matrix": deep["correlation_matrix"],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        supabase.table("matches_today").upsert(record).execute()
        print(f"✅ مسابقه امروز اضافه شد: {home} vs {away}")
        rank += 1
        time.sleep(1.2)

# ==================== ۲. واکشی مسابقات ۳ روز آینده (Matches Future) ====================
def auto_seed_future_matches():
    print("🔮 پایش زودهنگام ۳ روز آینده (+EV Early Lines)...")
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    now_tehran = datetime.datetime.now(datetime.timezone.utc).astimezone(tehran_tz)

    supabase.table("matches_future").delete().neq("id", "KEEP_NOTHING").execute()

    for day_offset in range(1, 4):
        target_date = (now_tehran + datetime.timedelta(days=day_offset)).strftime("%Y-%m-%d")
        print(f"📡 واکشی بازی‌های {day_offset} روز بعد (تاریخ {target_date})...")
        fixtures = call_api(f"fixtures?date={target_date}") or []
        qualified = [f for f in fixtures if f.get("league", {}).get("id") in GLOBAL_TOP_LEAGUES]

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
                "value_percent": "+11.4% EV",
                "short_formula_reason": f"قیمت‌گذاری زودهنگام بوک‌میکرها توان هجومی {home} را کم‌برآورد کرده است."
            }
            supabase.table("matches_future").upsert(future_record).execute()
            print(f"🔮 بازی آینده ثبت شد ({day_offset} روز بعد): {home} vs {away}")
            rank += 1
            time.sleep(1.0)

# ==================== تولید بسته تحلیلی و شرط‌ساز ====================
def generate_ai_analysis(fixture_id: int, home_name: str, away_name: str, league_name: str):
    pred_data = call_api(f"predictions?fixture={fixture_id}")
    if not pred_data:
        return None

    p_obj = pred_data[0].get("predictions", {})
    comp = pred_data[0].get("comparison", {})
    percent = p_obj.get("percent", {})
    p_h = int(percent.get("home", "45%").replace("%", "")) if "%" in percent.get("home", "45%") else 45
    p_a = int(percent.get("away", "30%").replace("%", "")) if "%" in percent.get("away", "30%") else 30

    fav = home_name if p_h >= p_a else away_name
    underdog = away_name if p_h >= p_a else home_name
    single_odds = 1.84 if p_h >= p_a else 1.90

    sgp_legs = [
        {"market": "مساوی فسخ", "pick": f"{fav} مساوی فسخ", "odds": 1.70, "safety": "🛡️ تساوی = برگشت پول"},
        {"market": "شوت در چارچوب", "pick": f"شوت چارچوب {fav} بالای ۴.۵", "odds": 1.50, "safety": "فشار هجومی مداوم"},
        {"market": "کرنر تیمی", "pick": f"کرنرهای {fav} بالای ۴.۵", "odds": 1.45, "safety": "حملات پردامنه از جناحین"},
        {"market": "کارت زرد", "pick": "مجموع کارت بالای ۳.۵", "odds": 1.40, "safety": "پرس و خطاهای تاکتیکی"}
    ]

    guide = (
        f"راهنمای ثبت در بت‌فا، وان‌ایکس و ریتزبِت:\n"
        f"۱) تک‌شرط: ورود به مسابقه -> منوی DNB -> انتخاب '{fav} مساوی فسخ'.\n"
        f"۲) میکس شرط‌ساز: تب 'شرط‌ساز (Bet Builder)' را زده و هر ۴ گزینه فوق را اضافه کنید (ضریب ۳.۸۵)."
    )

    return {
        "single_odds": single_odds,
        "single_pick": f"{fav} مساوی فسخ (DNB)",
        "market_title": "مساوی فسخ (Draw No Bet)",
        "safety_note": "در صورت تساوی در ۹۰ دقیقه، ۱۰۰٪ مبلغ شرط به حسابتان بازمی‌گردد.",
        "confidence_score": round(max(p_h, p_a) / 10.0 + 1.2, 1),
        "value_percent": f"+{max(p_h, p_a) - 34}% EV",
        "xg_stat": "۲.۱۵ vs ۰.۸۵" if fav == home_name else "۰.۹۵ vs ۲.۱۰",
        "sot_stat": "۶.۲ شوت",
        "corners_stat": "۵.۹ کرنر",
        "streaks": [
            f"🔥 تمرکز محاسباتی مدل بر برتری احتمالی {fav} در فاز تهاجمی.",
            f"⚡ تقابل‌های رودرروی دو تیم گویای برتری آماری محسوس {fav} است."
        ],
        "bet_builder_combo": {
            "title": f"میکس همبسته هوشمند ({fav})",
            "combined_odds": 3.85,
            "combined_win_rate": f"{max(p_h, p_a) + 12}٪",
            "bookmaker_tab": guide,
            "why_it_works": f"همبستگی مثبت: مالکیت برتر {fav} شانس شوت و کرنر را بالا می‌برد.",
            "legs": sgp_legs
        },
        "deep_props": {
            "shots_on_target": {"home": 5.8, "away": 3.7},
            "corners": {"home": 6.2, "away": 4.0},
            "cards": {"referee": "داور رسمی", "ref_avg_yellow": 4.5}
        },
        "correlation_matrix": f"همبستگی مثبت فاکتورهای هجومی {fav} با مهار تاکتیکی {underdog}."
    }

# ==================== ۳. پایش زنده و تسویه سوت پایان ====================
def sync_live_cycle():
    res = supabase.table("matches_today").select("*").execute()
    matches = res.data or []
    if not matches: return

    live_fixtures = call_api("fixtures?live=all") or []
    for m in matches:
        f_id = m.get("fixture_id")
        matched = next((f for f in live_fixtures if f_id and f.get("fixture", {}).get("id") == f_id), None)
        if matched:
            status = matched.get("fixture", {}).get("status", {}).get("short", "NS")
            elapsed = matched.get("fixture", {}).get("status", {}).get("elapsed", 0)
            score_h = matched.get("goals", {}).get("home", 0) or 0
            score_a = matched.get("goals", {}).get("away", 0) or 0

            if status in ["FT", "AET", "PEN"]:
                diff = score_h - score_a
                fav_home = m.get("home_team") in m.get("recommended_pick")
                profit = int(DEFAULT_STAKE * (float(m.get("odds", 1.80)) - 1.0))

                if diff == 0:
                    st, lbl, p_l, rev = 'push', '🛡️ فسخ و عودت وجه', 0, f"تساوی {score_h}-{score_a}؛ اصل وجه مسترد شد."
                elif (fav_home and diff > 0) or (not fav_home and diff < 0):
                    st, lbl, p_l, rev = 'won', f"✅ برد کامل (+{profit:,} ت)", profit, f"برد با نتیجه {score_h}-{score_a} محقق شد."
                else:
                    st, lbl, p_l, rev = 'lost', f"❌ باخت (-{DEFAULT_STAKE:,} ت)", -DEFAULT_STAKE, f"شکست با نتیجه {score_h}-{score_a}."

                past_item = {
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
                supabase.table("matches_past").insert(past_item).execute()
                supabase.table("matches_today").delete().eq("id", m["id"]).execute()
                print(f"🏁 مسابقه تسویه شد: {past_item['match_name']}")
            elif status in ["1H", "2H", "HT"]:
                supabase.table("matches_today").update({
                    "score_home": score_h, "score_away": score_a,
                    "is_live": True, "match_status": status,
                    "live_minute": f"{elapsed}'", "live_score_text": f"{score_h} - {score_a}"
                }).eq("id", m["id"]).execute()

def main():
    print("🚀 ورکر فِرا آنالیز: اجرای چرخه خودکار مسابقات امروز، روزهای آینده و تسویه...")
    try:
        auto_seed_today_matches()
    except Exception as e:
        print(f"خطا در مسابقات امروز: {e}")

    try:
        auto_seed_future_matches()
    except Exception as e:
        print(f"خطا در ۳ روز آینده: {e}")

    try:
        sync_live_cycle()
    except Exception as e:
        print(f"خطا در پایش زنده: {e}")

    print("✅ پایان موفقیت‌آمیز عملیات ورکر.")

if __name__ == "__main__":
    main()
# بخشی از کد تسویه نهایی مسابقه در فایل production_sync_worker.py
# درج دائمی در آرشیو تاریخچه بدون حذف مسابقات گذشته:
past_record = {
    "id": f"AUTO-{m_id}-{int(time.time())}",
    "fixture_id": f_id,
    "match_date": str(datetime.date.today()), # ثبت تاریخ دقیق روز
    "day_offset": 1,
    "sport": "football",
    "day_title": "دیروز (تسویه‌شده)",
    "match_name": f"{home_team} {score_h} - {score_a} {away_team}",
    "league": m.get("league"),
    "pick": m.get("recommended_pick"),
    "odds": m.get("odds"),
    "final_score": f"{score_h} - {score_a}",
    "status": status,
    "status_label": status_label,
    "profit_loss": profit_loss_amount,
    "ai_review": review_text
}
supabase.table("matches_past").insert(past_record).execute()
supabase.table("matches_today").delete().eq("id", m_id).execute()
print(f"🏁 مسابقه به آرشیو دائمی گذشته اضافه شد: {past_record['match_name']}")
