import csv
import time
from datetime import datetime, date, timedelta, time as dt_time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
from zoneinfo import ZoneInfo
import os

# Configuration
START_DATE = date(2007, 1, 2)
END_DATE   = date(2025, 6, 6)
CSV_FILE   = "forex_factory_news.csv"
LOCAL_TZ   = ZoneInfo("Australia/Sydney")


def setup_driver():
    options = Options()
    options.headless = True
    options.add_argument("--disable-blink-features=AutomationControlled")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def parse_html(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(".calendar__row")
    events = []
    for row in rows:
        time_cell     = row.select_one(".calendar__time")
        impact_cell   = row.select_one(".calendar__impact span[title]")
        currency_cell = row.select_one(".calendar__currency")
        event_cell    = row.select_one(".calendar__event")
        actual_cell   = row.select_one(".calendar__actual")
        forecast_cell = row.select_one(".calendar__forecast")
        previous_cell = row.select_one(".calendar__previous")

        time_text     = time_cell.get_text(strip=True) if time_cell else ""
        impact_text   = impact_cell["title"] if impact_cell else ""
        currency_text = currency_cell.get_text(strip=True) if currency_cell else ""
        event_text    = event_cell.get_text(strip=True) if event_cell else ""
        actual_text   = actual_cell.get_text(strip=True) if actual_cell else ""
        forecast_text = forecast_cell.get_text(strip=True) if forecast_cell else ""
        previous_text = previous_cell.get_text(strip=True) if previous_cell else ""

        events.append([time_text, impact_text, currency_text, event_text,
                       actual_text, forecast_text, previous_text])
    return events


def save_to_csv(events, current_date):
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["utc_datetime", "impact", "currency", "event",
                             "actual", "forecast", "previous"])

        for evt in events:
            time_text, impact, currency, name, actual, forecast, previous = evt
            text = time_text.strip().upper()

            if text == "ALL DAY":
                # record date only for all-day events
                utc_str = current_date.strftime("%Y-%m-%d")
            else:
                try:
                    t = datetime.strptime(text, "%I:%M%p").time()
                except ValueError:
                    t = dt_time(0, 0)

                local_dt = datetime.combine(current_date, t).replace(tzinfo=LOCAL_TZ)
                utc_dt   = local_dt.astimezone(ZoneInfo("UTC"))
                utc_str  = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            writer.writerow([utc_str, impact, currency, name,
                             actual, forecast, previous])


def get_last_scraped_date():
    if not os.path.exists(CSV_FILE):
        return START_DATE

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
        if len(lines) <= 1:
            return START_DATE
        last_line = lines[-1]
        last_date_str = last_line.split(",")[0].strip()
        last_dt = datetime.strptime(last_date_str, "%Y-%m-%dT%H:%M:%SZ")
        return last_dt.date() + timedelta(days=1)


def main():
    driver = setup_driver()
    current_date = get_last_scraped_date()

    print("🛡️ Warming up browser to pass Cloudflare...")
    test_str = current_date.strftime("%b%d.%Y")
    driver.get(f"https://www.forexfactory.com/calendar?day={test_str}")
    time.sleep(15)
    driver.get(f"https://www.forexfactory.com/calendar?day={test_str}")
    time.sleep(15)
    print("✅ Cloudflare check likely bypassed, starting scrape...\n")

    while current_date <= END_DATE:
        day_str = current_date.strftime("%b%d.%Y")
        url = f"https://www.forexfactory.com/calendar?day={day_str}"
        try:
            driver.get(url)
            time.sleep(5)
            html   = driver.page_source
            events = parse_html(html)
            if events:
                save_to_csv(events, current_date)
                print(f"✅ {current_date} - {len(events)} events saved")
            else:
                print(f"⚠️  {current_date} - no events found")
        except Exception as e:
            print(f"❌ {current_date} - failed: {e}")

        print("⏳ Waiting for 5 seconds before next request...")
        time.sleep(5)
        current_date += timedelta(days=1)

    driver.quit()
    print(f"\n🎉 Done! All events saved to {CSV_FILE}")


if __name__ == "__main__":
    main()
