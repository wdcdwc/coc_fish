import json
import threading
from datetime import datetime, timedelta
from typing import Set, Optional, Tuple

from flask import g

from api.api_config import session, DEFAULT_ROOM_NAME
from api.cloud_phone.chinac_open_api import get_phone_url
from api.dao.cloud_phone_dao import CloudPhonesDao
from api.dao.room_logs_dao import RoomLogDao
from api.dao.rooms_dao import RoomsDao
from api.dao.users_dao import UsersDao
from api.exception.room_exception import RoomNotFoundException, PhoneNotFoundException, PermissionDeniedException, \
    ParamInvalidException, RoomException
from api.models.my_enum import RoomPermission
from api.models.response.room_response import RoomInfoResponse
from api.services.my_scheduler import get_owner_user_remain_time
from api.services.room_fish_service import RoomActionService
from src.my_logger import logger
from src.redis_client import redis_cache


class EnterRoomService:
    """进入房间服务类"""

    # ==================== 主入口 ====================

    def get_room(self, room_id: int, room_name:str) -> RoomInfoResponse:
        """
        根据房间ID查询房间详情信息
        :param room_id: 房间ID
        :return: 房间信息响应实体
        """
        # 1. 参数校验
        self._validate_room_id(room_id)

        # 2. 查询房间和云手机
        room, phone = self._get_room_and_phone(room_id)

        # 3. 公共房间由第一个进入的用户认领
        if room.permission == RoomPermission.PUBLIC.value:
            return self._handle_public_entry(room, room_name, phone)

        # 4. 获取房主信息
        owner = UsersDao.get_by_id(room.owner)

        # 5. 根据权限分发处理
        logger.debug(f"用户 {g.uid} 正在进入房间 {room_id}")
        if room.owner == g.uid:
            return self._handle_owner_entry(room, phone, owner)

        if room.permission == RoomPermission.MEMBER_ONLY.value:
            return self._handle_member_entry(room, phone, owner=owner)

        if room.permission == RoomPermission.SHARE.value:
            return self._handle_share_entry(room, phone, owner)

        if room.permission == RoomPermission.PRIVATE.value:
            raise RoomException("仅房主能使用")

        raise RoomException("未识别房间类型")

    # ==================== 参数校验 ====================

    def _refresh_scrcpy(self,room_info:RoomsDao):
        phone_info = CloudPhonesDao.get_by_id(room_info.phone_id)
        logger.info(f"刷新云手机 {phone_info.address} 的远程链接")
        if RoomActionService.get_or_create_game_assist(phone_info.address):
            from api.services.room_fish_service import room_game_assists
            connect = room_game_assists.pop(phone_info.address, None)
            if connect:
                connect.client_stop()
                logger.debug(f"清理原来云手机 {phone_info.address} 的链接")
                threading.Event().wait(0.2)
            RoomActionService.get_or_create_game_assist(phone_info.address)

    def _validate_room_id(self, room_id: int) -> None:
        """校验房间ID"""
        if not room_id:
            raise ParamInvalidException("参数不合法")

    # ==================== 查询方法 ====================

    def _get_room_and_phone(self, room_id: int) -> Tuple[RoomsDao, CloudPhonesDao]:
        """查询房间和云手机"""
        room = RoomsDao.get_by_id(room_id)
        if not room:
            logger.error(f"房间不存在: room_id={room_id}")
            raise RoomNotFoundException("房间不存在")

        phone = CloudPhonesDao.get_by_id(room.phone_id)
        if not phone:
            logger.error(f"云手机不存在: phone_id={room.phone_id}, room_id={room.id}")
            raise PhoneNotFoundException(f"云手机不存在: id={room.phone_id}")

        return room, phone

    def _get_owner(self, room: RoomsDao) -> Optional[UsersDao]:
        """获取房主信息"""
        return UsersDao.get_by_id(room.owner)

    # ==================== 房间处理器 ====================

    def _handle_owner_entry(self, room: RoomsDao, phone: CloudPhonesDao,
                            owner: Optional[UsersDao]) -> RoomInfoResponse:
        """房主进入房间"""
        room.current_user = room.owner
        url = get_phone_url(phone.region, phone.id, phone.resolution)

        session.commit()
        session.refresh(room)
        redis_cache.set(f"room:alive:{room.id}", 1, ex=10 * 60)
        return self._build_response(
            room=room,
            url=url,
            owner=owner,
            end_time=None,
            current_user=g.uid,
            current_user_name=g.uname
        )

    def _handle_member_entry(self, room: RoomsDao, phone: CloudPhonesDao,
                              owner: Optional[UsersDao]) -> RoomInfoResponse:
        """成员进入 member_only 房间"""
        white_set = self.parse_white_list(room.white_list)

        # 1. 权限检查
        if g.uid not in white_set:
            raise RoomException("仅房主和白名单成员可以进入房间")

        # 2. 房间是否已满
        if room.current_user is not None and room.current_user != g.uid:
            raise PermissionDeniedException("房间已满")

        # 3. 检查是否在房主下开了其他房间
        if self._check_user_in_owner_room(owner_id=room.owner, exclude_room_id=room.id):
            raise PermissionDeniedException("无法同时进入房主的两个仅成员房间")

        # 4. 检查用户剩余时长
        remain_time =  get_owner_user_remain_time(owner_id=room.owner, user_id=g.uid)
        if remain_time <= 5:
            raise PermissionDeniedException("今日时长已经用满")
        logger.info(f"可用时长 {remain_time} 秒")
        # 5. 进入房间
        room.current_user = g.uid
        session.commit()
        session.refresh(room)

        url = get_phone_url(phone.region, phone.id, phone.resolution)

        RoomLogDao.add_log(
            room_id=room.id,
            event_type="enter_room",
            operator_id=g.uid,
            operator_name=g.uname
        )
        redis_cache.set(f"room:alive:{room.id}", 1, ex=10 * 60)
        return self._build_response(
            room=room,
            url=url,
            owner=owner,
            end_time = (datetime.utcnow() + timedelta(seconds=remain_time)).isoformat() + "Z", #前端的new Date会把它自动转成当地的时间
            current_user=g.uid,
            current_user_name=g.uname
        )

    def _check_user_in_owner_room(self, owner_id: int, exclude_room_id: int = None) -> bool:
        """
        检查用户是否已经在同一个 owner 的某个 member_only 房间中

        Args:
            owner_id: 房主ID
            exclude_room_id: 排除的房间ID（用于进入新房间时，忽略目标房间本身）

        Returns:
            True: 用户已在其他房间中
            False: 用户不在任何房间中
        """
        # 获取该 owner 的所有 member_only 房间
        rooms = session.query(RoomsDao).filter_by(
            owner=owner_id,
            permission=RoomPermission.MEMBER_ONLY.value
        ).all()

        for room in rooms:
            if exclude_room_id is not None and room.id == exclude_room_id:
                continue
            # 检查用户是否在这个房间中
            if room.current_user and room.current_user == g.uid:
                return True

        return False

    def _handle_share_entry(self, room: RoomsDao, phone: CloudPhonesDao,
                            owner: Optional[UsersDao]) -> RoomInfoResponse:
        """共享房间进入"""
        if room.current_user and room.current_user != g.uid:
            raise RoomException("房间已满")

        remain_time = get_owner_user_remain_time(owner_id=room.owner, user_id=g.uid)

        room.current_user = g.uid
        session.commit()
        session.refresh(room)

        url = get_phone_url(phone.region, phone.id, phone.resolution)

        RoomLogDao.add_log(
            room_id=room.id,
            event_type="enter_room",
            operator_id=g.uid,
            operator_name=g.uname
        )
        redis_cache.set(f"room:alive:{room.id}", 1, ex=10 * 60)
        return self._build_response(
            room=room,
            url=url,
            owner=owner,
            end_time=(datetime.utcnow() + timedelta(seconds=remain_time)).isoformat() + "Z",
            current_user=g.uid,
            current_user_name=g.uname
        )

    def _handle_public_entry(self, room: RoomsDao, room_name:str, phone:CloudPhonesDao) -> RoomInfoResponse:
        """公共房间由第一个进入的用户认领为自己的私人房间"""
        if not room_name:
            room_name = "我的" + DEFAULT_ROOM_NAME
        room_name = room_name.strip()

        if len(room_name) > 10 or len(room_name) < 1:
            raise RoomException("房间的名字必须在1～10个字符之间")

        if room.current_user is not None and room.current_user != g.uid:
            raise RoomException("房间正在被使用")

        try:
            RoomActionService.get_or_create_game_assist(phone.address)
        except Exception:
            logger.error(f"云手机 {phone.address} 不可用")
            raise RoomException("云手机资源不可用")

        room.owner = g.uid
        room.current_user = g.uid
        room.permission = RoomPermission.PRIVATE.value
        room.rname = room_name

        session.commit()
        session.refresh(room)

        RoomLogDao.add_log(
            room_id=room.id,
            event_type="enter_room",
            operator_id=g.uid,
            operator_name=g.uname
        )
        redis_cache.set(f"room:alive:{room.id}", 1, ex=10 * 60)
        return self._build_response(
            room=room,
            url=get_phone_url(phone.region, phone.id, phone.resolution),
            owner=self._get_owner(room),
            end_time=None,
            current_user=g.uid,
            current_user_name=g.uname
        )


    # ==================== 响应构建 ====================

    def _build_response(self, room: RoomsDao, url: str, owner: Optional[UsersDao],
                        end_time: str | None, current_user: int, current_user_name: str, duration: int=0) -> RoomInfoResponse:
        """构建通用房间响应"""
        return RoomInfoResponse(
            room_id=room.id,
            room_name=room.rname,
            phone_url=url,
            permission=room.permission,
            owner=room.owner,
            owner_name=owner.name if owner else None,
            current_user=current_user,
            current_user_name=current_user_name,
            create_time=(room.create_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
            end_time=end_time,
            specific_solder=redis_cache.get(f"fish:solders:{room.id}:{g.uid}"),
            fish_server=room.fish_server,
            duration=duration
        )

    # ==================== 工具方法 ====================

    def parse_white_list(self, raw_str: str | None) -> Set[int]:
        """解析库中white_list JSON字符串为int uid集合，空/异常返回空集合"""
        if not raw_str or raw_str.strip() == "":
            return set()

        try:
            uid_list = json.loads(raw_str)
            return {int(uid) for uid in uid_list if isinstance(uid, (int, str)) and str(uid).strip().isdigit()}
        except (json.JSONDecodeError, ValueError, TypeError):
            return set()


enter_room_service = EnterRoomService()