# ☪ Haram Blocker v1.0

A Linux desktop app that blocks Haram websites **system-wide** via `/etc/hosts`.

---

## 🚫 What it blocks (200+ domains)

| Category | Examples |
|---|---|
| 🔞 Adult / 18+ | PornHub, XVideos, xHamster, OnlyFans, Fansly, Chaturbate, e-hentai… |
| 🎰 Betting & Gambling | Bet365, 1xBet, PokerStars, Stake, Roobet, DraftKings, Betfair… |
| 💔 Dating & Hookup | Tinder, Bumble, Badoo, Hinge, OkCupid, AdultFriendFinder… |
| 🚬 Alcohol & Drugs | Leafly, Weedmaps, Drizly, Erowid, Shroomery… |

---

## Features
-  **System-wide** — blocks in all browsers, no extension needed
-  **Password protection** — disabling requires your password
-  **Toggle categories** — enable/disable each category
-  **Custom sites** — add any domain you want
-  **Auto www variants** — blocks both `domain.com` and `www.domain.com`
-  **Polished dark GUI** — clean tabbed interface

---

## 🚀 Quick Start

```bash
# Install dependency
sudo apt install python3 python3-tk

# Run directly
python3 haram_blocker.py
```

> Default password: **bismillah** — change it immediately after first launch!

---

## 📦 Install System-Wide

```bash
bash install.sh
# Then launch with:
haram-blocker
```