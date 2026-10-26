import time
from datetime import datetime
from typing import Callable
import threading

from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from api.api_config import session, MEMBER_ONLY_USE_HOURS, DEFAULT_ROOM_NAME, INIT_SCRCPY_LINK
from api.cloud_phone.chinac_open_api import get_phone_url
from api.dao.cloud_phone_dao import CloudPhonesDao
from api.dao.room_logs_dao import RoomLogDao
from api.dao.rooms_dao import RoomsDao
from api.dao.users_dao import UsersDao
from api.models.my_enum import RoomPermission
from api.services.room_fish_service import RoomActionService
from api.services.task_manager import task_manager
from src.redis_client import redis_cache
from src.my_logger import logger

# ============ 核心调度器（APScheduler 版本） ============

# 创建后台调度器
scheduler = BackgroundScheduler()
scheduler._daemon = True

# 存储任务ID，用于管理
scheduler_job_ids = {}

# ============ 常量定义 ============
DEDUCT_STEP_SEC = 2 * 60  # 单次扣减2分钟
KEEP_ALIVE_INTERVAL_SEC = 30 * 60
KEY_EXPIRE = 8 * 3600  # 24小时过期重置
ZOMBIE_THRESHOLD_MINUTES = 10  # 僵尸连接阈值


# ============ 核心调度方法 ============

def add_delay_job(delay_sec: float, job: Callable, args: tuple = None, room_id: int = None, job_id: str = None):
    """
    添加延时任务（APScheduler 版本）

    :param delay_sec: 延迟秒数
    :param job: 要执行的任务函数
    :param args: 任务参数
    :param room_id: 房间ID（用于标识）
    :param job_id: 任务ID（可选）
    """
    try:
        # 生成任务ID
        if job_id is None:
            job_id = f"{job.__name__}_{room_id}_{int(time.time())}" if room_id else f"{job.__name__}_{int(time.time())}"

        # 添加一次性任务，延迟执行
        scheduler.add_job(
            job,
            'date',
            run_date=datetime.now() + time.timedelta(seconds=delay_sec),
            args=args or (),
            id=job_id,
            replace_existing=True
        )

        if room_id and room_id > 0:
            scheduler_job_ids[room_id] = job_id
            logger.debug(f"[调度器] 房间 {room_id} 添加延时任务: {delay_sec}秒后执行 {job.__name__}")
        else:
            logger.debug(f"[调度器] 添加延时任务: {delay_sec}秒后执行 {job.__name__}")

    except Exception as e:
        logger.error(f"[调度器] 添加延时任务失败 (job={job.__name__}): {e}")


def remove_job_by_room_id(room_id: int):
    """根据房间ID移除对应的调度任务"""
    if room_id in scheduler_job_ids:
        job_id = scheduler_job_ids[room_id]
        try:
            scheduler.remove_job(job_id)
            del scheduler_job_ids[room_id]
            logger.info(f"[调度器] 已移除房间 {room_id} 的任务")
        except Exception as e:
            logger.error(f"[调度器] 移除房间 {room_id} 任务失败: {e}")


# ============ 任务执行监听 ============

def job_listener(event):
    """任务执行监听器"""
    if event.exception:
        logger.error(f"[调度器] 任务 {event.job_id} 执行失败: {event.exception}")
    else:
        logger.debug(f"[调度器] 任务 {event.job_id} 执行成功")


# 添加监听器
scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)


# ============ 保活任务 ============

def keep_alive():
    """保活定时任务 - 监管房间信息健康"""
    try:
        logger.info("[保活任务] 开始执行")
        clean_zombie_connections()
        if INIT_SCRCPY_LINK:
            refresh_cloud_phone_adb_link()
    except Exception as e:
        logger.error(f"[保活任务] 执行失败: {e}", exc_info=True)


# ============ 房间扣减时长任务 ============

