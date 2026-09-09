# Hermes v2 Deployment Guide

This guide covers deploying Hermes v2 to production platforms with IPv6 support.

## ✅ Pre-Deployment Checklist

- [x] Database tables created in Supabase
- [x] All API keys configured (.env)
- [x] Core services tested (4/5 passing)
- [x] Test reviewer added to database
- [x] End-to-end workflow tested locally

## 🚀 Recommended Platform: Railway (EASIEST)

Railway provides the simplest deployment experience for Python/FastAPI apps with full IPv6 support.

### Important Files:
- `Procfile` - Tells Railway how to start the app
- `runtime.txt` - Specifies Python 3.11
- `nixpacks.toml` - Ensures PostgreSQL libraries are installed
- `requirements.txt` - Python dependencies with psycopg[binary]

### Deployment Steps:

1. **Sign up at [Railway](https://railway.app/)** - Login with GitHub

2. **Create New Project**
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your Hermes repository

3. **Configure Environment Variables**
   
   Add all variables from your `.env` file in Railway dashboard

4. **Deploy**
   - Railway auto-detects Procfile and deploys
   - Wait ~2-3 minutes for build
   - Get URL: `https://hermes-production.up.railway.app`

5. **Generate a public domain** in Railway: Service → Settings → Networking → **Generate Domain**. The `*.railway.internal` address is private and cannot receive SendGrid or Twilio webhooks.
6. **Test**: `bash scripts/check_live_connectivity.sh https://your-app.railway.app`

## 🔧 Post-Deployment Setup

### Configure SendGrid Webhook
- URL: `https://your-app.railway.app/webhooks/email`
- If customers currently write to Outlook, create an Outlook forwarding rule to
  the address on the domain configured in SendGrid Inbound Parse. Receiving a
  message in Outlook alone does not call this webhook.
- Configure that Inbound Parse domain's MX records with SendGrid before relying
  on the forwarding rule.
- If Hermes reads a personal Outlook.com Inbox directly, use
  [OUTLOOK_SETUP.md](OUTLOOK_SETUP.md) instead; no SendGrid Inbound Parse domain
  or Outlook forwarding rule is required.
- If Hermes reads a personal Gmail Inbox directly, use
  [GMAIL_SETUP.md](GMAIL_SETUP.md) instead; no SendGrid Inbound Parse domain or
  forwarding rule is required.

### Configure Twilio WhatsApp
- URL: `https://your-app.railway.app/webhooks/whatsapp`
- Set the webhook method to `POST`.

### Production Variables
- Copy every required variable from `.env` into Railway's **Variables** tab,
  without copying the `.env` file itself.
- Set `ENVIRONMENT=production` in Railway. The local file is intentionally set
  to `development`.

### Update Reviewer Phone
- Replace test number with your real WhatsApp number in database

## 🎉 Done!

Your instance is live with full LangGraph + IPv6 support!
