# Discord Commands

Discord control is disabled by default. Enable it in the project config and set the bot identity and allowlist before use.

```toml
[discord]
enabled = true
token_file = "/home/nama/discord-api-key.txt"
bot_name = "AgentDev"
channel_id = "..."
allowed_guild_ids = ["..."]
allowed_channel_ids = ["..."]
allowed_user_ids = ["..."]
skip_existing_on_startup = true
max_command_age_sec = 60.0
```

The worker polls the configured channel in a background thread. If several commands arrive while Discord is unreachable, only the newest fresh command is considered. Commands older than `max_command_age_sec` are logged as stale and are not executed.
On startup, the first successful poll only records the latest existing message as the baseline when `skip_existing_on_startup` is true. This prevents the bot from re-running a command that was already handled before the process restarted.

## CLI-Only Mode

To run only the Discord integration without opening the WebUI HTTP server:

```sh
python3 pi/app.py --mode discord --config config/local.toml
```

In this mode, Discord polling and command execution are printed to the console. The WebUI API surface is still reused internally through the Flask app, but no browser-facing server is started.

For a one-shot connectivity check:

```sh
python3 pi/app.py --mode discord --config config/local.toml --discord-once
```

## Command Forms

| Command | Meaning |
| --- | --- |
| `@AgentDev open browser` | Run `open browser` as a Planning request. This is the default. |
| `@AgentDev request: open browser` | Same as above, explicit request form. |
| `@AgentDev hid: KEY WIN+R` | Send a direct Manual HID command. Use only for low-level checks. |
| `@AgentDev screen` | Send the latest screenshot to Discord. |
| `@AgentDev stop` | Trigger emergency stop. |
| `@AgentDev approve` | Approve the current pending approval request. |
| `@AgentDev reject` | Reject the current pending approval request. |

Slash-compatible forms such as `/screen`, `/request open browser`, `/approve`, and `/reject` are accepted for test compatibility, but normal operation should use the bot mention form.

## Safety Rules

- Only configured guilds, channels, and users are accepted.
- Direct HID requires the `hid:` prefix. Plain text mention commands are Planning requests.
- Only the newest newly observed Discord command is executed per poll.
- Old commands are ignored after `max_command_age_sec` to prevent backlog execution after a Discord outage.
- The worker sends a screenshot only after command completion or when `screen` is requested.
- Screenshot attachments larger than `attachment_limit_mb` are omitted and logged.
- Discord polling and Discord send operations run outside the WebUI request path, so WebUI API responses are not blocked by Discord API calls.
