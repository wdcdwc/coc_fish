import threading
import time
import traceback
from typing import Dict
from urllib.parse import urlparse

from flask import g

import hit_fish
from api.dao.cloud_phone_dao import CloudPhonesDao
from api.dao.room_logs_dao import RoomLogDao
from api.dao.rooms_dao import RoomsDao
from api.dao.website_links_dao import WebsiteLinksDao
from api.exception.game_exception import GameException
from api.exception.room_exception import RoomNotFoundException, PermissionDeniedException, RoomException, \
    ParamInvalidException, PhoneNotFoundException
from api.services.task_manager import task_manager, TaskStructure
from asserts import attack_on_main
from game_assist_uiautomator import U2GameAssist
from hit_fish_dark import HitFishDark
from src.redis_client import redis_cache
from src.api.api_config import run_with_timeout, OperationTimeoutError
from src.hit_fish import HitFish
from src.my_logger import logger
from utils import contains_ui

# 全局游戏辅助实例缓存，key为adb地址，value为对应的游戏辅助实例
room_game_assists: Dict[str, U2GameAssist] = {}
_game_assist_lock = threading.Lock()


class RoomActionService:
    def exec_hit_fish(self, room_id: int, is_aboard_version: bool = False, ranking:bool=False) -> bool:
        """
        执行打鱼任务
        :param room_id: 房间ID
        :return: 任务是否启动成功
        :raises RoomNotFoundException: 房间不存在
        :raises PermissionDeniedException: 无权限
        :raises PhoneNotFoundException: 云手机不存在
        :raises RoomException: 云手机连接失败
        """
        if not room_id:
            return False

        # 检查任务是否已运行
        if task_manager.jobs.get(room_id) is not None:
            logger.info(f"打鱼任务已在运行中: room_id={room_id}")
            return True

        # 校验房间和权限
        room_info = RoomsDao.get_by_id(room_id)
        if not room_info:
            logger.error(f"房间不存在: room_id={room_id}")
            raise RoomNotFoundException("房间不存在")

        if room_info.current_user != g.uid:
            raise PermissionDeniedException("没有权限操作该房间")

        # 获取云手机
        phone = self.get_phone_by_room(room_info)

        # 获取或创建游戏辅助实例
        game_assist = self.get_or_create_game_assist(phone.address)

        # 启动打鱼任务
        return self._start_hit_fish_task(game_assist, room_id, phone.id, is_aboard_version, ranking)

    def exec_hit_fish_dark(self, room_id: int, is_aboard_version: bool = False) -> bool:
        if not room_id:
            return False

        # 检查任务是否已运行
        if task_manager.jobs.get(room_id) is not None:
            logger.info(f"打鱼任务已在运行中: room_id={room_id}")
            return True

        # 校验房间和权限
        room_info = RoomsDao.get_by_id(room_id)
        if not room_info:
            logger.error(f"房间不存在: room_id={room_id}")
            raise RoomNotFoundException("房间不存在")

        if room_info.current_user != g.uid:
            raise PermissionDeniedException("没有权限操作该房间")

        # 获取云手机
        phone = self.get_phone_by_room(room_info)

        # 获取或创建游戏辅助实例
        game_assist = self.get_or_create_game_assist(phone.address)

        # 启动打鱼任务
        return self._start_hit_fish_task_dark(game_assist, room_id, phone.id, is_aboard_version)

    def get_phone_by_room(self, room_info):
        """根据房间信息获取关联的云手机"""
        phone = CloudPhonesDao.get_by_id(room_info.phone_id)
        if not phone:
            logger.error(f"云手机不存在: phone_id={room_info.phone_id}")
            raise PhoneNotFoundException("云手机不存在")
        return phone

    def is_hit_fish_thread_alive(self, room_id: int) -> bool:
        if not room_id:
            raise ParamInvalidException("参数不合法")
        return task_manager.is_fish_thread_alive(room_id)

    def specific_fish_solders(self, room_id: int, solder_name):
        if not room_id:
            raise RoomException("房间ID不能为空")
        if not solder_name:
            redis_cache.delete(f"fish:solders:{room_id}:{g.uid}")
            return
        if solder_name not in hit_fish.army_strs:
            raise RoomException("不能识别该流派")
        redis_cache.setex(f"fish:solders:{room_id}:{g.uid}", 24 * 60 * 60, solder_name)

    def _start_hit_fish_task(self, game_assist: U2GameAssist, room_id: int, phone_id: str, is_aboard_version: bool = False, ranking:bool=False) -> bool:
        """启动打鱼任务线程"""
        room_info = RoomsDao.get_by_id(room_id)
        if not room_info or not room_info.current_user:
            raise RoomException(f"房间 {room_id} 不存在，或者房间当前没有人，不能开展打鱼")
        if is_aboard_version and game_assist.get_game_region() != 'global':
            raise RoomException("当前没有打开国际服")
        elif not is_aboard_version and game_assist.get_game_region() != 'cn':
            raise RoomException("当前打开的不是部落冲突国服")
        if not contains_ui(game_assist.get_frame(), ui=attack_on_main):
            raise RoomException("当前不是村庄主界面")
        hit_fish = HitFish(game_assist, room_id=room_info.id, current_user_id=room_info.current_user, is_aboard_version=is_aboard_version, ranking=ranking)
        t = threading.Thread(target=hit_fish.execute, daemon=True)
        t.start()

        # 等待线程启动并验证状态
        time.sleep(1.5)

        # 注册任务到管理器
        task_struct = TaskStructure(
            thread=t,
            task_type="hit_fish",
            phone_id=phone_id,
            current_user_id=room_info.current_user,
            room_id=room_id,
            hit_fish=hit_fish
        )
        task_manager.add_task(task_struct)
        room = RoomsDao.get_by_id(room_id)
        if room:
            RoomLogDao.add_log(room_id=room.id, event_type="start_fish",
                               operator_id=g.uid if g.uid is not None else 0,
                               operator_name=g.uname if g.uname is not None else "system")
        return True

    def _start_hit_fish_task_dark(self, game_assist: U2GameAssist, room_id: int, phone_id: str, is_aboard_version: bool = False) -> bool:
        """启动打鱼任务线程"""
        room_info = RoomsDao.get_by_id(room_id)
        if not room_info or not room_info.current_user:
            raise RoomException(f"房间 {room_id} 不存在，或者房间当前没有人，不能开展打鱼")
        if is_aboard_version and game_assist.get_game_region() != 'global':
            raise RoomException("当前没有打开国际服")
        elif not is_aboard_version and game_assist.get_game_region() != 'cn':
            raise RoomException("当前打开的不是部落冲突国服")
        hit_fish_dark = HitFishDark(game_assist, room_id=room_info.id, current_user_id=room_info.current_user, is_aboard_version=is_aboard_version)
        t = threading.Thread(target=hit_fish_dark.loop_fish, daemon=True)
        t.start()
        logger.info(f"房间 {room_id} 用户 {room_info.current_user} 开启打鱼线程")
        # 等待线程启动并验证状态
        time.sleep(1.5)

        # 注册任务到管理器
        task_struct = TaskStructure(
            thread=t,
            task_type="hit_fish_dark",
            phone_id=phone_id,
            current_user_id=room_info.current_user,
            room_id=room_id,
            hit_fish=hit_fish_dark
        )
        task_manager.add_task(task_struct)
        room = RoomsDao.get_by_id(room_id)
        if room:
            RoomLogDao.add_log(room_id=room.id, event_type="start_fish",
                               operator_id=g.uid if g.uid is not None else 0,
                               operator_name=g.uname if g.uname is not None else "system")
        return True

    def get_task_status(self, room_id: int) -> bool:
        """获取打鱼任务运行状态"""
        if not room_id:
            return False

        room_info = RoomsDao.get_by_id(room_id)
        if not room_info:
            logger.error(f"房间不存在: room_id={room_id}")
            raise RoomNotFoundException("房间不存在")

        if room_info.current_user != g.uid:
            logger.info(f"用户 {g.uid} 已经不是当前房间 {room_id} 的使用者")
            return False

        return task_manager.is_fish_thread_alive(room_id)

    def stop_hit_fish(self, room_id: int) -> bool:
        """停止打鱼任务"""
        task = task_manager.jobs.get(room_id)
        if task and task.hit_fish:
            task.hit_fish.stop()
            room = RoomsDao.get_by_id(room_id)
            if room:
                RoomLogDao.add_log(room_id=room.id, event_type="stop_fish",
                                   operator_id=g.uid if g.uid is not None else 0, operator_name=g.uname if g.uname is not None else "system")
            logger.info(f"打鱼任务已停止: room_id={room_id}")
        return True

    def check_hit_fish_thread_alive(self, room_id: int) -> bool:
        """检查打鱼线程是否存活"""
        if not room_id:
            return False
        return task_manager.is_thread_alive(room_id)

    def build_formation(self, room_id: int, shell_url: str) -> bool:
        """
        设置部落冲突阵型（通过deep link）
        :param room_id: 房间ID
        :param shell_url: 阵型链接
        :raises RoomNotFoundException: 房间不存在
        :raises PermissionDeniedException: 无权限
        :raises RoomException: 操作冲突或云手机连接失败
        """
        if not room_id:
            return False

        # 校验房间和权限
        room_info = RoomsDao.get_by_id(room_id)
        if not room_info:
            logger.error(f"房间不存在: room_id={room_id}")
            raise RoomNotFoundException("房间不存在")

        if room_info.current_user != g.uid:
            raise PermissionDeniedException("没有权限操作该房间")

        # 检查是否有正在进行的任务
        if task_manager.jobs.get(room_id):
            raise RoomException("操作冲突，无法设置阵型")

        # 获取云手机
        phone = self.get_phone_by_room(room_info)

        # 获取游戏辅助实例
        game_assist = self.get_or_create_game_assist(phone.address)

        # 执行Deep Link跳转
        self._execute_deep_link(game_assist, shell_url, room_id)

        return True

    @classmethod
    def get_or_create_game_assist(cls, adb_addr: str, use_cache: bool = True) -> U2GameAssist:
        """从缓存获取或创建新的游戏辅助实例，链接超时抛出异常"""
        with _game_assist_lock:
            game_assist = room_game_assists.get(adb_addr)
            if game_assist:
                val = redis_cache.get(f"room:game_assist:{adb_addr}")
                if val and use_cache:
                    if game_assist.check_device_health():
                        logger.info("game_assist连接使用缓存")
                        return game_assist
                # 缓存失效，销毁旧连接
                game_assist.client_stop()
                time.sleep(0.2)
                logger.info("game_assist链接已经过期，重新建立")

            try:
                # 线程池超时替代gevent.Timeout，120秒限制初始化
                game_assist = run_with_timeout(U2GameAssist, 120, adb_link=adb_addr)
                room_game_assists[adb_addr] = game_assist
                logger.info(f"游戏辅助实例创建成功: adb={adb_addr}")
                redis_cache.set(f"room:game_assist:{adb_addr}", 1, ex=5 * 60 * 60)
                return game_assist

            except OperationTimeoutError:
                logger.error(f"游戏辅助链接超时: adb={adb_addr}")
                raise RoomException("云手机连接超时")
            except GameException as e:
                logger.error(f"游戏辅助实例创建失败: adb={adb_addr}, error={str(e)}")
                raise RoomException(f"云手机链接失败: {str(e)}")
            except Exception as e:
                logger.error(f"游戏辅助实例创建发生未知错误: adb={adb_addr}, error={str(e)}")
                logger.error(traceback.format_exc())
                raise RoomException(f"云手机连接异常: {str(e)}")

    def _execute_deep_link(self, game_assist: U2GameAssist, shell_url: str, room_id: int) -> None:
        """
        执行Deep Link跳转
        使用列表参数形式避免命令注入
        """
        parsed = urlparse(shell_url)
        deep_link = f"clashofclans://{parsed.query}"

        safe_command = [
            "am", "start",
            "-n", "com.tencent.tmgp.supercell.clashofclans/com.supercell.titan.tencent.GameAppTencent",
            "-a", "android.intent.action.VIEW",
            "-d", deep_link
        ]
        game_assist.device.shell(safe_command)
        logger.info(f"Deep Link已执行: room_id={room_id}")

    def refresh_scrcpy(self, room_id: int):
        if not room_id:
            raise RoomException("参数非法")
        room_info = RoomsDao.get_by_id(room_id)
        if not room_info:
            raise RoomException("房间不存在")
        val = redis_cache.get("room:refresh:{}".format(room_id))
        if val:
            raise RoomException("操作过于频繁")
        else:
            redis_cache.set("room:refresh:{}".format(room_id), 1, ex=3)

        phone_info = CloudPhonesDao.get_by_id(room_info.phone_id)
        logger.info(f"刷新云手机 {phone_info.address} 的远程链接")
        # 销毁旧实例
        old_conn = room_game_assists.pop(phone_info.address, None)
        if old_conn:
            old_conn.client_stop()
            time.sleep(0.2)
            logger.debug(f"清理原来云手机 {phone_info.address} 的链接")
        # 重新创建连接
        self.get_or_create_game_assist(phone_info.address)

    def get_url(self, name) -> str | None:
        website_link = WebsiteLinksDao.get_by_name(name)
        if website_link:
            return website_link.url
        return None


room_action_service = RoomActionService()
