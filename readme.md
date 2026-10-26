# 部落冲突「打鱼」挂机 · 云手机房间系统

[简体中文](readme.md) | [English](README.en.md)

Clash of Clans 资源自动化（俗称「打鱼」）脚本 + 基于云手机的多租户房间后端。

用户不需要有自己的安卓设备：后端把一台云手机实例绑定成一个「房间」，用户在网页里直接看到云手机画面并下发操作；服务端的打鱼线程通过 adb + 图像模板匹配，自动完成搜鱼、配兵、进攻、快进、领奖的完整循环。

不管用哪种方式跑起来，都必须有一台**开了 adb 调试的云手机（或安卓设备）**：脚本的每一步都是「adb 截图 → 模板识别 → adb 点击」。数据库只有对外提供房间服务时才用得到，单机打鱼不建库也能跑（详见[快速开始](#快速开始)）。

> **免责声明**
> 本项目仅用于学习自动化测试与图像识别技术。游戏脚本挂机违反 Supercell 用户协议，可能导致**账号被封**，由此产生的一切后果由使用者自行承担。
> 项目不包含任何内存读写、协议破解或客户端修改，所有操作都是「截图 → 识别 → 模拟点击」。
> 项目涉及的《部落冲突》素材、商标归 Supercell 所有；`asserts/` 下的模板截图仅用于识别定位，不在本仓库许可证的授权范围内（见[许可](#许可)）。

---

## 目录

- [它做什么](#它做什么)
- [架构](#架构)
- [目录结构](#目录结构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [配置项](#配置项)
- [数据表](#数据表)
- [启动服务](#启动服务)
- [定时任务](#定时任务)
- [房间与权限模型](#房间与权限模型)
- [API 一览](#api-一览)
- [打鱼流程](#打鱼流程)
- [前端](#前端)
- [发布前自查](#发布前自查)
- [许可](#许可)

---

## 它做什么

- **房间大厅**：列出所有房间、当前使用者、忙碌/空闲状态、剩余可用时长。
- **进房接管**：非房主进入房间需要走权限校验（详见[房间与权限模型](#房间与权限模型)），可抢占操作权。
- **自动打鱼**：一键开启/停止，国服与国际服（`fish_server`）、匹配与排位两种模式、主世界与夜市界两套流程。
- **流派配兵**：可指定兵种流派（铅笔天使 / 龙流 / 武神流 / 胖子弓箭手流等），服务端按流派顺序放下援兵，见 `src/battle_util.py`。
- **实时状态推送**：房间内的打鱼日志、剩余时长、保活状态通过 SSE 推给前端。
- **时长结算**：按房间实际占用时长扣减使用者额度，额度耗尽自动停鱼并回收房间。
- **邮件通知**：打鱼失败、验证码、系统通知三类 HTML 模板邮件。
- **捐兵**：`src/donate_soldiers.py` 独立支持部落捐兵流程。

## 架构

```
浏览器 H5（独立仓库）
   │  REST + SSE
   ▼
Flask 应用  :8848  ──► PostgreSQL（用户/房间/云手机/公告/日志）
   │                ──► Redis（缓存、限流计数、token 黑名单、流派与任务状态）
   │                ──► 中国电信极览云手机 OpenAPI（取播放直连 URL、下发指令）
   │
   └─► 每个房间一个打鱼线程（adbutils + uiautomator2 + OpenCV 模板匹配）──► 云手机实例
```

关键进程模型（都在导入期副作用启动，注意别在多个进程里重复导入）：

- `src/api/app.py` 用 gevent `patch_all()` + `WSGIServer` 监听 `0.0.0.0:8848`，并在文件头自己把 `src/` 与仓库根塞进 `sys.path`，所以模块内部同时存在 `from api.xxx` 和 `from src.xxx` 两种导入路径。
- `src/redis_client.py` 是全局唯一的 Redis 连接（`redis_cache`），限流、房间存活标记、每日额度、流派选择都落在它上面；连接参数走环境变量。
- `src/api/services/task_manager.py` 被导入时即启动线程巡检定时器，负责给存活线程发 `fish_keepalive`、清理死线程。
- `src/api/services/my_scheduler.py` 被导入时即 `start_scheduler()` 启动 APScheduler（由 `room_service`、`enter_room_service` 间接引入）。
- 房间与云手机是一行 `rooms` 记录绑定一个 `phone_id`，创建房间时用乐观锁从空闲机池里抢一台。

## 目录结构

```
.
├── requirements.txt               # 直接依赖清单，按分组注释区分「单机打鱼」与「服务端」
├── schema.sql                     # PostgreSQL 建表脚本（房间模式用得到，单机打鱼不需要）
├── .env.example                   # 环境变量模板，复制成 .env 填自己的值（.env 不入库）
├── LICENSE                        # PolyForm Noncommercial 1.0.0 全文
├── asserts/                       # OpenCV 模板截图，由 asserts/__init__.py 统一 imread
│   ├── main_page/                 # 主界面：设置、下线、资源、聊天室等定位图
│   ├── hit_fish_img/              # 打鱼流程：搜鱼、出兵面板、各兵种、快进、领奖、放弃战斗
│   ├── dark_main_page/            # 夜市界主界面
│   └── donate_page/               # 捐兵面板
└── src/
    ├── config.py                  # 自动化侧配置：ADB 地址（COC_ADB_LINK）、DPI、截屏分辨率、功能开关
    ├── hit_fish.py                # 主世界打鱼状态机
    ├── hit_fish_dark.py           # 夜市界打鱼状态机
    ├── battle_util.py             # 各流派放兵顺序与坐标
    ├── donate_soldiers.py         # 捐兵流程
    ├── game_assist_uiautomator.py # adb/uiautomator2 封装：截图、拟人点击、模板匹配、发消息
    ├── redis_client.py            # 全局 Redis 连接 redis_cache
    ├── utils.py                   # 匹配与相似度工具
    ├── my_logger.py               # 每小时滚动日志，落在用户目录下 logs/
    └── api/
        ├── app.py                 # Flask 入口、CORS、鉴权与限流、全局异常
        ├── api_config.py          # 读环境变量装配 JWT/数据库/云手机凭证，另有调度常量、限流器、超时工具
        ├── cloud_phone/chinac_open_api.py  # 极览云手机 OpenAPI 客户端（HMAC-SHA256 签名）
        ├── controllers/           # user / room / phone / mock 四个蓝图
        ├── services/              # 房间、进房、用户、打鱼、任务、调度、邮件
        ├── dao/                   # SQLAlchemy 模型：users/rooms/cloud_phones/ads/room_logs/website_links
        ├── models/                # 请求响应实体与枚举
        ├── exception/             # user/room/game 自定义异常
        └── resources/template/    # 邮件 HTML 模板
```

## 技术栈

| 分类 | 组件 |
| --- | --- |
| 语言 | Python ≥ 3.10（代码使用了 `X \| None` 联合类型标注），开发环境为 3.12 |
| Web | Flask + flask-cors + gevent（生产可选 waitress，需自行 `pip install waitress`） |
| 存储 | PostgreSQL（SQLAlchemy + psycopg2）、Redis |
| 鉴权 | PyJWT（HS256）、bcrypt 口令哈希、图形验证码 |
| 调度 | APScheduler |
| 图像 | opencv-python、numpy、pillow、Levenshtein（模板相似度） |
| 设备控制 | adbutils、uiautomator2 |
| 外部服务 | 中国电信极览云手机 OpenAPI、QQ 邮箱 SMTP |
| 日志 | 标准库 logging + 自研每小时滚动 FileHandler |

## 快速开始

两种用法，依赖不同：

| | 需要 PostgreSQL / `schema.sql` | 需要 Redis | 需要开了 adb 的云手机 |
| --- | --- | --- | --- |
| 单机打鱼（直接跑 `src/hit_fish.py`） | 不需要，不建库也能跑 | 需要 | **需要** |
| 房间模式（起 Web 后端对外服务） | 需要 | 需要 | **需要**，每台云手机都要能被服务端 `adb connect` |

两种方式都离不开云手机：脚本的一切操作都是「adb 截图 → 模板识别 → adb 点击」，没有实体安卓机也行，但这台机器必须开着 adb 调试端口。
Redis 在单机模式下同样要用——打鱼循环每轮都会读 `fish:logout:<room>:<user>` 等信号键（下线、停止自动下线、结束通知），只是完全不碰数据库。

```bash
# 1. 环境
conda create -n coc_chat python=3.12 -y && conda activate coc_chat
#    或 python3.12 -m venv .venv && source .venv/bin/activate

# 2. 依赖
pip install -r requirements.txt

# 3. 起 Redis（两种用法都要）
redis-server --daemonize yes          # 或 docker run -d -p 6379:6379 redis

# 4. 配置：复制模板填好自己的值，再导出到当前 shell
cp .env.example .env
#    单机打鱼至少要 COC_ADB_LINK + Redis；房间模式还要 COC_JWT_SECRET_KEY、COC_DATABASE_URL
set -a && source .env && set +a

# 5. 启动服务（房间模式）：另装 PostgreSQL，然后
createdb coc
psql -d coc -f schema.sql             # 建 6 张表；再往 cloud_phones 插入一台实例
python src/api/app.py
curl http://127.0.0.1:8848/ping       # 期望 pong
```

只想在自己的机器上打鱼、不建库时：

```bash
export COC_ADB_LINK=<你的云手机 adb 地址>   # 例如 192.168.0.10:5555
redis-server --daemonize yes
python src/hit_fish.py                # 文件自带 __main__ 调试入口
```

## 配置项

所有密钥和地址都从环境变量读取，仓库内不含任何真实凭证。模板是根目录的 [`.env.example`](.env.example)：

```bash
cp .env.example .env      # .env 已被 .gitignore 忽略，不要提交
vim .env                  # 填你自己的值
set -a && source .env && set +a   # 导出到当前 shell，再启动服务
```

| 环境变量 | 作用 | 不配置会怎样 |
| --- | --- | --- |
| `COC_JWT_SECRET_KEY` | JWT HS256 签名密钥 | 房间模式启动时直接退出 |
| `COC_DATABASE_URL` | PostgreSQL 连接串，形如 `postgresql://user:pwd@host:5432/coc` | 房间模式启动时直接退出；单机打鱼可留空 |
| `COC_REDIS_HOST` / `COC_REDIS_PORT` / `COC_REDIS_DB` | Redis 主机、端口、库号（默认 `127.0.0.1:6379/0`） | 两种用法都跑不起来 |
| `COC_ADB_LINK` | 单机打鱼连接的云手机 adb 地址（`src/config.py` 读取） | 退回默认示例值 `192.168.0.10:5555` |
| `COC_MAIL_SENDER` / `COC_MAIL_AUTH_CODE` | 发件邮箱与授权码（QQ 邮箱是 16 位授权码，不是登录密码） | 验证码与打鱼通知邮件发不出去 |
| `COC_SMTP_HOST` / `COC_SMTP_PORT` | SMTP 服务器（默认 `smtp.qq.com:465`） | — |
| `COC_CLOUD_PHONE_ACCESS_KEY_ID` / `COC_CLOUD_PHONE_ACCESS_KEY_SECRET` | 云手机厂商 OpenAPI 凭证 | 无法取到实例直连地址与画面 URL |
| `COC_BACK_END_DOMAIN` | 邮件里「点击进入打鱼网站」按钮的跳转地址 | 按钮链接为空 |

`src/api/api_config.py` 和 `src/config.py` 里剩下的常量都不涉及密钥，直接改代码即可：

| 变量 | 作用 |
| --- | --- |
| `ALGORITHM` / `EXPIRE_SEC` | JWT 算法与有效期（默认 HS256 / 24h） |
| `MEMBER_ONLY_USE_HOURS` | 成员每天可借用房主时长的上限（小时），`member_only` 与 `share` 房间都按它配额 |
| `DEFAULT_ROOM_NAME` | 清房后回写的默认房间名 |
| `INIT_SCRCPY_LINK` | 保活任务是否预热云手机 adb 连接 |
| `RateLimiter` / `run_with_timeout` | 基于 Redis ZSET 的滑动窗口限流、超时执行工具 |
| `ANDROID_DPI` | 目标设备 DPI |
| `CAP_PROP_FRAME_WIDTH/HEIGHT` | 截屏分辨率，模板截图必须与之一致（默认 1280×720） |
| `ENABLE_DONATION` | 是否走捐兵流程 |
| `USE_ACTIVITY_SOLDERS` | 是否使用活动兵种 |
| `DIY_STRATEGY` | 自定义配兵开关 |

## 数据表

建表脚本见仓库根的 [`schema.sql`](schema.sql)，`createdb coc && psql -d coc -f schema.sql` 即可，列定义与 `src/api/dao/*.py` 里的模型一一对应（代码里没有 `create_all`，也不会自动迁移）。只有房间模式需要它，单机打鱼不用建库。

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `users` | `id`、`name`、`password_hash`(bcrypt)、`email`、`display_uid`、`total_duration`、`allow_email_notice`、`is_deleted` | `total_duration` 是该用户可用的打鱼时长（秒），**0 表示不限量**；由管理员按需发放 |
| `rooms` | `id`、`rname`、`type`(`temporary`/`closed`)、`permission`、`phone_id`、`owner`、`current_user`、`white_list`、`end_time`、`fish_server` | `type='closed'` 即下架，`get_all()` 会过滤掉；`owner`/`current_user` 为空表示无人认领 |
| `cloud_phones` | `id`(云手机实例 ID，主键)、`region`、`resolution`、`address`(adb 地址)、`status`(`idle`/`active`) | 需要手工插入可用实例 |
| `room_logs` | `log_id`、`room_id`、`event_time`、`event_type`、`operator_id`、`operator_name`、`remark` | 进房、退房、改权限、白名单申请等审计流水 |
| `ads` | `content`、`ad_type` | 前端横幅与首页公告文案来源 |
| `website_links` | `link_name`、`url`、`remark` | 站点外链配置，如 `/room/url/wechat` 返回的群二维码 |

## 启动服务

开发/单机：

```bash
python src/api/app.py          # gevent WSGIServer, 0.0.0.0:8848
```

生产（实测在用的写法，进程守护交给 pm2 或 systemd）：

```bash
python -c "from waitress import serve; from src.api.app import app; \
           serve(app, host='0.0.0.0', port=8848, threads=4)"
```

SSE 走 nginx 反代时不要开缓冲，响应里已带 `X-Accel-Buffering: no`。

## 定时任务

`src/api/services/my_scheduler.py`，APScheduler 三个任务：

| 任务 | 周期 | 作用 |
| --- | --- | --- |
| `keep_alive` | 30 分钟 | 清理僵尸连接、刷新云手机 adb 链接、写 `device:status:<phone_id>` 在线标记 |
| `active_room_deduct_time_job` | 2 分钟 | 给使用中的房间按 `DEDUCT_STEP_SEC = 120` 秒一档扣时长；额度为 0 的用户视为不限量、不扣减；额度耗尽或打鱼已收尾时触发关房与通知 |
| `clean_zombie_connections` | 1 小时 | 直接 `pg_terminate_backend` 回收数据库空闲连接 |

另有 `clean_room_job`（到期回收房间：重置为 `temporary`、回写默认房名、清空房主与使用者、停打鱼、重置云手机链接）和 `check_public_detained_user`。

房间存活靠 Redis 键 `room:alive:<room_id>`（进房时写入，TTL 10 分钟）；`/room/sse/<id>` 与保活任务共同维持它。

## 房间与权限模型

`permission` 四种（`src/api/models/my_enum.py`）：

- `public` —— **候选房间**。还没有主人的空闲房间，谁先进入谁认领：进入后 `owner`、`current_user` 写为进入者，权限自动变成 `private`，房名由用户填写（1～10 个字符，留空则用 `我的{DEFAULT_ROOM_NAME}`）。房主把房间改回 `public` 就等于放弃它，房间重新回到大厅。
- `member_only` —— 仅白名单成员。`white_list` 存 JSON 数组的 uid 列表，由房主通过 `/room/white_list` 维护，未入名单的人可以用 `/room/white_list/apply` 发起申请；每人每天可借用房主时长 `MEMBER_ONLY_USE_HOURS` 小时，同一房主的多个仅成员房间之间共用这份配额。
- `share` —— 共享房间。任何人都能用，同样受每日配额限制，配额挂在房主 uid + 使用者 uid 上。
- `private` —— 仅房主。

配套逻辑：`ADMIN_USER_IDS`（`src/api/services/room_service.py`，写死的管理员 uid 列表，**部署前必须改成你自己的**）、Redis 里的 `black_token` JWT 黑名单、登录 IP 频控触发图形验证码、路径级与用户级限流。

## API 一览

前缀由蓝图注册决定：`/user`、`/room`、`/phone`、`/mock`。免鉴权白名单见 `src/api/app.py` 的 `jwt_token_filter`。

**user**：`/login`、`/register`、`/name`、`/captcha`、`/captcha/verify`、`/info`、`/info/name/<display_uid>`、`/rooms`、`/password`、`/change-name`、`/logout`、`/email`、`/email-verify`、`/allow-notice`

**room**：`/list`、`/init/`、`/create`、`/leave/<id>`、`/sse/<id>`、`/message`、`/apply-operate`、`/hit_fish`(POST 开/PUT 停)、`/hit_fish_dark`(POST/PUT)、`/is-fish/<id>`、`/task/status/<id>`、`/formate`、`/white_list`(POST/GET)、`/white_list/apply`、`/permission`、`/rname`、`/refresh/<id>`、`/url/<name>`、`/ads/<type>`、`/solders`

**phone**：`/list`　**mock**：`/rooms`、`/phone`（写死的演示数据）

统一响应结构 `{code, message, data}`，成功 `code=200`，业务失败 `code=400/401/429/500`。

## 打鱼流程

`src/hit_fish.py` 主循环（单轮上限 70 次），每轮 `_execute_flow`：

1. 校验当前在主界面（模板匹配 `asserts/main_page`），必要时打开设置退出登录态检查。
2. 切到匹配或排位区域，`search_fish` 搜鱼，确认 `attack_on_panel`。
3. 结束备战态，缩放地图定位目标。
4. 自动战斗，或按选定流派依次放兵（`battle_util.py` 决定顺序与落点，支持援兵）。
5. 战斗监控：186 秒超时上限；识别到 `speed` 按钮就点快进；用主界面摧毁率 ROI（截屏 `frame[555:587, 1191:1265]`）判断是否已推平、可提前结束。
6. 结算领奖：`hammer`/`jian`/`continue` 等模板逐个点掉，拿宝箱与奖励。
7. 回主界面，检查资源是否满（按像素颜色判定），必要时换号下线（`logout`）。

夜市界在 `src/hit_fish_dark.py`，是同一套骨架的简化分支；捐兵在 `src/donate_soldiers.py`。所有点击都带随机偏移与拟人延时（`src/game_assist_uiautomator.py`），模板资源统一由 `asserts/__init__.py` 读成 OpenCV Mat——缺图只记一条 `logger.error`，不会中断启动，你可以换成自己的截图。

## 前端

本仓库**不含前端**。线上前端是一个独立的 uni-app H5 工程（房间大厅、房间页用云手机厂商 JS SDK 在 iframe 里播放画面、环形菜单切换模式/流派/邮件通知/世界），只消费上面「API 一览」里的 JSON 接口与 SSE。想跑通完整体验需要自行实现前端，或者按接口文档对接你自己的页面。

## 发布前自查

仓库内已经不含明文密钥与作者自己的真实地址：凭证全部走环境变量，`.env` 被 gitignore 忽略，调试入口用 `COC_ADB_LINK`，`/mock` 只返回占位假数据。剩下这几项要你自己过一遍：

1. **轮换所有接触过的密钥**：JWT `SECRET_KEY`、数据库口令、云手机 `access_key_id/access_key_secret`、邮箱授权码，以及任何曾提交到旧仓库的历史文件（证书、私钥等）。新仓库是干净起步，不需要 `git filter-repo`，但**只要出现在过一次提交里，就按已泄露处理，一律换新的**。
2. **管理员名单**：`src/api/services/room_service.py` 的 `ADMIN_USER_IDS = (4, 6)` 是写死的 uid，部署前改成你自己的。
3. **换成自己的地址**：`.env` 里的 `COC_ADB_LINK`、`COC_BACK_END_DOMAIN`，以及 `schema.sql` 底部示例插入语句里的云手机实例 ID 与 adb 地址（示例值形如 `192.168.0.10:5555`，只是格式参考）。
4. **别把 .env 提交上去**：`.gitignore` 已经忽略，但公开前 `git ls-files | grep -E '^\.env$'` 再确认一次。

## 许可

本仓库源码采用 **PolyForm Noncommercial License 1.0.0**（全文见 [`LICENSE`](LICENSE)，SPDX 标识 `PolyForm-Noncommercial-1.0.0`）。

- **可以**：个人学习、研究、试验与自娱自乐地使用和改动；公益组织、学校、公共科研、公共安全/健康、环保与政府机构使用（不论资金来源与义务关系）。
- **需要事先取得单独许可**：任何商业目的，包括但不限于收费代打/包月出租房间、把这套系统作为服务对外售卖、企业内部的商业性部署。
- **分发时**：必须把这份条款（或它的 URL）一并给到每一个接收者，并保留作者在软件中给出的 `Required Notice:` 明文行。
- 这份许可证**不是 OSI 认证的开源协议**，它属于「源码可见」（source available）。托管平台（GitHub/Gitee）的许可证栏可能显示为 `Other`，这是正常的。

`asserts/` 下的游戏截图与模板图属于《部落冲突》素材，版权归 Supercell，**不在本许可证的授权范围内**，它们只作为图像识别定位的示例存在。`asserts/__init__.py` 按文件名读取图片，你可以删掉这些 png 后用自己的游戏截图重做。

无论采用何种许可证，使用者需自行承担：因游戏脚本导致的账号封禁与财产损失风险；对《部落冲突》素材与商标的不当使用风险；以及自行接入的云手机、短信、邮件等第三方服务的费用与合规责任。作者不提供任何担保，也不对使用后果负责。
