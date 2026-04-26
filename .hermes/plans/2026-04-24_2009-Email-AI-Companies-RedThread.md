# Plan: Email AI Companies about RedThread Project via Gmail (Himalaya)

## Goal
Send personalized emails to a curated list of AI companies introducing the RedThread project, emphasizing our unique approach to securing AI agents, and expressing interest in potential job/collaboration opportunities.

## Context / Assumptions
- Hermes Agent is installed with model-rotator skill active (using NVIDIA NIM).
- GBrain is installed with the RedThread wiki imported as the brain repository (~ /Documents/personal/redthread/docs/wiki).
- Himalaya CLI is not yet installed; we will install and configure it for Gmail via SMTP/IMAP using an App Password.
- We have a Gmail account (user to provide credentials) that can send emails.
- We will use the brain to store and retrieve target company information and email templates.
- Email sending should be done in batches to avoid rate limits; we will track sent messages in a log file.

## Proposed Approach
1. Install and configure Himalaya for Gmail.
2. Use GBrain to store a list of target AI companies (with contacts, notes).
3. Draft a master email template in MML/Himalaya-friendly format, with placeholders for personalization.
4. For each company, generate a personalized email by filling placeholders (company name, specific project angle, why RedThread fits).
5. Send emails via Himalaya, logging each send (timestamp, recipient, status).
6. Optionally, set up a follow‑up schedule (e.g., check for replies after 3 days).
7. Ensure compliance with Gmail sending limits (≈100 recipients/day for regular accounts).

## Step‑by‑Step Plan

### 1. Install Himalaya
```bash
# Pre‑built binary (recommended)
curl -sSL https://raw.githubusercontent.com/pimalaya/himalaya/master/install.sh | PREFIX=~/.local sh
# Ensure ~/.local/bin is in PATH
export PATH="$HOME/.local/bin:$PATH"
# Verify
himalaya --version
```
*(If cargo/rust is preferred, use `cargo install himalaya --locked`)*

### 2. Configure Gmail Account in Himalaya
- Obtain an **App Password** from Google Account (if 2FA enabled) or use normal password if less secure apps allowed (not recommended).
- Run the interactive wizard:
```bash
himalaya account configure
```
  - Choose IMAP for reading, SMTP for sending.
  - Set `imap.gmail.com` (port 993, TLS) and `smtp.gmail.com` (port 587, STARTTLS).
  - Store credentials securely (e.g., using `pass` or keyring).
- Alternatively, manually create `~/.config/himalaya/config.toml` with the above details.

### 3. Populate Brain with Target Companies
- Use GBrain to create a folder `companies/ai/` (or import existing list).
- For each target, create a markdown file with fields:
  ```
  ---
  name: Company Name
  website: https://...
  contact: person@email.com
  notes: Why they are a good fit for RedThread (security focus, AI agents, etc.)
  ---
  ```
- Example sources: AI safety labs, agent frameworks, AI infrastructure firms (Anthropic, OpenAI, Cohere, Hugging Face, Adept, Imbue, etc.).
- Use `gbrain import` or manual `write_file` via Hermes to add these.

### 4. Draft Email Template (MML)
Create a template file `email-templates/redthread-intro.mml`:
```mml
From: {{sender_email}}
To: {{recipient_email}}
Subject: Introducing RedThread – Securing AI Agents for {{company_name}}

Hi {{contact_name}},

I’ve been following {{company_name}}’s work in {{specific_area}} and am impressed by your focus on {{relevant_aspect}}.

I’m reaching out to share **RedThread**, a project that builds a secure, observable runtime for AI agents—think MemPalace + a knowledge‑graph backbone that enforces least‑privilege, logs every tool call, and enables automated policy enforcement.

Key points that may align with {{company_name}}’s goals:
- **Agent‑level sandboxing**: each agent runs with minimal capabilities, reducing blast radius.
- **Tamper‑evident logging**: every action is written to an append‑only log, enabling forensic analysis.
- **Policy‑as‑code**: security rules live alongside the agent, making them version‑controlled and auditable.
- **Knowledge‑grounded reasoning**: the agent consults a trusted internal wiki (like your own internal docs) before acting, reducing hallucinations and unsafe actions.

I would love to discuss how RedThread could complement {{company_name}}’s efforts, whether as a potential collaboration, consulting role, or full‑time position focused on AI agent security.

Are you open to a brief 15‑minute call next week? Please let me know a time that works for you, or feel free to forward this to the appropriate teammate.

Best regards,
{{your_name}}
{{your_linkedin_or_website}}
```
- Placeholders will be replaced via a small script (see step 5).

