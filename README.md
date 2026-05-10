# Simple Chain Daily Bot 🤖

Automated daily bot for [Simple Chain](https://task.simplechain.com?inviteCode=9v5lpvicc3b), built by **DEGIO**.

Runs every 24 hours — performs wallet login, visit task, and daily check-in automatically.

---

## Features

- ✅ Daily check-in automation
- ✅ Visit task automation
- ✅ Multi-wallet support
- ✅ Optional proxy support
- ✅ Loops every 24 hours automatically

---

## Requirements

- Python 3.8+
- pip packages (see `requirements.txt`)

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/simplechain-daily-bot.git
cd simplechain-daily-bot
pip install -r requirements.txt
```

---

## Configuration

### 1. `keys.txt` — Private Keys (required)

One Ethereum private key per line:

```
0xYOUR_PRIVATE_KEY_1
0xYOUR_PRIVATE_KEY_2
```

> ⚠️ **Never share your private keys or commit `keys.txt` to GitHub.** It is already in `.gitignore`.

### 2. `proxy.txt` — Proxies (optional)

One proxy per line:

```
http://user:pass@host:port
socks5://user:pass@host:port
ip:port
```

Leave the file empty or omit it entirely to run without proxies.

---

## Usage

```bash
python3 bot.py  or  python bot.py
```

The bot will:
1. Run immediately on start
2. Repeat every 24 hours automatically

---

## Running in Background

**Linux/macOS (screen):**
```bash
screen -S simplechain
python3 bot.py
# Detach: Ctrl+A then D
# Reattach: screen -r simplechain
```

**Linux (nohup):**
```bash
nohup python3 bot.py > bot.log 2>&1 &
```

---

## File Structure

```
simplechain-daily-bot/
├── bot.py               # Main bot script
├── keys.txt             # Private keys (not committed)
├── proxy.txt            # Proxies (not committed, optional)
├── keys.example.txt     # Sample keys format
├── proxy.example.txt    # Sample proxy format
├── requirements.txt
└── README.md
```

---

## Disclaimer

This bot is for educational purposes only. Use at your own risk. The author is not responsible for any loss of funds or account bans. Always keep your private keys safe.

---

## License

MIT License
