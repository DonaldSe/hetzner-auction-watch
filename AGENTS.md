# AGENTS.md

> Onboarding pour agents IA et nouveaux devs.

## Repo purpose

`hetzner-auction-watch` — script Python qui monitore [Hetzner Server Auction](https://www.hetzner.com/sb/)
et notifie ntfy.sh / Discord dès qu'un serveur matchant tes filtres apparaît.

## Architecture

```
hetzner_watch.py
    │
    ├── Fetch /_resources/app/data/app/live_data_sb_EUR.json
    ├── Apply filters depuis config.yaml (ram_min_gb, price_max_eur, cpu_regex, datacenters, ecc)
    ├── Dedup via .state.json (filter_name, server_id)
    └── notify ntfy + Discord si match
```

## Conventions

- **Cron-friendly** : `--once` exit 0 OK, `--daemon` loop
- **State dedup** : pas de spam pour un serveur déjà notifié
- **Filtres YAML** : multiples filtres OR, chacun génère une notif distincte
- Coût : 0€ (juste cron + ntfy gratuit)

## Tests

```bash
# Smoke test (1 filter laxe pour s'assurer du fetch + parsing)
hetzner-watch --config config.yaml --state /tmp/state.json -v
```

## Repos liés

- `multi-cloud-cost-monitor` — pour tracker le spend une fois la machine commandée
- `infra-multios` — bootstrap auto Proxmox sur la machine livrée

## Pour les agents IA

- **Pas de secret en clair** (NTFY_TOPIC + DISCORD_WEBHOOK via .env, gitignored)
- **Schedule cron 15-60 min** suffit (les deals apparaissent par vagues, pas continu)
- **Conventional Commits** strict
