# alertmanager-discord  
Discord receiver for Alertmanager

## About  
`alertmanager-discord` is a lightweight adapter that enables Prometheus Alertmanager-compatible alerts to be sent to Discord channels via web-hooks.  
VMAlertmanager (Victoria Metrics) doesn't have native Discord support — this project fills that gap, so you can notify your team on Discord with alerts from Prometheus-style monitoring stacks.

## Features  
- Receives standard Alertmanager webhook payloads.  
- Translates them to Discord webhook messages.   
- Lightweight and easy to deploy (Python-based).  
- Simple configuration; minimal dependencies.

## Getting Started  

### Prerequisites  
- A working Prometheus Alertmanager instance.  
- A Discord server with a channel set up, and a Discord **webhook URL** created (in channel Settings → Integrations → Webhooks).  

### Configuration

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/your_webhook_id/your_webhook_token"
export ALERTMANAGER_URL="http://your-alertmanager:9093"
export GRAFANA_URL="http://your-grafana:3000"
export PORT="5000"
```
