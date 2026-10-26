# Clash of Clans "Fishing" Automation · Cloud-Phone Room System

[简体中文](readme.md) | **English**

Resource farming automation for Clash of Clans (known in the Chinese community as "fishing" / 打鱼), plus a multi-tenant room backend built on cloud phones.

Users do not need a physical Android device: the backend binds one cloud phone instance to a "room", and the user watches the device stream and sends input straight from the browser. On the server side, a per-room automation thread drives `adb` + OpenCV template matching through the full loop of finding a target, deploying an army, attacking, fast-forwarding, and collecting loot.

Either way you run it, you need **a cloud phone (or Android device) with adb debugging enabled**: every step the script takes is "adb screenshot → template match → adb tap". The database is only needed for room mode — standalone farming runs without any schema (see [Quick start](#quick-start)).

> **Disclaimer**
> This project exists to explore automation testing and image recognition. Botting in Clash of Clans violates the Supercell Terms of Service and can get an account **banned**; you assume that risk yourself.
> The project does not read or write game memory, reverse engineer protocols, or modify the client. Every action is "screenshot → recognize → simulated tap".
> Clash of Clans assets and trademarks belong to Supercell. The template screenshots under `asserts/` exist only as matching references and are **not** licensed under this repository's license (see [License](#license)).

---

## Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Database tables](#database-tables)
- [Running the service](#running-the-service)
- [Scheduled jobs](#scheduled-jobs)
- [Rooms and permissions](#rooms-and-permissions)
- [API overview](#api-overview)
- [The farming loop](#the-farming-loop)
- [Frontend](#frontend)
- [Before you publish](#before-you-publish)
- [License](#license)

---

## What it does

- **Room lobby** — lists every room, who is currently using it, busy/idle state, and remaining time.
- **Take control** — a non-owner must pass the permission check (see [Rooms and permissions](#rooms-and-permissions)) before grabbing control of a room.
- **Automated farming** — start/stop with one click; CN and international servers (`fish_server`), league and wars modes, and two separate flows for the home village and the night market.
- **Army composition presets** — choose a strategy (铅笔天使 / dragon / golem-hybrid etc.) and the server deploys the reinforcement troops in the configured order; see `src/battle_util.py`.
- **Live status over SSE** — farming logs, remaining time, and keep-alive state are pushed to the browser.
- **Time accounting** — a room consumes the user's quota while it is in use; when the quota runs out the farming thread stops and the room is reclaimed.
- **Email notifications** — three HTML templates: farming failure, verification code, system notice.
- **Reinforcement donation** — `src/donate_soldiers.py` drives the clan donation flow on its own.

## Architecture

```
Browser H5 (separate repository)
   │  REST + SSE
   ▼
Flask app  :8848  ──► PostgreSQL (users / rooms / cloud phones / ads / logs)
   │                ──► Redis (cache, rate-limit counters, token blocklist, strategy & task state)
   │                ──► China Telecom Jilan cloud phone OpenAPI (playback URL, command channel)
   │
   └─► one farming thread per room (adbutils + uiautomator2 + OpenCV matching) ──► cloud phone instance
```

Process model — several subsystems start side effects at import time, so do not import the app twice across processes:

- `src/api/app.py` calls gevent `patch_all()` and serves `0.0.0.0:8848` with `WSGIServer`. It prepends both `src/` and the repository root to `sys.path`, which is why the codebase mixes `from api.xxx` and `from src.xxx` imports.
- `src/redis_client.py` exposes the single global Redis connection (`redis_cache`) used for rate limiting, room liveness keys, daily quotas, and strategy selection. Connection parameters come from environment variables.
- `src/api/services/task_manager.py` starts a watchdog thread on import that sends `fish_keepalive` to living threads and reaps dead ones.
- `src/api/services/my_scheduler.py` calls `start_scheduler()` on import, which boots APScheduler (pulled in indirectly by `room_service` and `enter_room_service`).
- A room is one row in `rooms` bound to a `phone_id`. Room creation claims a free device from the idle pool with an optimistic-lock update.

## Repository layout

```
.
├── requirements.txt               # direct dependencies, grouped by "standalone farming" vs "server"
├── schema.sql                     # PostgreSQL DDL (only needed for room mode; not for standalone farming)
├── .env.example                   # environment variable template — copy to .env and fill in (.env is not committed)
├── LICENSE                        # full PolyForm Noncommercial 1.0.0 text
├── asserts/                       # OpenCV template screenshots, imread'ed by asserts/__init__.py
│   ├── main_page/                 # main screen: settings, logout, resources, chat locators
│   ├── hit_fish_img/              # farming flow: search, deploy panel, troops, speed-up, loot, give up
│   ├── dark_main_page/            # night market main screen
│   └── donate_page/               # donation panel
└── src/
    ├── config.py                  # automation config: ADB address (COC_ADB_LINK), DPI, capture resolution, feature flags
    ├── hit_fish.py                # home village farming state machine
    ├── hit_fish_dark.py           # night market farming state machine
    ├── battle_util.py             # deploy order and coordinates per strategy
    ├── donate_soldiers.py         # donation flow
    ├── game_assist_uiautomator.py # adb/uiautomator2 wrapper: capture, humanised taps, matching, messaging
    ├── redis_client.py            # global redis_cache connection
    ├── utils.py                   # matching and similarity helpers
    ├── my_logger.py               # hourly-rotating logs under the user's home directory
    └── api/
        ├── app.py                 # Flask entrypoint, CORS, auth and rate limiting, global error handler
        ├── api_config.py          # wires JWT/database/cloud-phone credentials from env vars; scheduling constants, rate limiter, timeout helper
        ├── cloud_phone/chinac_open_api.py  # cloud phone OpenAPI client (HMAC-SHA256 signing)
        ├── controllers/           # user / room / phone / mock blueprints
        ├── services/              # room, room entry, user, farming, tasks, scheduling, email
        ├── dao/                   # SQLAlchemy models: users/rooms/cloud_phones/ads/room_logs/website_links
        ├── models/                # request/response entities and enums
        ├── exception/             # user/room/game custom exceptions
        └── resources/template/    # email HTML templates
```

## Tech stack

| Area | Components |
| --- | --- |
| Language | Python ≥ 3.10 (`X \| None` union annotations are used); developed on 3.12 |
| Web | Flask + flask-cors + gevent (waitress works too in production, install it yourself) |
| Storage | PostgreSQL (SQLAlchemy + psycopg2), Redis |
| Auth | PyJWT (HS256), bcrypt password hashes, image captcha |
| Scheduling | APScheduler |
| Imaging | opencv-python, numpy, pillow, Levenshtein (template similarity) |
| Device control | adbutils, uiautomator2 |
| External services | China Telecom Jilan cloud phone OpenAPI, QQ Mail SMTP |
| Logging | stdlib `logging` + a custom hourly-rotation FileHandler |

## Quick start

Two ways to use this project, with different requirements:

| | PostgreSQL / `schema.sql` | Redis | adb-enabled cloud phone |
| --- | --- | --- | --- |
| Standalone farming (run `src/hit_fish.py` directly) | not needed, no database required | required | **required** |
| Room mode (serve the web backend) | required | required | **required**, and every phone must be reachable via `adb connect` from the server |

Both modes need a cloud phone: every action the script takes is "adb screenshot → template match → adb tap". A physical Android device works too, but adb debugging has to be enabled on it.
Redis is used in standalone mode as well — each farming loop iteration reads signal keys such as `fish:logout:<room>:<user>` (log the account out, suppress auto-logout, report completion). The database is the only thing you can skip.

```bash
# 1. Environment
conda create -n coc_chat python=3.12 -y && conda activate coc_chat
#    or: python3.12 -m venv .venv && source .venv/bin/activate

# 2. Dependencies
pip install -r requirements.txt

# 3. Start Redis (needed by both modes)
redis-server --daemonize yes          # or: docker run -d -p 6379:6379 redis

# 4. Configure: copy the template and fill in your own values, then export them
cp .env.example .env
#    standalone farming needs at least COC_ADB_LINK + Redis; room mode also needs COC_JWT_SECRET_KEY and COC_DATABASE_URL
set -a && source .env && set +a

# 5. Room mode only: install PostgreSQL, then create the schema
createdb coc
psql -d coc -f schema.sql             # 6 tables; then insert one usable row into cloud_phones
python src/api/app.py
curl http://127.0.0.1:8848/ping       # expect: pong
```

To just farm on your own machine without creating any database:

```bash
export COC_ADB_LINK=<your cloud phone adb address>   # e.g. 192.168.0.10:5555
redis-server --daemonize yes
python src/hit_fish.py                # the module has a __main__ debug entry
```

## Configuration

Every secret and address is read from an environment variable; the repository ships no real credentials. The template is [`.env.example`](.env.example) in the repository root:

```bash
cp .env.example .env      # .env is git-ignored — never commit it
vim .env                  # put your own values in
set -a && source .env && set +a   # export them, then start the service
```

| Environment variable | Purpose | If left unset |
| --- | --- | --- |
| `COC_JWT_SECRET_KEY` | JWT HS256 signing key | room mode refuses to start |
| `COC_DATABASE_URL` | PostgreSQL connection string, e.g. `postgresql://user:pwd@host:5432/coc` | room mode refuses to start; standalone farming can leave it empty |
| `COC_REDIS_HOST` / `COC_REDIS_PORT` / `COC_REDIS_DB` | Redis host, port, database number (default `127.0.0.1:6379/0`) | neither mode runs |
| `COC_ADB_LINK` | Cloud phone adb address used by standalone mode (read by `src/config.py`) | falls back to the sample `192.168.0.10:5555` |
| `COC_MAIL_SENDER` / `COC_MAIL_AUTH_CODE` | Sender mailbox and auth code (for QQ Mail this is the 16-character auth code, not the login password) | verification codes and farming notifications cannot be sent |
| `COC_SMTP_HOST` / `COC_SMTP_PORT` | SMTP server (default `smtp.qq.com:465`) | — |
| `COC_CLOUD_PHONE_ACCESS_KEY_ID` / `COC_CLOUD_PHONE_ACCESS_KEY_SECRET` | Cloud phone vendor OpenAPI credentials | no direct-connect address, no stream URL |
| `COC_BACK_END_DOMAIN` | Target of the "enter the site" button in notification emails | the button links nowhere |

The remaining constants in `src/api/api_config.py` and `src/config.py` hold no secrets — edit them directly:

| Setting | Purpose |
| --- | --- |
| `ALGORITHM` / `EXPIRE_SEC` | JWT algorithm and lifetime (HS256 / 24 h by default) |
| `MEMBER_ONLY_USE_HOURS` | Daily cap (hours) a user may borrow from the room owner's quota; applies to both `member_only` and `share` rooms |
| `DEFAULT_ROOM_NAME` | Room name written back when a room is reclaimed |
| `INIT_SCRCPY_LINK` | Whether the keep-alive job pre-warms the cloud phone adb connection |
| `RateLimiter` / `run_with_timeout` | Redis ZSET sliding-window rate limiter; timeout wrapper |
| `ANDROID_DPI` | Target device DPI |
| `CAP_PROP_FRAME_WIDTH/HEIGHT` | Capture resolution; template screenshots must match it (1280×720 by default) |
| `ENABLE_DONATION` | Run the donation flow |
| `USE_ACTIVITY_SOLDERS` | Include event troops |
| `DIY_STRATEGY` | Custom army-composition switch |

## Database tables

The DDL ships as [`schema.sql`](schema.sql) in the repository root: `createdb coc && psql -d coc -f schema.sql`. Its columns match the models in `src/api/dao/*.py` one by one (there is no `create_all` call and no migration tool, so nothing is created automatically). Only room mode needs it — standalone farming does not touch the database.

| Table | Key columns | Notes |
| --- | --- | --- |
| `users` | `id`, `name`, `password_hash` (bcrypt), `email`, `display_uid`, `total_duration`, `allow_email_notice`, `is_deleted` | `total_duration` is the usable farming quota in seconds; **0 means unlimited**. Granted by an admin |
| `rooms` | `id`, `rname`, `type` (`temporary`/`closed`), `permission`, `phone_id`, `owner`, `current_user`, `white_list`, `end_time`, `fish_server` | `type='closed'` means taken offline and is filtered out by `get_all()`; empty `owner`/`current_user` means the room is unclaimed |
| `cloud_phones` | `id` (cloud phone instance ID, primary key), `region`, `resolution`, `address` (adb endpoint), `status` (`idle`/`active`) | Usable instances are inserted manually |
| `room_logs` | `log_id`, `room_id`, `event_time`, `event_type`, `operator_id`, `operator_name`, `remark` | Audit trail: entering, leaving, permission changes, whitelist requests |
| `ads` | `content`, `ad_type` | Banner and lobby announcement text for the frontend |
| `website_links` | `link_name`, `url`, `remark` | External links, e.g. the group QR code returned by `/room/url/wechat` |

## Running the service

Development / single machine:

```bash
python src/api/app.py          # gevent WSGIServer, 0.0.0.0:8848
```

Production (the setup actually in use — let pm2 or systemd supervise it):

```bash
python -c "from waitress import serve; from src.api.app import app; \
           serve(app, host='0.0.0.0', port=8848, threads=4)"
```

Do not enable buffering for SSE if you put nginx in front; responses already carry `X-Accel-Buffering: no`.

## Scheduled jobs

`src/api/services/my_scheduler.py` registers three APScheduler jobs:

| Job | Interval | Purpose |
| --- | --- | --- |
| `keep_alive` | 30 min | Reaps zombie connections, refreshes cloud phone adb links, writes the `device:status:<phone_id>` online marker |
| `active_room_deduct_time_job` | 2 min | Deducts time from in-use rooms in `DEDUCT_STEP_SEC = 120` second steps; a quota of 0 is treated as unlimited and skipped; an exhausted quota or a finished farming run triggers room cleanup and notifications |
| `clean_zombie_connections` | 1 h | Reclaims idle database connections with `pg_terminate_backend` |

`clean_room_job` (reclaims an expired room: reset to `temporary`, restore the default name, clear owner and current user, stop farming, reset the cloud phone link) and `check_public_detained_user` are called from those jobs.

Room liveness lives in the Redis key `room:alive:<room_id>` (written on entry, TTL 10 minutes), maintained by `/room/sse/<id>` and the keep-alive job.

## Rooms and permissions

Four values of `permission` (`src/api/models/my_enum.py`):

- `public` — **candidate room**. An unclaimed, idle room: whoever enters first owns it. Entry writes the entering user into `owner` and `current_user` and flips the room to `private`. The name is supplied by the user (1–10 characters; empty falls back to `我的{DEFAULT_ROOM_NAME}`). Setting a room back to `public` gives it up and returns it to the lobby.
- `member_only` — whitelist members only. `white_list` is a JSON array of uids maintained by the owner through `/room/white_list`; outsiders can send a request via `/room/white_list/apply`. Each member may borrow up to `MEMBER_ONLY_USE_HOURS` hours of the owner's quota per day, and that allowance is shared across all `member_only` rooms of the same owner.
- `share` — shared room. Anyone can use it, subject to the same daily quota, keyed on owner uid + user uid.
- `private` — owner only.

Related machinery: `ADMIN_USER_IDS` in `src/api/services/room_service.py` (a hardcoded admin uid list — **change it before deploying**), the `black_token` JWT blocklist in Redis, image captcha triggered by login IP throttling, and per-path plus per-user rate limits.

## API overview

Blueprint prefixes: `/user`, `/room`, `/phone`, `/mock`. The auth-free allowlist is the `jwt_token_filter` in `src/api/app.py`.

**user**: `/login`, `/register`, `/name`, `/captcha`, `/captcha/verify`, `/info`, `/info/name/<display_uid>`, `/rooms`, `/password`, `/change-name`, `/logout`, `/email`, `/email-verify`, `/allow-notice`

**room**: `/list`, `/init/`, `/create`, `/leave/<id>`, `/sse/<id>`, `/message`, `/apply-operate`, `/hit_fish` (POST start / PUT stop), `/hit_fish_dark` (POST/PUT), `/is-fish/<id>`, `/task/status/<id>`, `/formate`, `/white_list` (POST/GET), `/white_list/apply`, `/permission`, `/rname`, `/refresh/<id>`, `/url/<name>`, `/ads/<type>`, `/solders`

**phone**: `/list`　**mock**: `/rooms`, `/phone` (hard-coded demo payloads)

Every response is `{code, message, data}` with `code=200` on success and `400/401/429/500` for business errors.

## The farming loop

`src/hit_fish.py` runs a bounded loop (70 rounds max); each round calls `_execute_flow`:

1. Confirm we are on the main screen (template match against `asserts/main_page`), opening settings if needed to clear a stuck logout check.
2. Switch to the league or wars tab, `search_fish` for a target, confirm `attack_on_panel`.
3. End the prep state and zoom the map to locate the base.
4. Attack automatically, or deploy troops in the order defined by the selected strategy (`battle_util.py` decides order and drop points, reinforcements included).
5. Battle monitoring: 186 s cap; tap the `speed` button whenever it appears; read the destruction ROI on the main screen (`frame[555:587, 1191:1265]`) to end early once the base is three-starred.
6. Collect loot: dismiss `hammer` / `jian` / `continue` dialogs one by one and take the chests.
7. Return to the main screen, check whether resources are full (by pixel colour), and log out to rotate accounts when needed.

The night market variant lives in `src/hit_fish_dark.py` as a simplified branch of the same skeleton; donation lives in `src/donate_soldiers.py`. Every tap carries a random offset and humanised delay (`src/game_assist_uiautomator.py`), and all template images are loaded into OpenCV Mats by `asserts/__init__.py` — a missing file only logs `logger.error` and never blocks startup, so you can replace the screenshots with your own.

## Frontend

This repository **does not include a frontend**. The production UI is a separate uni-app H5 project (room lobby, room page that plays the cloud phone stream through the vendor JS SDK inside an iframe, radial menu for mode / strategy / email / world switches). It only consumes the JSON endpoints and SSE listed above. To get the full experience you will need to build your own frontend or wire these endpoints into an existing page.

## Before you publish

The repository ships no plaintext secrets and none of the author's real addresses: credentials come from environment variables, `.env` is git-ignored, the debug entry points use `COC_ADB_LINK`, and `/mock` returns placeholder data only. These items are still yours to handle before going public:

1. **Rotate every credential you have ever committed** — the JWT `SECRET_KEY`, database password, cloud phone `access_key_id/access_key_secret`, mail auth code, and any historical file such as certificates or private keys. A clean repository from the current working tree means no `git filter-repo` is needed, but **anything that appeared in even one commit must be treated as leaked and replaced**.
2. **Admin list** — `ADMIN_USER_IDS = (4, 6)` in `src/api/services/room_service.py` is hard-coded; change it to your own uids before deploying.
3. **Use your own addresses** — `COC_ADB_LINK` and `COC_BACK_END_DOMAIN` in `.env`, plus the sample cloud phone instance id and adb address in the commented inserts at the bottom of `schema.sql` (values like `192.168.0.10:5555` are format examples only).
4. **Keep `.env` out of git** — `.gitignore` already covers it, but confirm once before publishing: `git ls-files | grep -E '^\.env$'`.

## License

The source in this repository is licensed under the **PolyForm Noncommercial License 1.0.0** (full text in [`LICENSE`](LICENSE), SPDX identifier `PolyForm-Noncommercial-1.0.0`).

- **Allowed**: personal use, learning, research, experimentation and hobby projects; plus use by non-profits, schools, public research, public safety/health, environmental and government bodies, regardless of funding or obligations.
- **Requires a separate license**: any commercial purpose, including paid farming services or renting rooms out, selling this system as a service, or commercial internal deployments.
- **When redistributing**: pass these terms (or their URL) to every recipient and keep the `Required Notice:` line the author placed in the software.
- This is **not an OSI-approved open source license**; it is source-available. Hosting platforms (GitHub/Gitee) may show the license field as `Other`, which is expected.

Game screenshots and template images under `asserts/` are Clash of Clans material, copyright Supercell, and are **outside the scope of this license** — they exist purely as image-matching references. `asserts/__init__.py` loads them by file name, so you can delete the PNGs and rebuild the set from your own screenshots.

Whatever license applies, users accept on their own: the risk of account bans and financial loss from game scripting; the risk of misuse of Clash of Clans assets and trademarks; and the cost and compliance responsibility for the cloud phone, SMS, and email services they connect. The author provides no warranty and accepts no liability for the consequences of use.
