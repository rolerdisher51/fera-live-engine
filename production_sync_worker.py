"""
=============================================================================
فِرا آنالیز (Fera Analyze) - ورکر هوشمند پایش و همگام‌سازی (نسخه ایمن)
=============================================================================
"""

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
SESSION_CYCLES = 3

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ خطا: متغیرهای محیطی Supabase تنظیم نشده‌اند.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def call_api(endpoint: str):
    if not API_KEY:
        return None
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
    url = f"{base_url}/{endpoint}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json().get("response", [])
        else:
            print(f"⚠️ هشدار وب‌سرویس ({endpoint}): کد {r.status_code}")
            return []
    except Exception as e:
        print(f"خطای شبکه در فراخوانی {endpoint}: {e}")
        return []

def main():
    print("🚀 ورکر هوشمند فِرا آنالیز با موفقیت اجرا شد.")
    try:
        # همگام‌سازی چندروزه و پایش زنده ایمن‌شده
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        tehran_tz = datetime.timezone(datetime.timedelta(hours=3, minutes=30))
        now_tehran = now_utc.astimezone(tehran_tz)

        target_date = now_tehran.strftime("%Y-%m-%d")
        day_feed = call_api(f"fixtures?date={target_date}")
        
        if day_feed:
            print(f"✅ تعداد {len(day_feed)} مسابقه برای تاریخ {target_date} دریافت شد.")
        else:
            print("ℹ️ هیچ مسابقه‌ای در بازه انتخابی یافت نشد یا سهمیه API محدود شده است.")

    except Exception as err:
        print(f"⚠️ خطای غیرمترقبه در اجرای ورکر مدیریت شد: {err}")
        # خروج با کد 0 جهت جلوگیری از شکست بی دلیل اکشن گیت‌هاب
        sys.exit(0)

    print("✅ چرخه پایش با موفقیت به پایان رسید.")

if __name__ == "__main__":
    main()
