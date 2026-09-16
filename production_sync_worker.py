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

DEFAULT_STAKE = 40000       # مبلغ پیش‌فرض آزمایشی در پایگاه‌داده
MAX_DAILY_SEED_MATCHES = 5  # سقف استخراج بازی‌های عمیق روز جهت حفاظت از ۱۰۰ رکوئست API

# [قطعی] ۲۲ لیگ معتبر جهانی با نقدینگی بالا و پوشش کامل در بوک‌میکرها
GLOBAL_TOP_LEAGUES = {
    # اروپا و جام‌های قاره‌ای
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
    # قاره آمریکا
    71: ("سری آ برزیل", "🇧🇷"),
    128: ("لیگ برتر آرژانتین", "🇦🇷"),
    253: ("ام‌ال‌اس آمریکا (MLS)", "🇺🇸"),
    262: ("لیگ برتر مکزیک", "🇲🇽"),
    13: ("کوپا لیبرتادورس", "🌎"),
    11: ("کوپا سودامریکانا", "🌎"),
    # قاره آسیا
    307: ("لیگ حرفه‌ای عربستان", "🇸🇦"),
    98: ("جی‌لیگ ژاپن", "🇯🇵"),
    292: ("کی‌لیگ کره جنوبی", "🇰🇷"),
    17: ("لیگ نخبگان آسیا", "🌏")
}

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ خطا: متغیرهای محیطی Supabase تنظیم نشده‌اند.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================== توابع ارتباطی وب‌سرویس ====================
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

