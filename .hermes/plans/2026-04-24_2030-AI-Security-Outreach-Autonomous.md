# Plan: Autonomous AI Security Agent Outreach for Job Opportunities

## Goal
Create an autonomous system that periodically identifies AI security (especially agentic security) job opportunities or companies working on AI agents, and sends personalized outreach emails showcasing Matheus Theodoro's expertise in offensive security, AI agent hardening, and red teaming for AI systems, with the aim of securing job interviews or collaborations.

## Context / Assumptions
- Hermes Agent is installed with model-rotator skill active (using NVIDIA NIM).
- GBrain is installed with the RedThread wiki imported as the brain repository (~ /Documents/matheusvsky/Documents/personal/redthread/docs/wiki).
- We have a Gmail account: dev.matheustheodoro@gmail.com (user will provide App Password).
- We have the user's CV at /Users/matheusvsky/Downloads/matheus-ai.pdf (text extracted).
- We can scrape LinkedIn (linkedin.com/in/matheusht) and GitHub (github.com/matheusht) for additional professional details.
- Outreach will be done via Himalaya CLI (to be installed and configured).
- The system should run autonomously (e.g., via cron job or Hermes background process) to avoid manual intervention each time.
- We will store state (sent emails, last run, etc.) in a dedicated project folder under ~/.hermes/ai-security-outreach/.
- We will respect Gmail sending limits (~80-100 emails per day) and avoid spamming.

## Proposed Approach
1. Set up a dedicated project directory for the autonomous outreach agent.
2. Install and configure Himalaya for Gmail.
3. Extract and structure the user's professional profile from CV, LinkedIn, GitHub.
4. Create a knowledge base of target companies/roles in AI security (agentic security focus) using web search and GBrain.
5. Draft email templates that highlight specific AI security expertise (adversarial defense, agent monitoring, red teaming AI systems, securing AI workflows, etc.).
6. Build a script that, on each run:
   a. Identifies new target companies/roles (or re-engages with previous ones after a cooldown).
   b. Personalizes email using the template and the user's profile.
   c. Sends email via Himalaya.
   d. Logs sent emails and updates state.
7. Schedule the script to run periodically (e.g., every 6 hours) via cron or Hermes background task.
8. Include safety checks: stop if too many bounces/replies negative, honor unsubscribe requests, etc.

## Step‑by‑Step Plan

### 1. Create Project Directory
```bash
mkdir -p ~/.hermes/ai-security-outreach
cd ~/.hermes/ai-security-outreach
```
Subdirectories:
- `profiles/` – store scraped LinkedIn/GitHub/CV data
- `templates/` – email templates (MML for Himalaya)
- `targets/` – list of target companies/roles (can be GBrain-backed or flat files)
- `logs/` – sent email logs, error logs
- `state/` – JSON file tracking last run, sent emails, cooldowns
- `scripts/` – Python/shell scripts for the outreach logic

### 2. Install and Configure Himalaya (for Gmail)
```bash
# Install Himalaya (pre-built binary)
curl -sSL https://raw.githubusercontent.com/pimalaya/himalaya/master/install.sh | PREFIX=~/.local sh
export PATH="$HOME/.local/bin:$PATH"
himalaya --version
# Configure Gmail account (will prompt for credentials)
himalaya account configure
  # Use IMAP/SMTP for Gmail:
  #   IMAP: imap.gmail.com:993 TLS
  #   SMTP: smtp.gmail.com:587 STARTTLS
  #   Username: dev.matheustheodoro@gmail.com
  #   Password: <App Password> (generate from Google Account)
```
Test by sending a test email to yourself.

### 3. Extract and Structure Professional Profile
We'll create a JSON/YAML profile from multiple sources:
- **CV** (already extracted): summarize key achievements, skills, experience.
- **LinkedIn**: scrape public profile (or use cached data) for headline, about, experience, skills, recommendations.
- **GitHub**: scrape repositories, readmes, languages, notable projects.
We'll store this as `profiles/matheus-theodoro.json`.

### 4. Build Target Knowledge Base
We need a list of companies/roles that are hiring for AI security, agentic security, red teaming for LLMs, etc.
Approaches:
- Use GBrain to store notes on companies (we already have RedThread wiki; we can add a `companies/ai-security/` folder).
- Use web search (via Hermes web_search or browser-harness) to find recent job postings, AI security firms, labs.
- Examples of target areas: AI safety labs (Anthropic, OpenAI, Conjecture, etc.), AI agent frameworks (LangChain, LlamaIndex, Auto-GPT, etc.), AI infrastructure (Hugging Face, Replicate, etc.), cybersecurity firms with AI focus (CrowdStrike, Palo Alto, SentinelOne, etc.), AI red teaming startups.
We'll create a script that periodically refreshes the target list (e.g., weekly) and stores it in `targets/`.

