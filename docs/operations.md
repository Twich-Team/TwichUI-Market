# Operations

Use only `docker --context rootless` and project-scoped Compose commands. Do not enumerate or modify unrelated containers. No sudo. Before startup inspect `ss -ltn`, `free -h`, `df -h .` and confirm rootless security options. Services bind to 127.0.0.1; external HTTPS/domain/firewall work requires a separate administrator action and is not authorized here.

Never put credentials in command arguments, Git, logs or fixtures. Read Blizzard credentials from environment. Store local configuration in ignored .env. Probe output must exclude access tokens and Authorization headers.

Deployment, backup, restoration and Windows release instructions will be added alongside verified implementations. No running production service or backup verification exists yet.