def active_room_deduct_time_job():
    """活跃房间扣减用户使用时长 - 批量更新版"""
    job_name = "[扣减时长任务]"
    try:
        # 查询所有owner不为空的房间
        active_rooms = session.query(RoomsDao).filter(
            RoomsDao.owner.isnot(None)
        ).all()

        if not active_rooms:
            logger.info(f"{job_name} 无有房主的房间，任务结束")
            return

        total_seconds = MEMBER_ONLY_USE_HOURS * 3600
        to_clean_rooms = []  # 记录需要重置的房间ID
        room_updates = []  # 批量更新房间数据
        user_updates = []
        sse_messages = []  # 收集需要发送SSE的消息

        logger.info(f"{job_name} 开始处理 {len(active_rooms)} 个有房主的房间")

        for room in active_rooms:
            room_id = room.id
            owner_id = room.owner
            current_uid = room.current_user
            permission = room.permission

            # 跳过公开房间（不扣时长）
            if permission == RoomPermission.PUBLIC.value:
                continue

            # 房主ID不能为空（查询条件已保证，但保留安全判断）
            if owner_id is None:
                continue

            # 初始化房间更新字段
            room_update = {'id': room_id}
            need_update_room = False

            # --- 房主时长扣减逻辑（适用于所有非public房间） ---
            owner = UsersDao.get_by_id(owner_id)
            if owner:
                # total_duration 为 0 表示不限量，只有存在余量时才扣减
                limited = owner.total_duration > 0
                new_duration = max(0, owner.total_duration - DEDUCT_STEP_SEC) if limited else owner.total_duration

                if limited:
                    logger.info(
                        f"{job_name} 房间 {room_id} 的房主 {owner_id} 扣减 {DEDUCT_STEP_SEC}秒，剩余 {new_duration}秒")
                    user_updates.append({
                        'id': owner.id,
                        'total_duration': new_duration
                    })

                    # 准备SSE消息（发送给当前使用者，仅当房间有人时）
                    if current_uid is not None:
                        sse_messages.append({
                            'room_id': room_id,
                            'target_user_id': current_uid,
                            'type': 'remain_duration',
                            'msg': str(new_duration)
                        })

                    # 时间即将耗尽（最后10分钟），通知打鱼线程下线帐号
                    if new_duration <= 10 * 60:
                        tag = redis_cache.get(f"fish:logout:{room_id}:{current_uid}")
                        if not tag:
                            logger.info(f"设置fish:logout:{room_id}:{current_uid} 标志位为1")
                            redis_cache.setex(name=f"fish:logout:{room_id}:{current_uid}", time=10 * 60 + 5, value="1")

                # 当前打鱼线程是否打满资源的标记位
                finished = redis_cache.get(name=f"hit_fish:finish:{room_id}:{current_uid}")
                if finished:
                    finished = int(finished)

                # 房主时长已经耗尽，或者资源已经打满
                if (limited and new_duration <= 0) or (
                        (finished and finished == 1) and room.permission == RoomPermission.PRIVATE.value):
                    if limited and new_duration <= 0:
                        logger.warning(f"{job_name} 房主 {owner_id} 的剩余时长已用尽，准备清理房间 {room_id}")
                    else:
                        redis_cache.delete(f"hit_fish:finish:{room_id}:{current_uid}")
                        logger.warning(f"{job_name} 房主 {owner_id} 资源已经打满了，直接退出房间")
                    to_clean_rooms.append(room_id)

            # --- SHARE 和 MEMBER_ONLY 额外扣减共享时长（Redis缓存） ---
            if permission in (RoomPermission.SHARE.value,
                              RoomPermission.MEMBER_ONLY.value) and current_uid is not None and current_uid != owner_id:
                redis_key = f"room_time_limit:owner_{owner_id}:user_{current_uid}"
                val = redis_cache.get(redis_key)

                if val is None:
                    remain = total_seconds - DEDUCT_STEP_SEC
                    redis_cache.setex(redis_key, KEY_EXPIRE, remain)
                    logger.info(
                        f"{job_name} 免费共享房间 {room_id} 用户 {current_uid} 首次使用房主 {owner_id} 的房间，剩余 {remain}秒")
                else:
                    # 该共享房间当前正在被使用
                    # 当前打鱼线程是否打满资源的标记位
                    finished = redis_cache.get(name=f"hit_fish:finish:{room_id}:{current_uid}")
                    if finished:
                        finished = int(finished)

                    # 当前使用者剩余的免费时长
                    remain = int(val) - DEDUCT_STEP_SEC
                    redis_cache.setex(redis_key, KEY_EXPIRE, remain)
                    logger.info(
                        f"{job_name} 免费共享房间 {room_id} 用户 {current_uid} 扣减 {DEDUCT_STEP_SEC}秒，剩余 {remain}秒")

                    # 时间即将耗尽（最后10分钟），通知打鱼线程下线帐号
                    if remain <= 10 * 60:
                        tag = redis_cache.get(f"fish:logout:{room_id}:{current_uid}")
                        if not tag:
                            redis_cache.setex(name=f"fish:logout:{room_id}:{current_uid}", time=10 * 60 + 5,
                                              value="1")
                    alive = redis_cache.get(f"room:alive:{room.id}")
                    if remain <= 0 or finished == 1 or not alive:
                        if remain <= 0:
                            logger.warning(f"{job_name} 房间 {room_id} 用户 {current_uid} 共享时长已用尽，强制下线")
                        elif finished == 1:
                            redis_cache.delete(f"hit_fish:finish:{room_id}:{current_uid}")
                            logger.warning(f"{job_name} 房间 {room_id} 用户 {current_uid} 资源已经打满，下线房间")
                        elif not alive:
                            logger.warning(f"房间 {room_id} 的用户 {current_uid} 已经不活跃了,踢出房间")

                        # 标记当前用户下线
                        room_update['current_user'] = None
                        phone_info = CloudPhonesDao.get_by_id(room.phone_id)
                        # 刷新手机连接
                        get_phone_url(phone_info.region, phone_info.id, phone_info.resolution)
                        need_update_room = True

            # 如果有房间更新，添加到批量更新列表
            if need_update_room:
                room_updates.append(room_update)

        # 执行批量更新
        if room_updates:
            session.bulk_update_mappings(RoomsDao, room_updates)
            logger.info(f"{job_name} 批量更新 {len(room_updates)} 个房间")

        if user_updates:
            session.bulk_update_mappings(UsersDao, user_updates)
            logger.info(f"{job_name} 批量更新 {len(user_updates)} 个用户")

        # 发送SSE消息（批量）
        if sse_messages:
            from api.services.room_service import RoomService
            for msg in sse_messages:
                try:
                    RoomService.send_room_msg(
                        room_id=msg['room_id'],
                        target_user_id=msg['target_user_id'],
                        type=msg['type'],
                        msg=msg['msg']
                    )
                except Exception as e:
                    logger.error(f"{job_name} 发送SSE消息失败: {e}")

        # 重置需要清理的房间（使用批量更新 + 清理逻辑）
        for room_id in to_clean_rooms:
            room = session.query(RoomsDao).filter_by(id=room_id).first()
            if room:
                from api.services.room_fish_service import room_action_service
                if room_action_service.is_hit_fish_thread_alive(room_id):
                    room_action_service.stop_hit_fish(room_id)
                clean_room_job(room)

        session.commit()
        logger.info(f"{job_name} 任务完成，清理 {len(to_clean_rooms)} 个房间")

    except Exception as e:
        logger.error(f"{job_name} 执行失败: {e}", exc_info=True)
        session.rollback()
    finally:
        session.remove()
        # 使用 APScheduler 的 interval 触发器重新调度
        try:
            # 检查是否已有该任务，避免重复添加
            job_id = "active_room_deduct"
            existing_job = scheduler.get_job(job_id)
            if existing_job:
                scheduler.reschedule_job(job_id, trigger=IntervalTrigger(seconds=DEDUCT_STEP_SEC))
            else:
                scheduler.add_job(
                    active_room_deduct_time_job,
                    'interval',
                    seconds=DEDUCT_STEP_SEC,
                    id=job_id,
                    replace_existing=True
                )
        except Exception as e:
            logger.error(f"重新调度扣减任务失败: {e}")


