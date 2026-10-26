import json
import time
import uuid
import queue
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Set

from flask import g
from sqlalchemy import update

from api.api_config import session
from api.cloud_phone.chinac_open_api import get_phone_url
from api.dao.ads_dao import AdsDao
from api.dao.cloud_phone_dao import CloudPhonesDao
from api.dao.room_logs_dao import RoomLogDao
from api.dao.rooms_dao import RoomsDao
from api.dao.users_dao import UsersDao
from api.exception.room_exception import RoomNotFoundException, PhoneNotFoundException, PermissionDeniedException, \
    IdempotencyException, ResourceInsufficientException, CloudPhoneNotAvailableException, ParamInvalidException, \
    RoomException
from api.models.my_enum import RoomPermission
from api.models.request.room_request import CreateRoomRequest
from api.models.response.room_response import CreateRoomResponse, UpdateRoomWhiteListResponse, \
    UpdateRoomPermissionResponse, UpdateRoomCurrentUserResponse
from api.services.my_scheduler import clean_room_job, get_owner_user_remain_time
from src.my_logger import logger
from src.redis_client import redis_cache

# 存储所有SSE订阅队列：room_id -> {uid: 消息队列}
room_sub = defaultdict(dict)
# 保护外层字典并发读写锁，杜绝KeyError、并发修改异常
room_sub_lock = threading.Lock()