### 5. Personalize and Send Emails
Write a Python/Hermes script that:
1. Lists all company files in brain (`companies/ai/*.md`).
2. For each, extracts front‑matter (name, website, contact, notes).
3. Reads the template, replaces placeholders:
   - `{{sender_email}}` → your Gmail address
   - `{{recipient_email}}` → contact email
   - `{{company_name}}` → company name
   - `{{contact_name}}` → first name or full name from contact
   - `{{specific_area}}` → derived from notes or website (or ask user to fill)
   - `{{relevant_aspect}}` → from notes
   - `{{your_name}}`, `{{your_linkedin_or_website}}` → user‑provided signature
4. Calls Himalaya to send:
   ```bash
   cat personalized.mml | himalaya template send
   ```
5. Logs result to `~/hermes/logs/redthread-email-sent.log` (timestamp, company, status, message‑id).
6. Respects rate limits: sleep 1‑2 seconds between sends, stop after 80/day.

### 6. Track Replies & Follow‑Up
- Use Himalaya to search INBOX for replies containing “RedThread” or your subject.
- After 3 days, send a polite follow‑up to non‑responders (template: “Just checking if you had a chance to review…”).
- Optionally, add a label in Gmail (e.g., `RedThread/Outreach`) via Himalaya’s tagging.

### 7. Validation / Testing
- Send a test email to yourself first to verify formatting and deliverability.
- Check that the brain still functions after the outreach (no corruption).
- Review sent log for any errors; retry failed sends after a delay.

## Files Likely to Change / Be Created
- `~/.config/himalaya/config.toml` (Himalaya account config)
- Brain files under `companies/ai/` (new company markdowns)
- `email-templates/redthread-intro.mml` (template)
- `~/hermes/logs/redthread-email-sent.log` (sent‑mail log)
- Optional: `~/hermes/scripts/send-redthread-emails.py` (personalization script)
- Himalaya cache/directory under `~/.local/share/himalaya/` (created by tool)

## Tests / Validation
- **Unit**: script placeholder substitution correctness (can be tested with `python -m doctest`).
- **Integration**: send one test email and verify receipt.
- **Monitoring**: check Himalaya logs for errors; ensure no auth failures.

## Risks, Tradeoffs, Open Questions
- **Rate Limits**: Gmail may temporarily block sending if too many emails are sent quickly; mitigation: batch and sleep.
- **Deliverability**: Emails may land in spam; mitigation: avoid spammy language, personalize each mail, use a proper From address with SPF/DKIM (Gmail already does).
- **Privacy**: Storing contact emails in brain is fine as it’s local; ensure not to push brain to public repo inadvertently.
- **Tool Availability**: Himalaya must be installed; plan includes installation step.
- **User Input Needed**: Gmail address, app password, personal signature, list of target companies (or we can auto‑gather via web search – but that adds complexity).

## Next Steps for User
1. Provide Gmail address and generate an App Password (or approve less‑secure apps).
2. Confirm or edit the list of target AI companies (or let the agent suggest a starter list).
3. Approve the email template or suggest tweaks.
4. Once confirmed, we can move from plan to execution (would require leaving plan mode).

---
*Plan saved at .hermes/plans/2026-04-24_2009-Email-AI-Companies-RedThread.md*