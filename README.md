# 🌳 Aura (The Caretaker) - Treehouse Hangout Bot

Aura is a specialized Discord bot designed to manage private, cozy, friends-only communities. Its focus is on providing subtle administrative support and interactive fun, rather than strict, public community enforcement. Aura handles security, logging, and metrics, ensuring your hangout remains a comfortable and safe space.

## ☕ Core Philosophy

This bot is built for the "Treehouse Hangout" model:
* **Private First:** No public verification system is needed. Access is managed by the Host and Co-Hosts.
* **Cozy Moderation:** Administrative actions are framed as "Time-Outs" or "Barrings."
* **Interactive Presence:** Includes a generative AI feature (`!vibe`) to add flavor and atmosphere to the chat.

---

## ✨ Key Features

* **Atmosphere Setter (`!vibe`):** An interactive command powered by the Gemini API that generates short, relevant, and fun responses based on a user's topic to enhance the current chat mood.
* **Essential Security:** Includes an automated **Ban Evasion Check** upon member entry to ensure previously barred guests cannot silently return.
* **Simplified Flagging (`!flag`):** A discreet, easy-to-use command for any guest to report a concern privately to the Host/Co-Hosts.
* **Caretaker Log:** A web-based **Caretaker Log** (`/admin` dashboard) for the Host to view server metrics, activity, and the full moderation history (Guestbook).
* **Clean-Up Toolkit:** Core commands for Co-Hosts to handle spam and temporary disruptions (`!purge`, `!mute`, `!kick`).

---

## 🛠️ Bot Commands (Prefix: `!`)

### All Guests

| Command | Description |
| :--- | :--- |
| `!vibe [topic]` | Aura provides a fun, short, and thematic response based on your input (e.g., `!vibe rainy day`). |
| `!flag @Guest [reason]` | Discreetly sends a private note about a concern to the Host/Co-Hosts in the alert channel. |

### Co-Hosts / Host (Requires `manage_messages` permission)

| Command | Description |
| :--- | :--- |
| `!commands` | Displays the full list of Caretaker commands and their usage. |
| `!say #channel [message]` | Aura broadcasts a message to the specified channel (Host/Co-Host voice). |
| `!purge [count]` | Cleans up clutter (deletes the specified number of messages). |
| `!kick @Guest [reason]` | Issues a Temporary Time-Out (removes the guest from the server). |
| `!mute @Guest [reason]` | Applies a Chat Time-Out (restricts chat ability). |
| `!unmute @Guest` | Removes the Chat Time-Out restriction. |
| `!ban @Guest [reason]` | Applies Permanent Barring (bans the guest). |
| `!whois @Guest` | Checks a guest’s Sign-in History (moderation logs). |

---

## 📝 Roles and Terminology

The bot operates using these themed roles and names:

| Concept | Role / Name | Description |
| :--- | :--- | :--- |
| Bot Name | Aura (The Caretaker) | The friendly administrative presence. |
| Server Owner | Host | The owner of the server. |
| Moderator | Co-Host | Trusted helpers with management tools. |
| Standard Member | Regular | The default role for confirmed members (manually assigned). |
| Mute Role | Time-Out | Role used to restrict chat privileges. |
| Dashboard | Caretaker Log (`/admin`) | Web interface for metrics and logging. |

---

## ⚙️ Setup and Configuration

Aura requires specific environment variables to function properly.

### Required Environment Variables

| Variable | Description | Notes |
| :--- | :--- | :--- |
| `DISCORD_BOT_TOKEN` | Your Discord Bot's Token. | Required for bot login. |
| `ADMIN_USER` | Username for the `/admin` dashboard login. | Required for dashboard access. |
| `ADMIN_PASS` | Password for the `/admin` dashboard login. | Required for dashboard access. |
| `MOD_ALERT_CHANNEL_ID` | The numerical ID of your Co-Host alert channel. | Used for `!flag`, `!kick`, `!ban` notifications. |
| `WELCOME_CHANNEL_ID` | The numerical ID of your welcome channel. | Used for the `on_member_join` message. |
| `API_KEY` | The Gemini API Key. | Required for the fun `!vibe` command functionality. |

### Role Configuration

Ensure the following roles exist in your Discord server with the exact names configured in `bot_logic.py`:
* `Regular` (Set as `MEMBER_ROLE_NAME`)
* `Time-Out` (Set as `MUTED_ROLE_NAME`)
* `Co-Host` (Set as `STAFF_ROLE_NAME` - must have **Manage Messages** permission)
