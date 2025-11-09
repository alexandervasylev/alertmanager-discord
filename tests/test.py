import json
import requests

from datetime import datetime, timezone

with open("alerts.json") as f:
    webhook_data = json.loads(f.read())

    alerts = []
    for alert in webhook_data['alerts']:
        alert['startsAt'] = datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        alert['endsAt'] = datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        alerts.append(alert)

    webhook_data['alerts'] = alerts
    print(json.dumps(webhook_data, indent=2))

    try:
        response = requests.post('http://127.0.0.1:8080/webhook', json=webhook_data, headers={'Content-Type': 'application/json'})
    except Exception as ex:
        print(ex)
        raise
