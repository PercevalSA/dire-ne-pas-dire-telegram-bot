# dire-ne-pas-dire-telegram-bot

Bot Telegram qui t’envoie chaque jour un article “dire, ne pas dire” de l’Académie française, sans renvoyer les articles déjà envoyés. Il vérifie aussi périodiquement s’il y a un nouvel article et l’envoie dès qu’il apparaît.

## Prérequis

- Linux
- Python 3.11+ recommandé
- Un bot Telegram (via @BotFather) et son token

## Installation

### Installation locale manuelle

```bash
# cloner le dépôt
git clone https://github.com/PercevalSA/dire-ne-pas-dire-telegram-bot.git
cd dire-ne-pas-dire-telegram-bot

# installation locale
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

### Installation pour déploiement 

```bash
python3 -m pip install https://github.com/PercevalSA/dire-ne-pas-dire-telegram-bot.git
```

## Configuration

Variables d’environnement attendues :

- `BOT_TOKEN` (obligatoire) : token Telegram du bot
- `CHAT_ID` (optionnel) : id du chat (toi). Si absent, le bot l’enregistre automatiquement au premier `/start` et utilise directement le DM.
- `TZ` (optionnel) : timezone, défaut `Europe/Paris`
- `DAILY_TIME` (optionnel) : heure d’envoi quotidien `HH:MM`, défaut `09:00`
- `CHECK_INTERVAL_MIN` (optionnel) : minutes entre vérifications “nouvel article”, défaut `60`
- `DB_PATH` (optionnel) : chemin SQLite. Par défaut `/var/lib/dire-ne-pas-dire-telegram-bot/bot.db` (si writable), sinon `~/.local/share/dire-ne-pas-dire-telegram-bot/bot.db`

Exemple :

```bash
export BOT_TOKEN="123:abc"
export CHAT_ID="123456789"
export TZ="Europe/Paris"
export DAILY_TIME="09:00"
export CHECK_INTERVAL_MIN="60"
export DB_PATH="/var/lib/dire-ne-pas-dire-telegram-bot/bot.db"
```

## Lancer en local

```bash
venv .venv
source .venv/bin/activate
python -m pip install .
export BOT_TOKEN="123:abc"
python -m dire_ne_pas_dire_telegram_bot
```

Dans Telegram :
- `/demarrer` (ou `/start`) pour confirmer que le bot répond
- `/identifiant` (ou `/chatid`) pour voir l’id du chat (debug)
- `/prochain` ou `/article` (ou `/next`) pour recevoir immédiatement le prochain article non envoyé

## Déploiement Linux (systemd)

Ici on suppose une installation pour déploiement.

- `systemd` crée automatiquement le dossier de données via `StateDirectory=`
- l’utilisateur du service peut être créé automatiquement via `DynamicUser=yes`
- systemd` créé automatiquement le fichier de configuration dans `StateDirectory`


 1. Ajoute le token du bot dans le fichier d’environnement
 2. Copie l’unité systemd fournie par le projet
    ```bash
    wget -O dire-ne-pas-dire-telegram-bot.service https://raw.githubusercontent.com/PercevalSA/dire-ne-pas-dire-telegram-bot/main/deploy/dire-ne-pas-dire-telegram-bot.service
    sudo cp dire-ne-pas-dire-telegram-bot.service /etc/systemd/system/dire-ne-pas-dire-telegram-bot.service
    ```
sudo /opt/dnpd-telegram-bot/venv/bin/pip install dire-ne-pas-dire-telegram-bot
```

4) Recharge systemd et démarre le service :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dire-ne-pas-dire-telegram-bot.service
sudo systemctl status dire-ne-pas-dire-telegram-bot.service
```

