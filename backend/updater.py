import schedule
import time
import subprocess
import datetime
from zoneinfo import ZoneInfo


def run_weekly_totals():
    subprocess.run(["python3", "weekly_totals.py"])
    now_est = datetime.datetime.now(ZoneInfo('America/New_York'))
    print(f"Ran weekly_totals.py at {now_est.strftime('%Y-%m-%d %H:%M:%S')} EST")


# Schedule runs every three hours from 2am to 11am EST
for hour in [2, 5, 8, 11]:
    schedule.every().day.at(f"{hour:02d}:00").do(run_weekly_totals)


# Schedule runs every 5 minutes from noon to 2am EST
def setup_frequent_schedule():
    # Clear previous frequent schedules
    for job in schedule.get_jobs():
        if hasattr(job, 'tag') and job.tag == 'frequent':
            schedule.cancel_job(job)

    current_hour = datetime.datetime.now(ZoneInfo('America/New_York')).hour

    # If we're between noon and 2am EST, schedule every 5 minutes
    if 12 <= current_hour < 24 or 0 <= current_hour < 2:
        for minute in range(0, 60, 5):
            job = schedule.every().hour.at(f":{minute:02d}").do(run_weekly_totals)
            job.tag = 'frequent'


# Initial setup of frequent schedule
setup_frequent_schedule()
# Refresh frequent schedule every hour to adjust for time passing
schedule.every().hour.do(setup_frequent_schedule)

print("Scheduler started. Press Ctrl+C to exit.")
while True:
    schedule.run_pending()
    time.sleep(1)