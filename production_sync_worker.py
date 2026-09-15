"""
=============================================================================
فِرا آنالیز (Fera Analyze) - ورکر صنعتی پایش بلادرنگ مسابقات
=============================================================================
این اسکریپت سبک پایتون وظیفه استعلام زنده مسابقات و همگام‌سازی تابلوی نتایج
را در دیتابیس ابری Supabase بر عهده دارد.
پشتیبانی هوشمند دوگانه:
۱. کلید RapidAPI (X-RapidAPI-Key)
۲. کلید مستقیم API-Football (x-apisports-key)
=============================================================================
"""

import os
import sys
import datetime
import requests
from supabase import create_client, Client

# واکشی متغیرهای امنیتی از محیط ابری GitHub Secrets
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
API_KEY = os.environ.get("RAPIDAPI_KEY", "").strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ خطا: متغیرهای محیطی SUPABASE_URL یا SUPABASE_SERVICE_ROLE_KEY در Secrets تنظیم نشده‌اند.")
    sys.exit(1)

# برقراری ارتباط با پایگاه داده Supabase
supabase: Client = None
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ اتصال پایدار با پایگاه داده ابری Supabase برقرار شد.")
except Exception as connection_error:
    print(f"❌ خطا در اتصال به پایگاه داده Supabase: {connection_error}")
    sys.exit(1)

def fetch_live_fixtures():
    """استعلام زنده مسابقات جاری دنیا با پشتیبانی هوشمند از کلید مستقیم و RapidAPI"""
    if not API_KEY:
        print("⚠️ متغیر RAPIDAPI_KEY تنظیم نشده است. استعلام زنده متوقف گردید.")
        return []

    # کلیدهای مستقیم API-Football دقیقاً ۳۲ کاراکتری هگزادسیمال هستند و خط تیره ندارند
    is_direct_apisports = (len(API_KEY) == 32 and "-" not in API_KEY)

    if is_direct_apisports:
        print("🔑 کلید رسمی API-SPORTS شناسایی شد. ارتباط با سرور مستقیم v3.football.api-sports.io...")
        url = "https://v3.football.api-sports.io/fixtures?live=all"
        headers = {
            "x-apisports-key": API_KEY
        }
    else:
        print("🔑 کلید پلتفرم RapidAPI شناسایی شد. ارتباط با درگاه api-football-v1.p.rapidapi.com...")
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures?live=all"
        headers = {
            "X-RapidAPI-Key": API_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            payload = response.json()
            fixtures = payload.get("response", [])
            print(f"📡 اطلاعات زنده استادیوم‌ها واکشی شد: {len(fixtures)} مسابقه هم‌اکنون در جریان است.")
            return fixtures
        else:
            print(f"⚠️ وب‌سرویس با وضعیت {response.status_code} پاسخ داد: {response.text}")
            return []
    except Exception as request_error:
        print(f"❌ خطای شبکه در برقراری ارتباط با وب‌سرویس مسابقات: {request_error}")
        return []

def normalize_team_name(name: str) -> str:
    """استانداردسازی و نگاشت اسامی فارسی و انگلیسی تیم‌ها"""
    if not name:
        return ""
    
    clean_name = name.lower().strip()
    mapping_dict = {
        "آ.اس. رم": "roma", "رم": "roma", "as roma": "roma",
        "تورینو": "torino",
        "اینتر میلان": "inter", "اینتر": "inter",
        "اودینزه": "udinese",
        "ویارئال": "villarreal",
        "رئال بتیس": "betis", "بتیس": "betis",
        "لیدز یونایتد": "leeds", "لیدز": "leeds",
        "نیوکسل یونایتد": "newcastle", "نیوکسل": "newcastle",
        "کومو": "como", "پارما": "parma",
        "براگا": "braga", "استوریل": "estoril",
        "رئال مادرید": "real madrid", "الچه": "elche"
    }

    for fa_key, en_val in mapping_dict.items():
        if fa_key in clean_name or en_val in clean_name:
            return en_val
            
    return clean_name

def run_sync_cycle():
    """چرخه پایش مسابقات فعال امروز و به‌روزرسانی زنده جداول"""
    try:
        res = supabase.table("matches_today").select("*").execute()
        db_matches = res.data or []
    except Exception as query_err:
        print(f"❌ خطا در واکشی جدول matches_today: {query_err}")
        return

    if not db_matches:
        print("ℹ️ در حال حاضر هیچ مسابقه‌ای در جدول matches_today ثبت نشده است.")
        return

    print(f"🔍 تعداد {len(db_matches)} مسابقه در دیتابیس فِرا آنالیز در صف پایش هستند.")

    live_fixtures = fetch_live_fixtures()
    updated_count = 0

    for match in db_matches:
        db_id = match.get("id")
        home_target = normalize_team_name(match.get("home_team", ""))
        away_target = normalize_team_name(match.get("away_team", ""))

        matched_fixture = None
        for fix in live_fixtures:
            teams = fix.get("teams", {})
            api_home = normalize_team_name(teams.get("home", {}).get("name", ""))
            api_away = normalize_team_name(teams.get("away", {}).get("name", ""))

            # تطابق دوطرفه نام تیم‌ها
            is_home_match = (home_target in api_home) or (api_home in home_target)
            is_away_match = (away_target in api_away) or (api_away in away_target)

            if is_home_match and is_away_match:
                matched_fixture = fix
                break

        if matched_fixture:
            fixture_info = matched_fixture.get("fixture", {})
            status_info = fixture_info.get("status", {})
            short_status = status_info.get("short", "1H")
            elapsed_minute = status_info.get("elapsed", 0)

            goals = matched_fixture.get("goals", {})
            score_home = goals.get("home") if goals.get("home") is not None else 0
            score_away = goals.get("away") if goals.get("away") is not None else 0

            is_finished = short_status in ["FT", "AET", "PEN"]
            is_live = short_status in ["1H", "2H", "HT", "ET", "P"]

            minute_display = f"{elapsed_minute}'"
            if short_status == "HT":
                minute_display = "استراحت بین دو نیمه (HT)"
            elif is_finished:
                minute_display = "پایان مسابقه (FT)"

            update_data = {
                "score_home": score_home,
                "score_away": score_away,
                "is_live": is_live,
                "match_status": short_status,
                "live_minute": minute_display,
                "live_score_text": f"{score_home} - {score_away}"
            }

            try:
                supabase.table("matches_today").update(update_data).eq("id", db_id).execute()
                updated_count += 1
                print(f"⚽ مسابقه {match.get('home_team')} - {match.get('away_team')} به‌روز شد: [{score_home} - {score_away}] ({minute_display})")
            except Exception as update_err:
                print(f"⚠️ خطا در به‌روزرسانی مسابقه {db_id}: {update_err}")

    print(f"🏁 چرخه پایش با موفقیت پایان یافت: {updated_count} مسابقه با اطلاعات استادیوم‌ها همگام‌سازی شد.")

if __name__ == "__main__":
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"============================================================")
    print(f"🚀 اجرای ورکر پایش بلادرنگ فِرا آنالیز در زمان: {now_str}")
    print(f"============================================================")
    run_sync_cycle()
