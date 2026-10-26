-- ============================================================================
-- 打鱼助手 数据库建表脚本 (PostgreSQL 12+)
--
-- 只有「房间模式」（对外提供服务、多用户管理）才需要数据库。
-- 单机自己跑 src/hit_fish.py 直接连你自己的云手机，不需要建库。
--
--   createdb coc
--   psql -d coc -f schema.sql
--
-- 表结构与 src/api/dao/*.py 里的 SQLAlchemy 模型一一对应。
-- 应用不会自动建表（代码里没有 create_all / 迁移工具），所以本文件就是唯一入口。
-- ============================================================================

-- ---------------------------------------------------------------------------
-- users：用户
-- 注意 total_duration 的语义是「剩余可用秒数」，0 表示不限时长（不会被扣减）。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                 BIGSERIAL    PRIMARY KEY,
    name               VARCHAR(50)  NOT NULL UNIQUE,
    password_hash      VARCHAR(255) NOT NULL,
    portrait           VARCHAR(500),
    email              VARCHAR(100),
    allow_email_notice BOOLEAN      NOT NULL DEFAULT FALSE,
    display_uid        VARCHAR(20)  NOT NULL UNIQUE,
    total_duration     BIGINT       NOT NULL DEFAULT 0,
    create_time        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_time    TIMESTAMP,
    is_deleted         BOOLEAN      NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE  users                  IS '用户表';
COMMENT ON COLUMN users.name             IS '登录用户名';
COMMENT ON COLUMN users.password_hash    IS 'bcrypt 密码哈希';
COMMENT ON COLUMN users.display_uid      IS '对外展示的 6 位 ID';
COMMENT ON COLUMN users.total_duration   IS '剩余可用秒数，0 = 不限时长';
COMMENT ON COLUMN users.is_deleted       IS '软删除标记';

CREATE INDEX IF NOT EXISTS idx_user_name       ON users USING btree (name);
CREATE INDEX IF NOT EXISTS idx_user_create_time ON users USING btree (create_time);
CREATE INDEX IF NOT EXISTS idx_user_is_deleted  ON users USING btree (is_deleted);

-- ---------------------------------------------------------------------------
-- cloud_phones：云手机池
-- address 是 adb 可调用的「IP:端口」，房间通过 phone_id 绑定到某台云手机。
-- status：active 可用 / idle 空闲 / 其余自定义。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cloud_phones (
    id         VARCHAR(50) PRIMARY KEY,
    region     VARCHAR(50) NOT NULL,
    resolution VARCHAR(20) NOT NULL,
    address    VARCHAR(50) NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  cloud_phones         IS '云手机表';
COMMENT ON COLUMN cloud_phones.address IS 'adb 地址，形如 192.168.0.10:5555';
COMMENT ON COLUMN cloud_phones.status  IS 'active / idle';

-- 示例：一台开了 adb 调试、能被服务端 `adb connect` 到的云手机
-- INSERT INTO cloud_phones (id, region, resolution, address) VALUES
--     ('cp-demo-0001', 'cn-local', '720P', '192.168.0.10:5555');

-- ---------------------------------------------------------------------------
-- rooms：房间
-- type：temporary 可进入 / closed 已下架
-- permission：private 独享 / member_only 仅成员 / public 候选（无人认领）/ share 共享
-- end_time：房间到期时间；NULL 或远期表示不过期。
-- 一个房间同一时刻只有 owner 在打鱼，current_user 记录当前使用者。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rooms (
    id           BIGSERIAL    PRIMARY KEY,
    rname        VARCHAR(100) NOT NULL,
    type         VARCHAR(20)  NOT NULL DEFAULT 'temporary',
    permission   VARCHAR(30)  NOT NULL DEFAULT 'private',
    phone_id     VARCHAR(50)  NOT NULL,
    owner        INTEGER,
    "current_user" INTEGER,
    white_list   TEXT,
    end_time     TIMESTAMP,
    create_time  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fish_server  VARCHAR(100) NOT NULL DEFAULT 'cn',
    FOREIGN KEY (phone_id) REFERENCES cloud_phones (id)
);

COMMENT ON TABLE  rooms            IS '打鱼房间表';
COMMENT ON COLUMN rooms.type       IS 'temporary 可进入 / closed 已下架';
COMMENT ON COLUMN rooms.permission IS 'private 独享 / member_only 仅成员 / public 候选 / share 共享';
COMMENT ON COLUMN rooms.phone_id   IS '绑定的云手机 ID';
COMMENT ON COLUMN rooms.owner      IS '房主的 users.id，NULL 表示无人认领';
COMMENT ON COLUMN rooms.white_list IS '白名单用户 ID 的 JSON 数组文本，如 ["10"]';
COMMENT ON COLUMN rooms.fish_server IS '游戏区服标识，默认 cn';

CREATE INDEX IF NOT EXISTS idx_rooms_phone_id ON rooms USING btree (phone_id);
CREATE INDEX IF NOT EXISTS idx_rooms_owner    ON rooms USING btree (owner);

-- ---------------------------------------------------------------------------
-- room_logs：房间操作日志
-- event_type 例如 create_room / join_room / leave_room / start_fish / stop_fish
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS room_logs (
    log_id        BIGSERIAL   PRIMARY KEY,
    room_id       BIGINT      NOT NULL REFERENCES rooms (id) ON DELETE CASCADE,
    event_time    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type    VARCHAR(30) NOT NULL,
    operator_id   INTEGER,
    operator_name VARCHAR(100),
    remark        TEXT
);

COMMENT ON TABLE room_logs IS '房间操作日志表';

CREATE INDEX IF NOT EXISTS idx_room_logs_room_id ON room_logs USING btree (room_id, event_time);

-- ---------------------------------------------------------------------------
-- ads：首页滚动公告
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ads (
    id         BIGSERIAL   PRIMARY KEY,
    content    TEXT        NOT NULL,
    ad_type    VARCHAR(20) NOT NULL DEFAULT 'text',
    created_at TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  ads         IS '公告横幅表';
COMMENT ON COLUMN ads.ad_type IS '首页广告 / 文字 / 图片 等自定义分类';

-- INSERT INTO ads (content, ad_type) VALUES
--     ('请勿在共享房间里安装第三方软件，违规将被踢出', '首页广告');

-- ---------------------------------------------------------------------------
-- website_links：可配置的外部链接
-- 前端通过 GET /room/url/<link_name> 取值，例如教程里的反馈入口。
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS website_links (
    id         BIGSERIAL   PRIMARY KEY,
    link_name  VARCHAR(128) NOT NULL UNIQUE,
    url        TEXT        NOT NULL,
    remark     TEXT,
    create_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE website_links IS '外部链接配置表';

-- INSERT INTO website_links (link_name, url, remark) VALUES
--     ('bug_report', 'https://example.com/feedback', '问题反馈入口');