def get_owner_user_remain_time(owner_id: int, user_id: int) -> int:
    """
    查询指定用户在对应房主名下单日剩余可用时长（单位：秒）
    :param owner_id: 房主ID
    :param user_id: 使用用户ID
    :return: 剩余秒数，最小返回0
    """
    total_sec = MEMBER_ONLY_USE_HOURS * 3600
    redis_key = f"room_time_limit:owner_{owner_id}:user_{user_id}"
    val = redis_cache.get(redis_key)
    if val is None:
        return total_sec
    return max(0, int(val))


# ============ 清理房间任务 ============

def clean_room_job(room_info: RoomsDao):
    """清理房间 - 不管理 Session，由调用方统一提交"""
    if not room_info:
        return

    room_id = room_info.id
    logger.info(f"[清理房间] 开始清理房间 {room_id}")

    # 重置房间
    room_info.permission = RoomPermission.PUBLIC.value
    room_info.rname = DEFAULT_ROOM_NAME + str(room_id)
    room_info.owner = None
    room_info.current_user = None
    room_info.type = "temporary"
    room_info.white_list = None

    # 停止打鱼
    if task_manager.is_fish_thread_alive(room_id):
        from api.services.room_fish_service import room_action_service
        room_action_service.stop_hit_fish(room_id)
        logger.info(f"[清理房间] 房间 {room_id} 已停止打鱼任务")

    logger.info(f"[清理房间] 房间 {room_id} 准备重置")

    # 重置云手机（这里不涉及数据库操作，可以放在这里）
    if room_info.phone_id:
        phone = CloudPhonesDao.get_by_id(room_info.phone_id)
        if phone:
            get_phone_url(id=room_info.phone_id, region=phone.region)
            logger.info(f"[清理房间] 房间 {room_id} 云手机 {room_info.phone_id} 链接已重置")


