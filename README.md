# Email AI Agent (MCP + Gmail + Gemini)

[![Live Demo](https://img.shields.io/badge/Streamlit-Live%20Demo-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://email-agent-6j71.onrender.com/)

> 🌐 **Try it Live:** [**Open Streamlit Web App**](https://email-agent-6j71.onrender.com/) — Chat directly with your Gmail via the deployed interface!

Chat with your Gmail. Ask the agent to read, search, summarise and send email, with your resume attached.

```
you> Send a mail to hr@example.com asking for AI Engineer opportunities and attach my resume
you> Do I have any important mails today?
```

## Architecture

```
You -> agent/ (LLM loop + approval) -> MCP client -> mcp_server/ (Gmail tools) -> Gmail API
```

Sending, replying and trashing always ask for your approval first.

## Setup

### 1. Install
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
Create a `.env` file in the root directory and fill it with your details:
```env
GEMINI_API_KEY=your_gemini_api_key_here
MODEL=gemini-2.5-flash
MAX_AGENT_STEPS=10

USER_NAME=Your Name
USER_SIGNATURE=Your Name | +91-XXXXXXXXXX | linkedin.com/in/yourprofile
USER_PROFILE=AI/ML engineer with experience in Python, LLMs, RAG, and agents.

RESUME_DIR=resumes
DEFAULT_RESUME=my_resume.pdf
DOWNLOAD_DIR=downloads

MAX_BODY_CHARS=6000
```

### 2. Google Cloud (one time)
1. Go to https://console.cloud.google.com and create a project.
2. **APIs & Services > Library**: enable the **Gmail API**.
3. **OAuth consent screen**: choose External, fill the basics, and add your own Gmail as a **Test user**.
4. **Credentials > Create credentials > OAuth client ID > Desktop app**.
5. Download the JSON and save it as `credentials/credentials.json`.

### 3. Add your resume
Copy your PDF into `resumes/` and set `DEFAULT_RESUME` in `.env` to its file name.
Only files inside `resumes/` can ever be attached.

### 4. Log in to Gmail (once)
```bash
python -m mcp_server.gmail_client
```
A browser opens, you approve access, and `credentials/token.json` is created.
If you change scopes later, delete `token.json` and log in again.
Note: while the consent screen is in "Testing" mode, Google expires the token after about 7 days, so re-run this command when asked.

### 5. Run
```bash
python -m agent.main             # terminal chat
streamlit run ui/app.py          # optional web UI
python -m pytest                 # tests (no Gmail needed)
```

Terminal commands: `/important`, `/followups [days]`, `/sent`, `/tools`, `/reset`, `/help`, `/exit`.

## Use the MCP server with Claude Desktop instead

Skip `agent/` and add this to Claude Desktop's config (use absolute paths):
```json
{
  "mcpServers": {
    "email-agent": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/email-agent"
    }
  }
}
```
Claude Desktop asks for permission before each tool call, which serves as the approval step there.

## Tools exposed by the MCP server

| Group | Tools |
|---|---|
| Read | `get_my_profile`, `list_emails`, `get_unread_emails`, `search_emails`, `read_email`, `read_thread`, `thread_has_reply` |
| Send | `send_email`, `create_draft`, `list_drafts`, `send_draft`, `reply_to_email` |
| Manage | `mark_as_read`, `mark_as_unread`, `archive_email`, `star_email`, `unstar_email`, `list_labels`, `add_label`, `remove_label`, `trash_email` |
| Files | `list_available_files`, `list_email_attachments`, `download_attachment` |

## Safety design

- Human approval before `send_email`, `send_draft`, `reply_to_email`, `trash_email`.
- Attachments restricted to the `resumes/` folder (no path traversal).
- Email text is treated as untrusted data; the system prompt tells the model never to follow instructions inside emails.
- Address and header validation blocks header injection.
- Secrets and personal data (`.env`, `credentials/*.json`, `resumes/`, `downloads/`, `storage/`) are git-ignored.
