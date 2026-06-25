"""Show the last 5 Twilio calls and their SIP leg status."""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from twilio.rest import Client


def _getenv(*names):
    for name in names:
        v = os.getenv(name, "").strip()
        if v:
            return v
    return None


sid   = _getenv("TWILIO_ACCOUNT_SID",  "TWILLIO_ACCOUNT_SID")
token = _getenv("TWILIO_AUTH_TOKEN",    "TWILLIO_AUTH_TOKEN")

if not sid or not token:
    print("ERROR: Twilio credentials not found")
    sys.exit(1)

client = Client(sid, token)

calls = client.calls.list(limit=5)
if not calls:
    print("No calls found.")
    sys.exit(0)

for call in calls:
    print(f"\nSID:       {call.sid}")
    print(f"Direction: {call.direction}")
    print(f"From:      {call._from}")
    print(f"To:        {call.to}")
    print(f"Status:    {call.status}")
    print(f"Duration:  {call.duration}s")
    print(f"Start:     {call.start_time}")

    # child legs (the SIP dial)
    children = client.calls(call.sid).fetch().subresource_uris
    legs = client.calls.list(parent_call_sid=call.sid)
    for leg in legs:
        print(f"  └─ Leg SID: {leg.sid}  to={leg.to}  status={leg.status}  duration={leg.duration}s")
