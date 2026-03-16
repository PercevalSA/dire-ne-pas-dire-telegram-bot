# dire-ne-pas-dire-telegram-bot

Bot Telegram qui t’envoie chaque jour un article “dire, ne pas dire” de l’Académie française, sans renvoyer les articles déjà envoyés. Il vérifie aussi périodiquement s’il y a un nouvel article et l’envoie dès qu’il apparaît.

## Prérequis

- Linux
- Python 3.11+ recommandé
- Un bot Telegram (via @BotFather) et son token

## Installation

```bash
cd /home/perceval/funspace/academie-fr-dnpd-tgbot
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Variables d’environnement attendues :

- `BOT_TOKEN` (obligatoire) : token Telegram du bot
- `CHAT_ID` (optionnel) : id du chat (toi). Si absent, le bot l’enregistre automatiquement au premier `/start` et utilise directement le DM.
- `TZ` (optionnel) : timezone, défaut `Europe/Paris`
- `DAILY_TIME` (optionnel) : heure d’envoi quotidien `HH:MM`, défaut `09:00`
- `CHECK_INTERVAL_MIN` (optionnel) : minutes entre vérifications “nouvel article”, défaut `60`
- `DB_PATH` (optionnel) : chemin SQLite. Par défaut `/var/lib/academie-fr-dnpd-tgbot/bot.db` (si writable), sinon `~/.local/share/academie-fr-dnpd-tgbot/bot.db`

Exemple :

```bash
export BOT_TOKEN="123:abc"
export CHAT_ID="123456789"
export TZ="Europe/Paris"
export DAILY_TIME="09:00"
export CHECK_INTERVAL_MIN="60"
export DB_PATH="/var/lib/academie-fr-dnpd-tgbot/bot.db"
```

## Lancer en local

```bash
source .venv/bin/activate
python -m bot.main
```

Dans Telegram :
- `/start` pour confirmer que le bot répond
- `/chatid` pour voir l’id du chat (debug)
- `/next` pour recevoir immédiatement le prochain article non envoyé

## Déploiement Linux (systemd)

1) Crée un dossier de données (ex. `/var/lib/academie-fr-dnpd-tgbot`) et donne les droits à l’utilisateur du service.

2) Crée un fichier d’environnement, par exemple `/etc/academie-fr-dnpd-tgbot.env` :

```bash
BOT_TOKEN="..."
CHAT_ID="..."
TZ="Europe/Paris"
DAILY_TIME="09:00"
CHECK_INTERVAL_MIN="60"
DB_PATH="/var/lib/academie-fr-dnpd-tgbot/bot.db"
```

3) Unité systemd (ex. `/etc/systemd/system/academie-fr-dnpd-tgbot.service`) :

```ini
[Unit]
Description=Academie francaise Dire-ne-pas-dire Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/perceval/funspace/academie-fr-dnpd-tgbot
EnvironmentFile=/etc/academie-fr-dnpd-tgbot.env
ExecStart=/home/perceval/funspace/academie-fr-dnpd-tgbot/.venv/bin/python -m bot.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

4) Active et démarre :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now academie-fr-dnpd-tgbot.service
sudo systemctl status academie-fr-dnpd-tgbot.service
```

