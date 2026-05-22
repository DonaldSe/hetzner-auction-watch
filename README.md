# hetzner-auction-watch

> Surveille [Hetzner Server Auction](https://www.hetzner.com/sb/) et notifie
> via **ntfy.sh** ou **Discord** dès qu'un serveur matchant tes filtres apparaît.

Stack : Python 3.12 + `requests` + `click` + `pyyaml`. ~250 lignes total.
Container Docker pré-buildé, OCI-compatible.

## Pourquoi

Hetzner Server Auction tourne en continu : prix baissent au fil des heures
selon la demande, et les bonnes affaires (Ryzen 7 7700 DDR5 < 40 €/mois)
partent en quelques minutes. Polling manuel = tu rates. Polling auto + notif
mobile = tu choppes.

## Quickstart (local)

```bash
git clone https://github.com/DonaldSe/hetzner-auction-watch.git
cd hetzner-auction-watch

# Toolchain
mise install            # Python 3.12 dans .venv

# Deps
pip install -e .

# Config
cp config.yaml.example config.yaml
$EDITOR config.yaml     # ajuste prix max, CPU regex, datacenters
cp .env.example .env
$EDITOR .env            # NTFY_TOPIC ou DISCORD_WEBHOOK

# Run one-shot (test)
hetzner-watch -v

# Run en daemon (loop 15min)
hetzner-watch --daemon --interval 900
```

## Notifications

### ntfy.sh (recommandé, zéro config)

1. Installe l'app `ntfy` sur ton téléphone (App Store / Google Play / F-Droid).
2. Choisis un nom de topic random : `hetzner-watch-d8x7q3` (chaîne aléatoire = pseudo-privé).
3. Subscribe au topic dans l'app.
4. Pose `NTFY_TOPIC=hetzner-watch-d8x7q3` dans `.env`.
5. → push notifs gratuites, latence ~1s.

Pour un setup self-hosted (pas de dépendance ntfy.sh public) :
```bash
NTFY_URL=https://ntfy.toi.fr
NTFY_TOPIC=hetzner
NTFY_TOKEN=tk_xxx   # si protégé
```

### Discord webhook

1. Dans ton serveur Discord : `Channel settings → Integrations → Webhooks → New`.
2. Copy l'URL.
3. Pose `DISCORD_WEBHOOK=https://discord.com/api/webhooks/...` dans `.env`.

Tu peux activer les **deux** simultanément (ntfy en push mobile + Discord en archive).

## Config — exemples concrets

`config.yaml` :

```yaml
filters:
  # Sweet spot Ryzen 7 7700 DDR5 ≤45€/mois
  - name: "ryzen-7700"
    ram_min_gb: 64
    price_max_eur: 45.0
    cpu_regex: "Ryzen 7 7700"
    disk_type: "nvme"
    disk_count_min: 2
    datacenters: ["FSN", "HEL"]
    ecc_required: false

  # Deal de fou : toute machine 64GB+ ≤35€
  - name: "deal-de-fou"
    ram_min_gb: 64
    price_max_eur: 35.0
    cpu_regex: ".*"
    disk_type: "nvme"
    disk_count_min: 2
    datacenters: ["FSN", "HEL", "NBG"]
```

Chaque filtre est évalué indépendamment. Un même serveur qui match plusieurs
filtres = plusieurs notifs (dédupliquées par `(filter_name, server_id)` via
`.state.json`).

## Déploiement

### En cron (recommandé pour single-shot)

```cron
# /etc/cron.d/hetzner-watch
*/15 * * * * watch  cd /opt/hetzner-watch && /opt/hetzner-watch/.venv/bin/hetzner-watch
```

### En daemon systemd

```ini
# /etc/systemd/system/hetzner-watch.service
[Unit]
Description=Hetzner Auction Watch
After=network-online.target

[Service]
Type=simple
User=watch
WorkingDirectory=/opt/hetzner-watch
EnvironmentFile=/opt/hetzner-watch/.env
ExecStart=/opt/hetzner-watch/.venv/bin/hetzner-watch --daemon --interval 900
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

### Docker / compose

```bash
cp config.yaml.example config.yaml
cp .env.example .env
$EDITOR config.yaml .env
docker compose up -d
docker compose logs -f
```

## CLI

```
Usage: hetzner-watch [OPTIONS]

  --config PATH       Chemin config.yaml          [default: config.yaml]
  --state PATH        Chemin état dédoublonnage    [default: .state.json]
  --daemon            Boucle infinie              [default: off, cron-friendly]
  --interval INTEGER  Sleep daemon en secondes    [default: 900]
  -v, --verbose       Log DEBUG
  --help              Affiche l'aide
```

## État (`.state.json`)

Le fichier stocke les `(filter_name, server_id)` déjà notifiés pour éviter
le spam. Format : liste JSON.
Supprimer le fichier = re-notifier de zéro pour les serveurs déjà en auction.

## Champs JSON Hetzner exposés

Le script lit `https://www.hetzner.com/_resources/app/jsondata/live_data_sb_EUR.json`
et matche sur ces champs (cf. `match()` dans `hetzner_watch.py`) :

- `name` : modèle (AX42, EX44, etc.)
- `cpu` : description CPU
- `cpu_benchmark` : score interne Hetzner
- `ram_size` : Go
- `hdd_arr` : liste descriptions disques
- `hdd_count` : nombre de disques
- `is_ecc` : bool
- `datacenter` : ex `FSN1-DC18`
- `price` : EUR/mois

## Idées d'extension

- Telegram bot notification (au lieu de Discord)
- Score multi-critères `(perf/€)` au lieu de filtres binaires
- Historique prix dans SQLite + graphes Grafana
- Re-listing automatique des deals sur Mastodon/Twitter

PRs welcome.

## License

Apache 2.0.
