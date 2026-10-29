# 📈 S&P 500 Sector Dashboard

An interactive dashboard that shows the S&P 500 index and its 11 sectors,
with data fetched **automatically every day** from MarketWatch.

- **`scraper.py`** – fetches fresh data and saves it to `data/sector_data.csv`
- **`app.py`** – the Streamlit dashboard (charts + tables)
- **`.github/workflows/daily-refresh.yml`** – runs the scraper every 24 hours

---

## How the pieces fit together

```
GitHub Actions (runs daily)  ->  scraper.py  ->  data/sector_data.csv  ->  app.py (dashboard)
```

1. A **GitHub Action** runs once a day on GitHub's servers.
2. It runs **`scraper.py`**, which downloads the latest numbers from MarketWatch.
3. It saves them to **`data/sector_data.csv`** and commits that file back to your repo.
4. **Streamlit Cloud** hosts `app.py`, which reads the CSV and shows the dashboard.

---

## Part 1 — Put the project on GitHub

You don't need the command line for this.

1. Go to <https://github.com/new> and create a repository, e.g. `sp500-dashboard`.
   Make it **Public** (required for free Streamlit hosting). Click **Create repository**.
2. On the new repo's page, click **uploading an existing file**.
3. Drag in **all** of these files/folders, keeping the structure:
   - `app.py`
   - `scraper.py`
   - `requirements.txt`
   - `README.md`
   - `.gitignore`
   - the `data/` folder (containing `sector_data.csv`)
   - the `.github/` folder (containing `workflows/daily-refresh.yml`)
   > ⚠️ The `.github/workflows/` folder must keep that exact path or the schedule won't run.
4. Click **Commit changes**.

---

## Part 2 — Host the dashboard (free) on Streamlit Community Cloud

1. Go to <https://share.streamlit.io> and click **Sign in with GitHub**. Authorize it.
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Fill in:
   - **Repository:** `your-username/sp500-dashboard`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Click **Deploy**. After a minute you'll get a public URL like
   `https://your-username-sp500-dashboard.streamlit.app` — that's your live dashboard. 🎉

Whenever the CSV updates, Streamlit picks up the change automatically.

---

## Part 3 — Turn on the daily automatic refresh

The schedule is already defined in `.github/workflows/daily-refresh.yml`
(it runs every day at **06:00 UTC**). You just need to enable and test it:

1. In your GitHub repo, click the **Actions** tab (top of the page).
2. If you see a banner asking to enable workflows, click
   **"I understand my workflows, go ahead and enable them."**
3. In the left sidebar, click **Daily Data Refresh**.
4. Click the **Run workflow** button on the right → **Run workflow** (green button).
   This runs it once right now so you can confirm it works.
5. Click into the run to watch it. A green ✓ means it fetched data and committed
   the updated `data/sector_data.csv`.

After that first manual run, it will keep running **every 24 hours** on its own.

> **If the commit step fails with a permissions error:** go to
> **Settings → Actions → General → Workflow permissions**, select
> **Read and write permissions**, and **Save**. Then re-run the workflow.

---

## Run it locally (optional)

```bash
pip install -r requirements.txt
python scraper.py        # fetch fresh data
streamlit run app.py     # open the dashboard in your browser
```

---

## Change the refresh time

Edit the `cron` line in `.github/workflows/daily-refresh.yml`.
`"0 6 * * *"` means 06:00 UTC daily. For example, `"0 22 * * *"` = 22:00 UTC daily.
Times are always in **UTC**. (See <https://crontab.guru> to build your own.)

## Notes

- `data/sector_data.csv` ships with sample starter data so the dashboard works
  immediately. The first real scrape (manual or scheduled) replaces it.
- MarketWatch may change its page layout over time. If columns stop filling in,
  the selectors in `scraper.py` (`_get_key_data` / the price selectors) may need a tweak.
