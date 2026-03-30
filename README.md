# Claude Code Feature Flags Dumper

Dump all GrowthBook feature flags from Claude Code's remote eval API.

Extracted by reverse engineering the Claude Code CLI binary (`Mach-O arm64`), including:
- GrowthBook SDK client key
- Remote eval endpoint (`POST /api/eval/{clientKey}`)
- User attributes schema (deviceId, accountUUID, organizationUUID, etc.)
- 178 feature flags with Chinese descriptions and functional categories

## Usage

```bash
# Pretty print with categories
python3 claude_features.py

# Only show A/B experiments
python3 claude_features.py --experiments

# Raw JSON output
python3 claude_features.py --json
```

## Requirements

- Python 3.7+  (standard library only, no pip install needed)
- Claude Code installed and logged in (OAuth)
- macOS or Linux

## How it works

1. Reads `~/.claude.json` (or `~/.claude/.config.json`) for deviceId, accountUUID, etc.
2. Extracts OAuth token from system keychain (macOS `security` / Linux `secret-tool`)
3. Sends `POST https://api.anthropic.com/api/eval/sdk-zAZezfDKGoZuXXKe` with user attributes
4. Parses and displays feature flags grouped by category with Chinese descriptions

## Screenshot

![output](screenshot.png)

## Disclaimer

This tool is for educational and security research purposes. The GrowthBook client key (`sdk-zAZezfDKGoZuXXKe`) is embedded in the publicly distributed Claude Code binary.
