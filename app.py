import logging
import os
import requests

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any, Optional
from urllib.parse import quote

app = FastAPI(title="Discord AlertManager Receiver")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscordAlertManager:
    def __init__(self, webhook_url: str, alertmanager_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self.alertmanager_url = alertmanager_url or os.getenv('ALERTMANAGER_URL')
        self.grafana_url = os.getenv('GRAFANA_URL')

    def get_color(self, status: str, severity: str = None) -> int:
        """Get color based on status and severity"""
        if status == "resolved":
            return 0x00ff00  # Green

        severity_colors = {
            "critical": 0xff0000,  # Red
            "warning": 0xffa500,   # Orange
            "info": 0x0000ff,      # Blue
        }

        return severity_colors.get(severity, 0x808080)  # Default gray

    def create_embed(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Create Discord embed from alert"""
        severity = alert.get('labels', {}).get('severity', 'warning')
        status = alert.get('status', 'firing')
        color = self.get_color(status, severity)

        status_emoji = ":white_check_mark: " if status == "resolved" else ":fire: "
        alert_name = alert.get('labels', {}).get('alertname', 'Unknown Alert')

        embed = {
            "title": f"{status_emoji} {alert_name}",
            "color": color,
            "fields": [],
            "footer": {"text": "Prometheus AlertManager"}
        }

        # Status field
        embed["fields"].append({
            "name": "Status",
            "value": f"{status.upper()}",
            "inline": True
        })

        # Severity field
        embed["fields"].append({
            "name": "Severity",
            "value": severity.upper(),
            "inline": True
        })

        # Instance field
        if 'instance' in alert.get('labels', {}):
            embed["fields"].append({
                "name": "Instance",
                "value": alert['labels']['instance'],
                "inline": True
            })

        # Namespace field (for Kubernetes alerts)
        if 'namespace' in alert.get('labels', {}):
            embed["fields"].append({
                "name": "Namespace",
                "value": alert['labels']['namespace'],
                "inline": True
            })

        # Annotations
        for key, value in alert.get('annotations', {}).items():
            embed["fields"].append({
                "name": key.replace('_', ' ').title(),
                "value": str(value)[:1024],
                "inline": False
            })

        # Add timestamp if available
        if alert.get('startsAt'):
            embed["timestamp"] = alert['startsAt']

        # Add description with links as text (since buttons don't work with webhooks)
        description = self.create_description_with_links(alert)
        if description:
            embed["description"] = description

        return embed

    def create_description_with_links(self, alert: Dict[str, Any]) -> str:
        """Create description text with clickable links"""
        links = []
        generator_url = alert.get('generatorURL')
        labels = alert.get('labels', {})

        # AlertManager link
        if self.alertmanager_url:
            links.append(f"[📊 AlertManager]({self.alertmanager_url}/#/alerts)")

        # Grafana link
        if self.grafana_url and 'instance' in labels:
            instance = labels['instance']
            grafana_url = f"{self.grafana_url}/explore?var-instance={instance}"
            links.append(f"[📋 Grafana]({grafana_url})")

        # Runbook link
        runbook_url = alert.get('annotations', {}).get('runbook_url')
        if runbook_url:
            links.append(f"[📖 Runbook]({runbook_url})")

        # Silence link for firing alerts
        if (alert.get('status') == 'firing' and self.alertmanager_url and 'alertname' in labels):
            filter_parts = []
            for key, value in labels.items():
                if key not in ['alertname']:
                    filter_parts.append(f'{key}="{value}"')

            if filter_parts:
                filter_query = "{" + ", ".join(filter_parts) + "}"
                encoded_filter = quote(filter_query)
                silence_url = f"{self.alertmanager_url}/#/silences/new?filter={encoded_filter}"
                links.append(f"[🔕 Silence]({silence_url})")

        if links:
            return " • ".join(links)

        return ""

    async def send_alert(self, alert: Dict[str, Any]) -> bool:
        """Send single alert to Discord"""
        embed = self.create_embed(alert)

        payload = {
            "embeds": [embed],
            "username": "AlertManager Bot",
            "avatar_url": "https://prometheus.io/icon.svg"
        }

        logger.info(f"Sending alert to Discord: {alert.get('labels', {}).get('alertname')}")

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code in [200, 204]:
                logger.info(f"Alert sent successfully: {alert.get('labels', {}).get('alertname')}")
                return True
            else:
                logger.error(f"Discord API error: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.Timeout:
            logger.error("Timeout sending alert to Discord")
            return False
        except Exception as e:
            logger.error(f"Error sending to Discord: {e}")
            return False

# Pydantic models for Alertmanager webhook
class Alert(BaseModel):
    status: str
    labels: Dict[str, str]
    annotations: Dict[str, str] = {}
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None

    model_config = ConfigDict(extra='allow')

class WebhookData(BaseModel):
    receiver: str
    status: str
    alerts: List[Alert]
    groupLabels: Dict[str, str] = {}
    commonLabels: Dict[str, str] = {}
    commonAnnotations: Dict[str, str] = {}
    externalURL: Optional[str] = None
    version: Optional[str] = None
    groupKey: Optional[str] = None

    model_config = ConfigDict(extra='allow')

# Initialize Discord client
discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
if not discord_webhook_url:
    raise ValueError("DISCORD_WEBHOOK_URL environment variable is required")

discord_client = DiscordAlertManager(
    webhook_url=discord_webhook_url,
    alertmanager_url=os.getenv('ALERTMANAGER_URL')
)

@app.post("/webhook")
async def receive_webhook(webhook_data: WebhookData):
    """Receive Alertmanager webhook"""
    try:
        if not webhook_data.alerts:
            logger.warning("No alerts in webhook payload")
            return {"status": "success", "message": "No alerts to process"}

        results = []
        for alert in webhook_data.alerts:
            # Convert Pydantic model to dict
            alert_dict = alert.model_dump()
            success = await discord_client.send_alert(alert_dict)
            results.append(success)

        success_count = sum(results)
        total_count = len(results)

        if success_count == total_count:
            return {
                "status": "success",
                "message": f"All {total_count} alerts processed successfully"
            }
        elif success_count > 0:
            return {
                "status": "partial_success",
                "message": f"Processed {success_count}/{total_count} alerts"
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to process all {total_count} alerts"
            }

    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "discord-alertmanager-receiver"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Discord AlertManager Receiver",
        "status": "running",
        "endpoints": {
            "webhook": "POST /webhook",
            "health": "GET /health"
        }
    }

if __name__ == "__main__":
    import uvicorn

    # Get port from environment or default to 5000
    port = int(os.getenv('PORT', '5000'))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