# ============ 检查死鱼任务 ============

def check_public_detained_user(room_id: int):
    """清理公共房间内不活跃用户"""
    job_name = "[清理死鱼任务]"
    try:
        if not room_id:
            return

        room = RoomsDao.get_by_id(room_id)
        if not room:
            logger.error(f"{job_name} 房间 {room_id} 不存在")
            return

        if room.permission not in (RoomPermission.SHARE.value, RoomPermission.MEMBER_ONLY.value):
            return

        if not room.current_user:
            return

        status = redis_cache.get(f"room:alive:{room_id}")
        if not status and room.current_user != room.owner:
            logger.info(f"{job_name} 房间 {room_id} 用户 {room.current_user} 不活跃，执行踢出")

            room.current_user = None
            session.commit()

            RoomLogDao.add_log(
                room_id=room.id,
                event_type="leave_room",
                operator_id=0,
                operator_name="system"
            )
            logger.info(f"{job_name} 房间 {room_id} 用户已踢出")

    except Exception as e:
        logger.error(f"{job_name} 房间 {room_id} 执行失败: {e}", exc_info=True)
        session.rollback()
    finally:
        session.remove()


# ============ 清理僵尸连接 ============

def clean_zombie_connections(threshold_minutes: int = ZOMBIE_THRESHOLD_MINUTES):
    """
    清理僵尸数据库连接（idle in transaction 超过阈值）
    """
    job_name = "[清理僵尸连接]"
    try:
        logger.info(f"{job_name} 开始扫描 (阈值: {threshold_minutes} 分钟)")

        sql = text(f"""
            SELECT pid, usename, application_name, client_addr, 
                   xact_start, query_start,
                   EXTRACT(EPOCH FROM (NOW() - xact_start)) AS idle_seconds,
                   LEFT(query, 200) AS query_preview
            FROM pg_stat_activity 
            WHERE datname = current_database()
              AND state = 'idle in transaction'
              AND xact_start IS NOT NULL
              AND xact_start < NOW() - INTERVAL '{threshold_minutes} MINUTE'
              AND pid != pg_backend_pid()
              AND usename NOT IN ('postgres', 'replication')
            ORDER BY xact_start
        """)

        result = session.execute(sql)
        rows = result.fetchall()

        if not rows:
            logger.info(f"{job_name} 没有发现僵尸连接")
            return

        logger.warning(f"{job_name} 发现 {len(rows)} 个僵尸连接")

        killed_count = 0
        for row in rows:
            pid = row[0]
            usename = row[1]
            app_name = row[2] or "unknown"
            client_addr = row[3] or "local"
            idle_seconds = row[6] or 0
            idle_minutes = int(idle_seconds / 60)
            query_preview = row[7] or "unknown"

            logger.warning(
                f"{job_name} 僵尸连接: pid={pid}, user={usename}, app={app_name}, "
                f"client={client_addr}, idle={idle_minutes}分钟"
            )

            # 终止僵尸连接
            try:
                terminate_sql = text(f"SELECT pg_terminate_backend({pid})")
                result2 = session.execute(terminate_sql)
                session.commit()
                if result2.scalar():
                    killed_count += 1
                    logger.info(f"{job_name} 已终止连接 pid={pid}")
                else:
                    logger.warning(f"{job_name} 终止连接 pid={pid} 失败，可能已被释放")
            except Exception as e:
                logger.error(f"{job_name} 终止连接 pid={pid} 失败: {e}")
                session.rollback()

        logger.info(f"{job_name} 完成，共清理 {killed_count} 个僵尸连接")

    except Exception as e:
        logger.error(f"{job_name} 执行失败: {e}", exc_info=True)
        try:
            session.rollback()
        except:
            pass
    finally:
        try:
            session.remove()
        except:
            pass


