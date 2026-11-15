# Cover email — draft

**To:** assessment@enam.com
**Subject:** IIT Delhi – AI Engineer - 2027

Hello,

I built **FINN**, a mobile-first investment agent built around triage: the first screen answers "is there anything I must act on?" in one sentence, routine filings are buried, and research reads like an analyst's one-pager with receipts.

**Live demo:** https://finn-umber.vercel.app (first load may take ~50s — the API runs on Render's free tier and sleeps; the app shows a "Waking FINN up…" state).
**Repo:** https://github.com/OmThakre10047/finn
**AI build history:** https://github.com/OmThakre10047/finn/tree/main/ai-history — the complete agent session (427 messages, every tool call), exported raw and rendered, filed as a "global" session because it predates the repo.

**Push.** A windowed digest across an 18-stock portfolio: announcement classification is rules-first (70–87% handled with zero LLM cost, logged live), material items carry real renderings — quarterly results with Revenue/EBITDA/PBT/PAT vs QoQ/YoY and filing page references, management changes with sourced bios — while routine filings stay collapsed. A Radar screen defines "unusual": volume ≥ N× its 20-day average, price beyond ±X%, watched categories — with a live "would have fired N times in 30 days" backtest; fired alerts show the threshold line on the chart.

**Pull.** Any NSE ticker: FINN reads the annual report and the last four concall transcripts (whole documents, page-cited) and returns eight sections plus a Promise Tracker — what management promised vs what was delivered, with a credibility score and citations that open the source PDF at the cited page. Grounded only in primary sources; news never enters the pull side, and uncited claims are dropped in code.

**Judgment calls:** Python does all arithmetic; every number is verified against the filing's page text before display; cheap-first routing kept the build to ~100 LLM calls (84% flash-lite) with an in-app cost ledger; NSE blocking cloud IPs is handled with a committed snapshot that auto-restores.

**Left out deliberately:** free-form chat, web push, BSE announcement coverage, voice. **Next:** portfolio-level Promise Tracker across companies, alert delivery, and a citation-disciplined question layer over the chunked filings.

Best,
Om
