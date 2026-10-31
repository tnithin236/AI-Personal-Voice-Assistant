from datetime import datetime


def current_datetime() -> str:
    now = datetime.now().astimezone()
    return now.strftime("%A, %d %B %Y, %I:%M %p ") + (now.tzname() or "")
