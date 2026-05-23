# Security Policy

RetailOps CLI stores API tokens in the local user config file:

- Windows: `%APPDATA%\retailops\config.toml`
- macOS/Linux: `~/.config/retailops/config.toml`

Do not commit config files, `.env` files, API tokens, kiosk keys, or screenshots
that expose credentials.

## Reporting A Vulnerability

Open a private security advisory on GitHub if available, or contact the project
maintainer directly. Include:

- affected version or commit,
- operating system,
- command or workflow involved,
- expected behavior,
- actual behavior,
- impact and reproduction steps.

Please do not publish exploit details publicly until the issue has been triaged.