### 5. Draft Email Template (Focus on Expertise)
Template should be concise, showcase credibility, and call to action (e.g., request a chat, share resume, ask for referral).
Example MML template:
```mml
From: dev.matheustheodoro@gmail.com
To: {{recipient_email}}
Subject: AI Security Expertise in Agentic Systems – Matheus Theodoro

Hi {{recipient_name}},

I’m reaching out because I’ve been following {{company_name}}’s work in {{specific_domain}} (e.g., AI agents, LLM security, autonomous systems) and believe my background in offensive security and AI agent hardening could be relevant to your team.

Briefly, I specialize in:
- **Red teaming AI agents**: designing adversarial attacks to test agent robustness (prompt injection, tool misuse, model inversion).
- **Defensive engineering**: implementing input validation, sandboxing, and monitoring for autonomous AI workflows.
- **AI supply chain security**: securing model serving, pipeline integrity, and dependency tracking for LLM-based systems.
- **Threat detection for AI**: building SIEM use cases for anomalous agent behavior, logging, and forensic readiness.

I’ve secured autonomous AI and computer vision agents at Avenza Security, designed mTLS-protected telemetry for AgTech drones, and built SIEM enhancements that cut incident response time by 40% (Elastic Stack on Kubernetes). My CV is attached for more detail.

I’m currently exploring opportunities to focus full‑time on AI security—particularly agentic security and AI red teaming. If you’re hiring or know of relevant teams, I’d appreciate a brief chat or a referral.

Please let me know a convenient time, or feel free to forward this to the appropriate teammate.

Best regards,
Matheus Theodoro
dev.matheustheodoro@gmail.com
linkedin.com/in/matheusht
github.com/matheusht
```
Attach the CV (we can encode as base64 or attach via Himalaya's attachment feature; we'll need to check Himalaya's MML for attachments).

### 6. Build the Outreach Script
We'll write a Python script (`scripts/send-outreach.py`) that:
- Loads the profile.
- Loads the target list (from GBrain or file).
- For each target not contacted in the last X days (cooldown, e.g., 30 days):
   - Personalizes the template (fill in company name, recipient name if known, specific domain from notes).
   - Optionally, fetch a recent news item or project to mention.
   - Sends email via Himalaya (using `subprocess` to pipe MML to `himalaya template send`).
   - Logs the send (timestamp, recipient, status, message-id).
   - Updates state to mark as sent and record timestamp.
- Handles errors (rate limits, auth failures) with backoff.
- Respects daily limit: stop after N emails (e.g., 50).

We'll also create a wrapper shell script that can be called by cron.

### 7. Schedule Autonomous Execution
We'll create a cron job (via Hermes cronjob tool) that runs the outreach script every 6 hours (or as desired). The cron job will:
- Change to the project directory.
- Ensure virtual environment/dependencies are present (if any).
- Run the script and capture output to a log.
- Optionally, send a summary to the user if something goes wrong.

### 8. Validation / Testing
- Send a test email to yourself to verify formatting, attachment, and deliverability.
- Run the script in "dry‑run" mode to see what emails would be sent without actually sending.
- Check that the brain is not corrupted by the outreach activities.
- Monitor logs for any failures.

## Files to Be Created / Changed
- `~/.hermes/ai-security-outreach/` (root)
  - `config/` – Himalaya config (already in ~/.config/himalaya, but we can copy a reference)
  - `profiles/matheus-theodoro.json`
  - `templates/outreach-expertise.mml`
  - `targets/companies.json` (or GBrain-backed)
  - `state/outreach-state.json`
  - `logs/sent.log`, `logs/errors.log`
  - `scripts/send-outreach.py`
  - `scripts/utils.py` (for scraping, personalization)
  - `cron-job.sh` (wrapper for cron)
- Cron job entry (managed by Hermes cronjob tool)

## Tests / Validation
- **Unit**: test personalization logic with mock data.
- **Integration**: send one real email and verify receipt.
- **Monitoring**: check logs after each cron run; alert on repeated failures.

## Risks, Tradeoffs, Open Questions
- **Rate Limits**: Gmail may block if too many emails sent; we mitigate by daily limit and cooldowns.
- **Deliverability**: Avoid spam folder by personalizing, not using spammy words, and keeping a clean sender reputation (Gmail is good).
- **Privacy**: We store contact info locally; ensure not to leak.
- **Legal**: Follow anti‑spam laws (CAN‑SPAM, GDPR if applicable) – include opt‑out mechanism? For job outreach, it's generally acceptable but we should honor requests to stop.
- **Scalability**: If we want to scale to hundreds of emails, we might need to rotate sending accounts or use a service; but for job search, tens per day is fine.
- **Authentication**: Himalaya needs secure storage of app password; we rely on the user's system keyring or pass.

## Next Steps for User
1. Provide Gmail App Password (or generate one) so we can configure Himalaya.
2. Confirm the focus areas for AI security (e.g., agentic red teaming, AI supply chain, monitoring for LLMs) to tailor the template.
3. Optionally, provide a list of target companies or let the agent build one via web search.
4. Once approved, we can move from plan to execution by creating the project folder and setting up the cron job.

---
*Plan saved at .hermes/plans/2026-04-24_2030-AI-Security-Outreach-Autonomous.md*