# ============ 刷新所有云手机adb连接 ============

def refresh_cloud_phone_adb_link():
    logger.info("[刷新云手机adb过期链接]")
    rooms = RoomsDao.get_all()
    for room in rooms:
        phone_info = CloudPhonesDao.get_by_id(room.phone_id)
        if task_manager.is_fish_thread_alive(room.id):
            continue
        try:
            link = RoomActionService.get_or_create_game_assist(adb_addr=phone_info.address)
            if link:
                logger.info(f"云手机 {phone_info.id} 链接检查正常")
                redis_cache.setex(name=f"device:status:{room.phone_id}", time=KEEP_ALIVE_INTERVAL_SEC * 2, value=1)
            else:
                logger.error(f"云手机 {phone_info.id} 链接为空")
                redis_cache.setex(name=f"device:status:{room.phone_id}", time=KEEP_ALIVE_INTERVAL_SEC * 2, value=0)
        except Exception as e:
            logger.error(f"云手机 {phone_info.id} 的scrcpy连接初始化失败")


# ============ 启动调度器 ============

def start_scheduler():
    """启动调度器"""
    logger.info("[启动] APScheduler 调度器启动")

    # 启动调度器
    scheduler.start()

    # 添加定时任务：保活任务（每隔30分钟执行一次）
    scheduler.add_job(
        keep_alive,
        'interval',
        seconds=KEEP_ALIVE_INTERVAL_SEC,
        id='keep_alive',
        replace_existing=True
    )
    logger.info(f"[启动] 保活任务已添加，间隔 {KEEP_ALIVE_INTERVAL_SEC} 秒")

    # 添加定时任务：扣减时长（第一次延迟 DEDUCT_STEP_SEC 秒后执行，之后每隔 DEDUCT_STEP_SEC 秒执行）
    scheduler.add_job(
        active_room_deduct_time_job,
        'interval',
        seconds=DEDUCT_STEP_SEC,
        id='active_room_deduct',
        replace_existing=True
    )
    logger.info(f"[启动] 扣减时长任务已添加，间隔 {DEDUCT_STEP_SEC} 秒")

    # 添加定时任务：清理僵尸连接（每小时执行一次）
    scheduler.add_job(
        clean_zombie_connections,
        'interval',
        hours=1,
        id='clean_zombie_connections',
        replace_existing=True
    )
    logger.info("[启动] 清理僵尸连接任务已添加，间隔 1 小时")

    logger.info("[启动] 所有任务已添加到调度器")


def stop_scheduler():
    """停止调度器"""
    logger.info("[停止] 正在停止 APScheduler 调度器...")
    try:
        # 关闭所有 session
        session.remove()
        # 关闭调度器
        scheduler.shutdown(wait=True)
        logger.info("[停止] 调度器已停止")
    except Exception as e:
        logger.error(f"[停止] 停止调度器失败: {e}")


# ============ 启动调度器 ============

logger.info("[启动] 定时任务调度器初始化")
start_scheduler()

# 注册关闭钩子
import atexit

atexit.register(stop_scheduler)