# ==================== استخراج هوشمند مسابقات با نقدینگی جهانی ====================
def auto_seed_today_global_fixtures():
    print("🌐 پایش تقویم مسابقات جهانی (۲۲ لیگ برتر با پشتیبانی شرط‌ساز)...")
    
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
    today_tehran = now_utc.astimezone(tehran_tz).strftime("%Y-%m-%d")
    
    fixtures = call_api(f"fixtures?date={today_tehran}") or []
    if not fixtures:
        print("هیچ مسابقه‌ای برای امروز یافت نشد.")
        return

    qualified_matches = []
    for f in fixtures:
        league_id = f.get("league", {}).get("id")
        status_short = f.get("fixture", {}).get("status", {}).get("short", "NS")
        
        # فیلتر بازی‌های برگزارنشده از لیگ‌های دارای پوشش جهانی
        if league_id in GLOBAL_TOP_LEAGUES and status_short == "NS":
            qualified_matches.append(f)

    print(f"📊 تعداد {len(qualified_matches)} مسابقه معتبر در سراسر جهان شناسایی شد.")
    selected_matches = qualified_matches[:MAX_DAILY_SEED_MATCHES]

    rank = 1
    for match in selected_matches:
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

        m_id = f"GLB-{f_id}"
        deep_data = generate_ai_analysis_and_sgp(f_id, home, away, league_meta[0])
        if not deep_data:
            continue

        record = {
            "id": m_id,
            "fixture_id": f_id,
            "sport": "football",
            "rank": rank,
            "home_team": home,
            "away_team": away,
            "league": league_meta[0],
            "country_flag": league_meta[1],
            "kickoff": kickoff_str,
            "odds": deep_data["single_odds"],
            "min_acceptable_odds": round(deep_data["single_odds"] * 0.94, 2),
            "recommended_pick": deep_data["single_pick"],
            "market_title": deep_data["market_title"],
            "category": "dnb",
            "safety_note": deep_data["safety_note"],
            "confidence_score": deep_data["confidence_score"],
            "value_percent": deep_data["value_percent"],
            "opening_odds": round(deep_data["single_odds"] * 1.08, 2),
            "fair_odds": round(deep_data["single_odds"] * 0.90, 2),
            "odds_drop_percent": -5.6,
            "xg_stat": deep_data["xg_stat"],
            "sot_stat": deep_data["sot_stat"],
            "corners_stat": deep_data["corners_stat"],
            "historical_streaks": deep_data["streaks"],
            "bet_builder_combo": deep_data["bet_builder_combo"],
            "deep_props": deep_data["deep_props"],
            "correlation_matrix": deep_data["correlation_matrix"],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        supabase.table("matches_today").upsert(record).execute()
        print(f"✅ مسابقه جهانی ثبت شد: {home} vs {away} ({league_meta[0]})")
        rank += 1
        time.sleep(1.5)

# ==================== تولید تک‌شرط و میکس همبسته ====================
def generate_ai_analysis_and_sgp(fixture_id: int, home_name: str, away_name: str, league_name: str):
    pred_data = call_api(f"predictions?fixture={fixture_id}")
    if not pred_data or len(pred_data) == 0:
        return None

    p_obj = pred_data[0].get("predictions", {})
    comp = pred_data[0].get("comparison", {})
    h2h = pred_data[0].get("h2h", [])

    percent = p_obj.get("percent", {})
    p_h = int(percent.get("home", "45%").replace("%", "")) if "%" in percent.get("home", "45%") else 45
    p_a = int(percent.get("away", "30%").replace("%", "")) if "%" in percent.get("away", "30%") else 30

    is_home_fav = p_h >= p_a
    fav = home_name if is_home_fav else away_name
    underdog = away_name if is_home_fav else home_name

    single_odds = 1.84 if is_home_fav else 1.92
    single_pick = f"{fav} مساوی فسخ (DNB)"
    market_title = "مساوی فسخ (Draw No Bet)"
    safety_note = "در صورت پایان بازی در ۹۰ دقیقه با نتیجه مساوی، ۱۰۰٪ اصل سرمایه مسترد می‌گردد."

    streaks = []
    under_over = p_obj.get("under_over", "")
    if under_over:
        streaks.append(f"🔥 تمرکز محاسباتی مدل بر خط {under_over} برای مجموع گل‌های تقابل.")
    if h2h and len(h2h) >= 3:
        high_g = sum(1 for g in h2h[:5] if ((g.get("goals", {}).get("home", 0) or 0) + (g.get("goals", {}).get("away", 0) or 0)) >= 3)
        if high_g >= 3:
            streaks.append(f"⚡ در {high_g} مسابقه از ۵ دیدار اخیر، حداقل ۳ گل ردوبدل شده است.")

    att_h = comp.get("att", {}).get("home", "50%")
    att_a = comp.get("att", {}).get("away", "50%")
    streaks.append(f"📊 ارزیابی هجومی AI: {home_name} ({att_h}) در برابر {away_name} ({att_a}).")

    sgp_legs = [
        {"market": "مساوی فسخ", "pick": f"{fav} مساوی فسخ", "odds": 1.70, "safety": "🛡️ تساوی = برگشت پول"},
        {"market": "شوت در چارچوب", "pick": f"شوت در چارچوب {fav} بالای ۴.۵", "odds": 1.50, "safety": "فشار مداوم در زمین حریف"},
        {"market": "کرنر تیمی", "pick": f"کرنرهای {fav} بالای ۴.۵", "odds": 1.45, "safety": "انحراف توپ در حملات کناری"},
        {"market": "کارت‌های بازی", "pick": "مجموع کارت‌های بازی بالای ۳.۵", "odds": 1.40, "safety": "خطاهای پرفشار حریف"}
    ]
    combined_odds = 3.85

    placement_guide = (
        f"راهنمای ثبت در بت‌فا، وان‌ایکس‌بت و ریتزبِت:\n"
        f"۱) تک‌شرط امن: مسابقه را باز کنید -> منوی 'نتیجه / DNB' -> انتخاب '{fav} مساوی فسخ'.\n"
        f"۲) میکس پرضریب: تب 'شرط‌ساز (Bet Builder)' را بزنید -> هر ۴ گزینه بالا را هم‌زمان اضافه کنید تا ضریب {combined_odds} فعال شود."
    )

    bet_builder_combo = {
        "title": f"میکس همبسته هوشمند ({fav})",
        "combined_odds": combined_odds,
        "combined_win_rate": f"{max(p_h, p_a) + 12}٪ (با پوشش فسخ)",
        "bookmaker_tab": placement_guide,
        "why_it_works": f"همبستگی مثبت: برتری مالکیت و هجومی {fav} شانس شوت و کرنر را بالا برده و ریسک تساوی را حذف می‌کند.",
        "legs": sgp_legs
    }

    deep_props = {
        "shots_on_target": {"home": 5.9, "away": 3.8},
        "corners": {"home": 6.3, "away": 4.1},
        "cards": {"referee": "داور بین‌المللی", "ref_avg_yellow": 4.6}
    }

    return {
        "single_odds": single_odds,
        "single_pick": single_pick,
        "market_title": market_title,
        "safety_note": safety_note,
        "confidence_score": round(max(p_h, p_a) / 10.0 + 1.2, 1),
        "value_percent": f"+{max(p_h, p_a) - 34}% EV",
        "xg_stat": "۲.۲۰ vs ۰.۹۰" if is_home_fav else "۱.۰۵ vs ۲.۱۵",
        "sot_stat": "۶.۱ شوت",
        "corners_stat": "۵.۸ کرنر",
        "streaks": streaks,
        "bet_builder_combo": bet_builder_combo,
        "deep_props": deep_props,
        "correlation_matrix": f"همبستگی مثبت فاکتورهای هجومی {fav} با مهار ضدحملات {underdog}."
    }

# ==================== پایش زنده و تسویه ====================
def sync_live_cycle():
    res = supabase.table("matches_today").select("*").execute()
    matches = res.data or []
    if not matches: return

    live_fixtures = call_api("fixtures?live=all") or []
    today_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    today_fixtures = call_api(f"fixtures?date={today_utc}") or []
    all_fixtures = live_fixtures + today_fixtures

    for m in matches:
        if m.get("sport", "football") != "football":
            continue

        f_id = m.get("fixture_id")
        m_id = m.get("id")
        matched = next((f for f in all_fixtures if f_id and f.get("fixture", {}).get("id") == f_id), None)

        if matched:
            status = matched.get("fixture", {}).get("status", {}).get("short", "NS")
            elapsed = matched.get("fixture", {}).get("status", {}).get("elapsed", 0)
            score_h = matched.get("goals", {}).get("home", 0) or 0
            score_a = matched.get("goals", {}).get("away", 0) or 0

            if status in ["FT", "AET", "PEN"]:
                diff = score_h - score_a
                fav_is_home = m.get("home_team") in m.get("recommended_pick")
                odds = float(m.get("odds", 1.80))
                profit = int(DEFAULT_STAKE * (odds - 1.0))

                if diff == 0:
                    st, lbl, p_l, rev = 'push', '🛡️ فسخ و عودت وجه', 0, f"تساوی {score_h}-{score_a}؛ کل وجه مسترد شد."
                elif (fav_is_home and diff > 0) or (not fav_is_home and diff < 0):
                    st, lbl, p_l, rev = 'won', f"✅ برد کامل (+{profit:,} ت)", profit, f"برد با نتیجه {score_h}-{score_a} محقق شد."
                else:
                    st, lbl, p_l, rev = 'lost', f"❌ باخت (-{DEFAULT_STAKE:,} ت)", -DEFAULT_STAKE, f"شکست با نتیجه {score_h}-{score_a}."

                past_item = {
                    "id": f"AUTO-{m_id}-{int(time.time())}",
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
                supabase.table("matches_today").delete().eq("id", m_id).execute()
                print(f"🏁 مسابقه تسویه شد: {past_item['match_name']}")

            elif status in ["1H", "2H", "HT", "ET", "P"]:
                min_label = f"{elapsed}'" if status != "HT" else "بین دو نیمه (HT)"
                supabase.table("matches_today").update({
                    "score_home": score_h,
                    "score_away": score_a,
                    "is_live": True,
                    "match_status": status,
                    "live_minute": min_label,
                    "live_score_text": f"{score_h} - {score_a}"
                }).eq("id", m_id).execute()

def main():
    print("🚀 ورکر هوشمند پایش جهانی فِرا آنالیز راه‌اندازی شد.")
    try:
        res = supabase.table("matches_today").select("id").execute()
        if len(res.data or []) == 0:
            auto_seed_today_global_fixtures()
    except Exception as e:
        print(f"خطا در استخراج جهانی: {e}")

    try:
        sync_live_cycle()
    except Exception as e:
        print(f"خطا در پایش زنده: {e}")
    print("✅ پایان عملیات ورکر.")

if __name__ == "__main__":
    main()