class RoomService:
    """房间服务类，负责房间的创建、查询、操作等核心业务逻辑"""

    # 管理员用户ID列表，用于权限控制
    ADMIN_USER_IDS = (4, 6)

    def room_list(self):
        rooms = RoomsDao.get_all()
        resp = []
        if not rooms or len(rooms) == 0:
            return []
        for room in rooms:
            current_user_name = None
            if room.current_user:
                current_user = UsersDao.get_by_id(room.current_user)
                if current_user:
                    current_user_name = current_user.name
            remain_time = None
            if room.current_user and room.current_user != room.owner and room.permission == RoomPermission.MEMBER_ONLY.value:
                remain_time = get_owner_user_remain_time(owner_id=room.owner, user_id=room.current_user)
            resp.append({
                "room_id": room.id,
                "room_name": room.rname,
                "current_user_name": current_user_name,
                "owner": room.owner,
                "device": redis_cache.get(name=f"device:status:{room.phone_id}"),
                "permission": room.permission,
                "status": "busy" if room.current_user else "idle",
                "white_lite": room.white_list,
                "remain_time": remain_time
            })
        return resp

    def sse_stream(self, room_id, uid):
        """SSE长连接推送流，原生线程安全队列，30秒心跳ping"""
        msg_queue = queue.Queue()
        # 加锁：写入订阅字典
        with room_sub_lock:
            logger.info(f"和房间 {room_id} 的用户 {uid} 建立SSE链接消息队列")
            room_sub[room_id][uid] = msg_queue

        try:
            logger.info(f"[SSE] 开始循环 uid={uid}")
            # loop_count = 0
            while True:
                # loop_count += 1
                # logger.debug(f"[SSE] 第{loop_count}次循环开始 uid={uid}")
                try:
                    data = msg_queue.get(timeout=30)
                    logger.debug(f"[SSE] 获取到消息: {data} uid={uid}")
                    yield f"data:{json.dumps(data, ensure_ascii=False)}\n\n".encode('utf-8')
                    logger.debug(f"[SSE] yield成功 uid={uid}")
                except queue.Empty:
                    logger.debug(f"[SSE] 队列超时，发送心跳 uid={uid}")
                    yield f"data:{json.dumps({'type': 'ping'})}\n\n".encode('utf-8')
                    logger.debug(f"[SSE] 心跳发送成功 uid={uid}")
                except Exception as inner_e:
                    # ===== 关键：捕获内层所有异常 =====
                    logger.error(f"[SSE] 内层循环异常: uid={uid}, error={inner_e}, type={type(inner_e)}")
                    # 可以选择继续或退出
                    raise  # 重新抛出，让外层捕获
        except GeneratorExit as e:
            logger.info(f"[SSE] 捕获GeneratorExit: uid={uid}, error={e}")
            pass
        except Exception as e:
            # logger.error(f"[SSE] 外层捕获异常: uid={uid}, error={e}, type={type(e)}")
            pass
        finally:
            # logger.info(f"[SSE]  uid={uid}, loop_count={loop_count}")
            with room_sub_lock:
                if room_id in room_sub and uid in room_sub[room_id]:
                    del room_sub[room_id][uid]
                    logger.info(f"清理SSE链接 room_id={room_id}, uid={uid}")
                if room_id in room_sub and len(room_sub[room_id]) == 0:
                    del room_sub[room_id]
                    logger.info(f"房间 {room_id} 已无在线用户")

    @classmethod
    def send_room_msg(cls, room_id: int, target_user_id: int, type: str, msg: str):
        """向指定房间用户推送SSE消息，线程安全写入队列"""
        if not room_id or not target_user_id or not type or not msg:
            logger.debug("发送消息参数错误")
            return False

        # 组装推送字典
        push_data = {
            "type": type,
            "msg": msg,
            "room_id": room_id
        }

        # 先检查SSE连接是否存在（不加锁，只读检查）
        if room_id not in room_sub or target_user_id not in room_sub.get(room_id, {}):
            # room_users = {rid: list(users.keys()) for rid, users in room_sub.items()}
            # logger.warning(
            #     f"❌ SSE连接不存在，无法发送消息: room_id={room_id}, user_id={target_user_id}, type={type}, room_sub={room_users}")
            return False

        # 加锁原子查询+推送，防止中途键被删除
        with room_sub_lock:
            # 双重检查，防止在获取锁期间连接被断开
            if room_id in room_sub and target_user_id in room_sub[room_id]:
                # logger.debug(f"✅ SSE队列已连接，推送消息: room_id={room_id}, user_id={target_user_id}, type={type}")
                room_sub[room_id][target_user_id].put(push_data)
                return True
            else:
                logger.warning(f"❌ 获取锁后SSE连接已断开: room_id={room_id}, user_id={target_user_id}")
                return False

    def apply_operate(self, room_id) -> UpdateRoomCurrentUserResponse:
        # 参数校验
        if not room_id:
            raise ParamInvalidException("参数不合法")
        room = RoomsDao.get_by_id(room_id)
        if not room:
            logger.error(f"房间不存在: room_id={room_id}")
            raise RoomNotFoundException("房间不存在")
        phone = CloudPhonesDao.get_by_id(room.phone_id)
        if not phone:
            logger.error(f"云手机不存在: phone_id={phone.id}")
            raise RoomNotFoundException("云手机不存在")

        apply_uid = g.uid
        # 房主直接无限制接管，不走冷却与任务占用校验
        if room.owner == apply_uid:
            return self._upate_current_user(apply_uid, phone, room, room_id)

        # 非房主走普通申请流程
        if room.permission == "member_only" and room.current_user is None:
            return self._upate_current_user(apply_uid, phone, room, room_id)
        elif room.permission == "share" and room.current_user is None:
            return self._upate_current_user(apply_uid, phone, room, room_id)
        elif room.permission == "public" and room.current_user is None:
            return self._upate_current_user(apply_uid, phone, room, room_id)

    def _upate_current_user(self, apply_uid, phone, room, room_id) -> UpdateRoomCurrentUserResponse:
        room.current_user = apply_uid
        room.phone_url = None
        # 刷新房间最后一次操作的时间
        key = f"last_operate_time:{room_id}"
        now_ts = int(time.time())
        redis_cache.set(key, str(now_ts))
        logger.info(f"房间{room_id}用户{apply_uid}接管操作权成功")
        # 重新获取云手机操作URL
        url = get_phone_url(phone.region, phone.id, phone.resolution)

        session.commit()
        session.refresh(room)
        return UpdateRoomCurrentUserResponse(room_id, current_user=apply_uid, current_user_name=g.uname,
                                             phone_url=url)

    def leave_room(self, room_id: int) -> bool:
        logger.debug("执行离开房间逻辑")
        if not room_id:
            raise RoomException(f"房间不存在: room_id={room_id}")
        room = RoomsDao.get_by_id(room_id)
        user = UsersDao.get_by_id(g.uid)
        if not room:
            raise RoomException(f"房间不存在: room_id={room_id}")
        if not user:
            raise RoomException(f"用户不存在: room_id={g.uid}")

        from api.services.room_fish_service import room_action_service
        if room_action_service.get_task_status(room_id):
            logger.info("离开房间，顺便停止打鱼")
            room_action_service.stop_hit_fish(room_id)
        else:
            logger.info("当前没有正在打鱼")

        if room.current_user and room.current_user == g.uid:
            logger.info(f"用户 {g.uid} 退出房间 {room_id} ")

            if room.permission == RoomPermission.PRIVATE.value and room.current_user == room.owner:
                clean_room_job(room)
            else:
                room.current_user = None

            session.commit()
            session.refresh(room)
            RoomLogDao.add_log(room_id=room.id, event_type="leave_room",
                               operator_id=g.uid if g.uid is not None else 0,
                               operator_name=g.uname if g.uname is not None else "system")
            return True

        logger.info(f"用户 {g.uid} 已经不是当前房间 {room_id} 的使用者")
        return False

    def update_room_permission(self, room_id, permission: str) -> UpdateRoomPermissionResponse:
        logger.debug(f"执行更新房间 {room_id} 权限至 {permission} 的程序")
        if not room_id or not permission or not RoomPermission.is_valid_perm(permission):
            raise ParamInvalidException("参数不合法")
        room = self.validate_room_permission(room_id)
        if room.owner != g.uid:
            raise PermissionDeniedException("没有权限更改房间的权限")

        if room.permission == permission:
            return UpdateRoomPermissionResponse(room_id, permission)
        elif permission == RoomPermission.PUBLIC.value:
            logger.debug(f"房间 {room_id} 权限改成公共,房间将会被归还")
            clean_room_job(room)
        else:
            room.permission = permission
            session.commit()
            session.refresh(room)
        return UpdateRoomPermissionResponse(room_id, room.permission)

    def update_room_name(self, room_id, new_name) -> dict:
        if not room_id or not new_name or len(new_name) < 1 or len(new_name) > 10:
            raise ParamInvalidException("参数不合法")
        room = self.validate_room_permission(room_id)
        if room.permission == RoomPermission.PUBLIC.value:
            raise RoomException("候选房间无法更改房间名称")

        room.rname = new_name
        session.commit()
        session.refresh(room)
        return {"room_id": room_id, "rname": room.rname}

    def update_room_white_list(self, room_id: int, d_uids: str) -> UpdateRoomWhiteListResponse:
        # 1. 参数校验
        if not room_id:
            raise ParamInvalidException("参数不合法")

        # 2. 查询房间信息
        room = self.validate_room_permission(room_id)
        if room.owner != g.uid:
            raise PermissionDeniedException("没有权限更改房间的权限")

        if room.permission != RoomPermission.MEMBER_ONLY.value:
            raise RoomException("只有部落房间才能设置白名单")

        if not d_uids:
            room.white_list = None
            session.commit()
            return UpdateRoomWhiteListResponse(room_id, [])
        uids_list = d_uids.split(",")
        target_uids = uids_list
        if len(target_uids) > 0:
            target_uids = list(target_uids)
            room.white_list = json.dumps(target_uids)
            session.commit()
            session.refresh(room)
            white_key = f"white_list:{room.id}"
            # 先删除原有集合，再写入
            redis_cache.delete(white_key)
            redis_cache.sadd(white_key, *target_uids)
            return UpdateRoomWhiteListResponse(room_id, target_uids)
        else:
            raise RoomException("提交的用户展示ID全部无效，无合法用户可加入白名单")

    def get_room_white_list(self, room_id: int) -> UpdateRoomWhiteListResponse:
        """获取房间白名单"""
        # 1. 参数校验
        if not room_id:
            raise ParamInvalidException("参数不合法")

        # 2. 查询房间信息并校验权限
        room_info = RoomsDao.get_by_id(room_id)
        if not room_info:
            logger.error(f"房间不存在: room_id={room_id}")
            raise RoomNotFoundException("房间不存在")

        if room_info.owner != g.uid:
            raise PermissionDeniedException("没有权限查看该房间白名单")

        # 3. 获取白名单（带缓存）
        white_set = self.parse_white_list(room_info.white_list)

        # 4. 构建返回结果
        user_dict = UsersDao.batch_get_by_id(list(white_set))
        white_user = []
        for uid, user in user_dict.items():
            white_user.append({
                "uid": uid,
                "name": user.name,
                "display_uid": user.display_uid
            })

        return UpdateRoomWhiteListResponse(room_id, white_user)

    def apply_white_list(self, room_id: int) -> UpdateRoomWhiteListResponse:
        """用户自助申请加入房间白名单（仅成员房间）"""
        # 1. 参数校验
        if not room_id:
            raise ParamInvalidException("参数不合法")

        # 2. 查询房间
        room = RoomsDao.get_by_id(room_id)
        if not room:
            logger.error(f"房间不存在: room_id={room_id}")
            raise RoomNotFoundException("房间不存在")

        if room.permission != RoomPermission.MEMBER_ONLY.value:
            raise RoomException("只有仅成员房间支持申请加入")

        # 3. 房主无需申请
        white_set = self.parse_white_list(room.white_list)
        if room.owner == g.uid:
            return UpdateRoomWhiteListResponse(room_id, sorted(white_set))

        # 4. 把当前用户加入白名单（白名单以字符串uid存储，与前端判断保持一致）
        white_key = f"white_list:{room.id}"
        apply_uid = str(g.uid)
        if int(apply_uid) not in white_set:
            white_set.add(int(apply_uid))
            # 统一转成字符串排序后落库
            str_white_set = sorted(str(uid) for uid in white_set)
            room.white_list = json.dumps(str_white_set) if str_white_set else None
            session.commit()
            session.refresh(room)
            # 同步更新缓存集合
            redis_cache.delete(white_key)
            redis_cache.sadd(white_key, *str_white_set)
            logger.info(f"用户 {g.uid} 自助申请加入房间 {room_id} 白名单成功")

        return UpdateRoomWhiteListResponse(room_id, sorted(white_set))

    def parse_white_list(self, raw_str: str | None) -> Set[int]:
        """解析库中white_list JSON字符串为int uid集合，空/异常返回空集合"""
        if not raw_str or raw_str.strip() == "":
            return set()
        try:
            uid_list = json.loads(raw_str)
            # 只保留合法数字uid
            return {int(uid) for uid in uid_list if isinstance(uid, (int, str)) and str(uid).strip().isdigit()}
        except (json.JSONDecodeError, ValueError, TypeError):
            # JSON格式损坏直接返回空白名单
            return set()

    def _try_init_phone_url(self, room, phone) -> bool:
        """
        尝试初始化云手机连接URL
        :return: True表示需要提交事务，False表示无需更新
        :raises PhoneNotFoundException: 无法获取连接地址
        """
        if phone.id == "local_test":
            room.phone_url = "https://www.baidu.com"
            return False
        logger.debug(f"初始化云手机连接: phone_id={phone.id}")
        url = get_phone_url(phone.region, phone.id, phone.resolution)
        if not url:
            logger.error(f"无法获取云手机连接地址: phone_id={phone.id}")
            raise PhoneNotFoundException("无法获取云手机连接")

        room.phone_url = url
        return True

    @classmethod
    def validate_room_permission(cls, room_id: int) -> RoomsDao:
        """校验房间存在且当前用户有操作权限"""
        room_info = RoomsDao.get_by_id(room_id)
        if not room_info:
            logger.error(f"房间不存在: room_id={room_id}")
            raise RoomNotFoundException("房间不存在")

        if room_info.owner != g.uid:
            raise PermissionDeniedException("没有权限操作该房间")

        return room_info

    def create_room(self, request: CreateRoomRequest) -> Optional[CreateRoomResponse]:
        """
        创建房间（仅管理员可用）
        流程：幂等校验 → 选择云手机 → 管理员校验 → 原子化创建
        """
        # 幂等校验
        self._check_idempotent(g.uid)

        # 选择空闲云手机
        selected_phone = self._pick_idle_phone(request)

        # 仅管理员可创建
        if g.uid not in self.ADMIN_USER_IDS:
            logger.info(f"非管理员用户尝试创建房间: uid={g.uid}")
            return None

        logger.info(f"管理员创建房间: uid={g.uid}")

        # 原子化创建房间
        new_room = self._occupy_phone_and_create_room(request, selected_phone)

        session.refresh(new_room)
        if not new_room.id:
            return None

        return CreateRoomResponse(new_room.id, request.room_name, selected_phone.id)

    def _check_idempotent(self, uid: int) -> None:
        """
        幂等校验：5秒内禁止重复提交
        :raises IdempotencyException: 操作过于频繁
        """
        cache_key = f"room:create:{uid}"
        if redis_cache.get(cache_key):
            raise IdempotencyException("操作过于频繁")
        redis_cache.set(cache_key, 1, ex=5)

    def _pick_idle_phone(self, request: CreateRoomRequest):
        """
        选择空闲云手机
        :param request: 创建请求
        :return: 选中的空闲云手机
        :raises CloudPhoneNotAvailableException: 指定手机不可用
        :raises ResourceInsufficientException: 无空闲手机
        """
        # 指定手机ID的情况
        if request.phone_id is not None:
            phone = CloudPhonesDao.get_by_id(request.phone_id)
            if not phone or phone.status != "idle":
                raise CloudPhoneNotAvailableException(f"云手机 {request.phone_id} 不可选用")
            return phone

        # 自动分配空闲手机
        idle_phones = CloudPhonesDao.get_idles()
        if not idle_phones:
            raise ResourceInsufficientException("云手机资源不足")
        return idle_phones[0]

    def _occupy_phone_and_create_room(self, request: CreateRoomRequest, init_selected_phone):
        """
        原子操作：抢占云手机并创建房间
        使用乐观锁确保并发安全
        """
        # 尝试抢占初始手机
        selected_phone = self._try_occupy_phone(init_selected_phone)
        if not selected_phone:
            # 抢占失败，重试其他手机
            selected_phone = self._retry_occupy_other_phone()

        # 创建房间记录
        end_time = datetime.utcnow() + timedelta(hours=request.duration)
        new_room = RoomsDao(
            rname=request.room_name,
            type=request.type,
            permission=request.permission,
            phone_id=selected_phone.id,
            owner=g.uid,
            end_time=end_time
        )
        session.add(new_room)
        session.commit()
        return new_room

    def _try_occupy_phone(self, phone):
        """尝试抢占单个云手机，返回抢占成功后的手机实例或None"""
        update_stmt = (
            update(CloudPhonesDao)
            .where(CloudPhonesDao.id == phone.id)
            .where(CloudPhonesDao.status == "idle")
            .values(status="active")
        )
        result = session.execute(update_stmt)
        session.flush()  # 立即执行更新，但不提交事务

        if result.rowcount == 1:
            return phone
        return None

    def _retry_occupy_other_phone(self, max_retries: int = 5):
        for attempt in range(max_retries):
            idle_phones = CloudPhonesDao.get_idles()
            if not idle_phones:
                break

            for phone in idle_phones:
                occupied_phone = self._try_occupy_phone(phone)
                if occupied_phone:
                    return occupied_phone

        raise ResourceInsufficientException("云手机资源不足")

    def get_ads(self, type):
        ads = AdsDao.get_by_type(type)
        return [ad.content for ad in ads]


# 单例实例
room_service = RoomService()
