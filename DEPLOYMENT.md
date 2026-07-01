# 🚀 Render Deployment Guide

Complete step-by-step instructions for deploying the F1 2026 Fantasy Draft app to Render.

## Prerequisites

Before you begin, make sure you have:
- ✅ GitHub repository: `https://github.com/atekumalla/pakodis-f1-fantasy`
- ✅ Google Sheets spreadsheet created and shared with service account
- ✅ Google service account credentials JSON file

---

## Step 1: Prepare Your Credentials

### Get Your Spreadsheet ID
1. Open your Google Sheet
2. Copy the ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit
   ```

### Prepare Credentials JSON (Single Line)
You need to convert your `credentials.json` into a single-line string:

**Option A: Using jq (if installed)**
```bash
cat credentials.json | jq -c .
```

**Option B: Using Python**
```bash
python3 -c "import json; print(json.dumps(json.load(open('credentials.json'))))"
```

**Option C: Manually**
Open `credentials.json` and remove all newlines and extra spaces. It should look like:
```json
{"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"..."}
```

⚠️ **Important**: Copy this entire single-line JSON. You'll paste it into Render.

---

## Step 2: Create a New Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** button in the top right
3. Select **"Web Service"**

---

## Step 3: Connect Your Repository

1. **Connect GitHub Account** (if not already connected)
   - Click "Connect account" under GitHub
   - Authorize Render to access your repositories

2. **Select Repository**
   - Find and click **"Connect"** next to `atekumalla/pakodis-f1-fantasy`
   - If you don't see it, click "Configure account" and grant access to the repo

---

## Step 4: Configure the Web Service

Fill in the following settings:

### Basic Settings
| Field | Value |
|-------|-------|
| **Name** | `pakodis-f1-fantasy` (or your preferred name) |
| **Region** | Choose closest to you (e.g., `Oregon (US West)` or `Singapore`) |
| **Branch** | `main` |
| **Root Directory** | (leave blank) |
| **Runtime** | `Python 3` |

### Build & Deploy Settings
| Field | Value |
|-------|-------|
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn src.server:app --host 0.0.0.0 --port $PORT` |

### Instance Type
- Select **"Free"** (or paid plan if you prefer)
- Free tier limitations:
  - Spins down after 15 minutes of inactivity
  - Takes ~30 seconds to spin up on first request
  - 512 MB RAM, shared CPU

---

## Step 5: Add Environment Variables

Scroll down to the **"Environment Variables"** section and add the following:

### Required Variables

Click **"Add Environment Variable"** for each:

#### 1. GOOGLE_SHEETS_ID
- **Key**: `GOOGLE_SHEETS_ID`
- **Value**: Your spreadsheet ID (from Step 1)
- Example: `1abcXYZ123_your_actual_spreadsheet_id`

#### 2. GOOGLE_SHEETS_CREDENTIALS_JSON
- **Key**: `GOOGLE_SHEETS_CREDENTIALS_JSON`
- **Value**: Paste the single-line JSON from Step 1
- ⚠️ Make sure there are no extra spaces or newlines!

### Optional Variables (with defaults)

#### 3. F1_SEASON_YEAR
- **Key**: `F1_SEASON_YEAR`
- **Value**: `2026`

#### 4. SYNC_INTERVAL_MINUTES
- **Key**: `SYNC_INTERVAL_MINUTES`
- **Value**: `60` (hourly sync during regular periods)

#### 5. SYNC_LIVE_INTERVAL_SECONDS
- **Key**: `SYNC_LIVE_INTERVAL_SECONDS`
- **Value**: `120` (2-minute sync during live sessions)

#### 6. SYNC_TIMEZONE
- **Key**: `SYNC_TIMEZONE`
- **Value**: `Asia/Kolkata` (or your timezone)

#### 7. HALFWAY_ROUND
- **Key**: `HALFWAY_ROUND`
- **Value**: `12` (British GP is the redraft point)

#### 8. SYNC_COOLDOWN_SECONDS
- **Key**: `SYNC_COOLDOWN_SECONDS`
- **Value**: `600` (10 minutes between manual syncs)

---

## Step 6: Deploy!

1. Click **"Create Web Service"** at the bottom
2. Render will now:
   - Clone your repository
   - Install dependencies
   - Start your application

3. **Monitor the deployment**:
   - Watch the build logs in real-time
   - Look for: `🏎️  Server ready!` in the logs
   - First deployment takes 3-5 minutes

---

## Step 7: Seed Your Spreadsheet (First Time Only)

After the first deployment succeeds, you need to populate your Google Sheet with initial data.

### Option A: Using Render Shell (Recommended)

1. In your Render service dashboard, click **"Shell"** in the left sidebar
2. Run the seed command:
   ```bash
   python -m src.seed_data
   ```
3. Wait for confirmation message
4. Check your Google Sheet - it should now have all the worksheets and data

### Option B: Using API Endpoint

1. Access your deployed app: `https://your-service-name.onrender.com`
2. Use a tool like curl or Postman:
   ```bash
   curl -X POST https://your-service-name.onrender.com/api/seed
   ```
   (Note: You may need to add this endpoint to your server if it doesn't exist)

### Option C: Run Locally First (Easier)

Before deploying, run locally to seed:
```bash
# On your local machine
python -m src.seed_data
```

---

## Step 8: Verify Deployment

### Check the Service URL
Your app will be available at: `https://your-service-name.onrender.com`

### Test the Endpoints

1. **Dashboard**: Visit `https://your-service-name.onrender.com/`
   - Should show the F1-themed dashboard

2. **API Status**: `https://your-service-name.onrender.com/api/status`
   - Should return JSON with leaderboard and session data

3. **Calendar**: `https://your-service-name.onrender.com/api/calendar`
   - Should show the 2026 F1 race calendar

4. **Draft Page**: `https://your-service-name.onrender.com/draft`
   - Should show the mid-season draft interface

### Check the Logs

In Render dashboard, click **"Logs"** to monitor:
- Server startup messages
- Sync operations
- API requests
- Any errors

---

## Step 9: Trigger Initial Sync

Once deployed and seeded, trigger a sync to fetch F1 data:

### Using curl
```bash
curl -X POST https://your-service-name.onrender.com/api/sync
```

### Using your browser
Open the dashboard and it should automatically sync in the background.

---

## 🎉 Success Checklist

- ✅ Service is deployed and running
- ✅ No errors in logs
- ✅ Dashboard loads at your Render URL
- ✅ Google Sheet has all worksheets (Draft Picks H1, H2, Calendar, Results, Leaderboard, Scoring Rules)
- ✅ API endpoints return data
- ✅ Auto-sync is running (check logs for sync messages)

---

## 🔧 Troubleshooting

### Issue: "Failed to load from sheets" error

**Cause**: Google Sheets credentials not configured correctly

**Fix**:
1. Verify `GOOGLE_SHEETS_ID` is correct
2. Check `GOOGLE_SHEETS_CREDENTIALS_JSON` is a valid single-line JSON
3. Ensure the spreadsheet is shared with the service account email
4. Restart the service after fixing environment variables

### Issue: Service keeps crashing / restarting

**Cause**: Missing dependencies or configuration error

**Fix**:
1. Check logs for specific error messages
2. Verify all required packages are in `requirements.txt`
3. Ensure Python version is 3.11+ (check runtime settings)

### Issue: "No module named 'src'" error

**Cause**: Import path issues

**Fix**:
- Verify the start command is exactly: `uvicorn src.server:app --host 0.0.0.0 --port $PORT`
- Check that all `src/` files are committed to GitHub

### Issue: Spreadsheet not seeding

**Cause**: Permissions or credentials issue

**Fix**:
1. Verify service account email has "Editor" access to the sheet
2. Check that credentials JSON includes `client_email` field
3. Try running seed command from Render Shell

### Issue: Free tier spins down too often

**Solution**: Upgrade to a paid plan ($7/month) for:
- Always-on service (no spin-down)
- Better performance
- More RAM

---

## 🔄 Updating Your Deployment

When you make changes to your code:

1. **Commit and push to GitHub**:
   ```bash
   git add .
   git commit -m "Your update message"
   git push origin main
   ```

2. **Render auto-deploys**:
   - Render automatically detects the push
   - Rebuilds and redeploys your service
   - Monitor progress in the Render dashboard

3. **Manual deploy** (if auto-deploy is off):
   - Go to Render dashboard
   - Click "Manual Deploy" → "Deploy latest commit"

---

## 📊 Monitoring Your App

### View Logs
- Go to your service in Render dashboard
- Click **"Logs"** in the left sidebar
- Filter by log level or search for specific messages

### Metrics
- Click **"Metrics"** to see:
  - CPU usage
  - Memory usage
  - Request latency
  - Error rates

### Alerts
Set up email/Slack alerts for:
- Service crashes
- High error rates
- Memory limits exceeded

---

## 💰 Cost Estimates

### Free Tier
- **Cost**: $0/month
- **Limits**: 
  - 750 hours/month (shared across all free services)
  - Spins down after 15 min inactivity
  - 512 MB RAM

### Starter Plan
- **Cost**: $7/month
- **Benefits**:
  - Always-on (no spin-down)
  - 512 MB RAM
  - Priority support

### Standard Plan
- **Cost**: $25/month
- **Benefits**:
  - 2 GB RAM
  - Better performance
  - Faster builds

---

## 🔗 Useful Links

- **Your App**: `https://your-service-name.onrender.com`
- **Render Dashboard**: https://dashboard.render.com/
- **Render Docs**: https://render.com/docs
- **GitHub Repo**: https://github.com/atekumalla/pakodis-f1-fantasy

---

## 📝 Custom Domain (Optional)

To use your own domain:

1. Go to service **Settings** in Render
2. Scroll to **"Custom Domains"**
3. Click **"Add Custom Domain"**
4. Enter your domain (e.g., `f1.yourdomain.com`)
5. Update your DNS records with provided CNAME
6. Render automatically provisions SSL certificate

---

## 🎯 Next Steps

1. Share your app URL with your league members
2. Set up WhatsApp group for standings updates
3. Monitor during race weekends to ensure sync is working
4. Prepare for mid-season redraft at Round 12 (British GP)

**Need help?** Check the logs first, then refer to the troubleshooting section above.

Good luck with your F1 Fantasy Draft! 🏎️🏁
