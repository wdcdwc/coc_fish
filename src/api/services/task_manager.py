import threading
import time

from dataclasses import dataclass

from hit_fish_dark import HitFishDark
from src.redis_client import redis_cache
from src.hit_fish import HitFish
from src.my_logger import logger

@dataclass
class TaskStructure:
    thread: threading.Thread
    task_type: str
    phone_id: str
    room_id: int
    current_user_id: int
    hit_fish: HitFish | HitFishDark


class TaskManager:
    def __init__(self):
        self.jobs: dict[int, TaskStructure] = {}
        self._lock = threading.RLock()
        self._update_interval = 2.0
        self._max_interval = 15

    def start(self):
        threading.Thread(target=self._exec, name="后台算法管理线程").start()
        logger.info("后台算法管理线程启动")

    def _refresh_alive_thread(self):
        # logger.info("刷新算法线程的存活状态")
        dead_room_rid = []
        if len(self.jobs.items()) == 0:
            return False
        # 遍历标记存活与死亡房间
        from api.services.room_service import RoomService
        with self._lock:
            for rid, task in self.jobs.items():
                if task.thread.is_alive():
                    RoomService.send_room_msg(task.room_id, task.current_user_id, type="fish_keepalive", msg="1")
                    # 即使更新redis中房间的活跃状态
                    redis_cache.set(f"room:alive:{rid}", 1, ex= 5 * 60)
                else:
                    RoomService.send_room_msg(task.room_id, task.current_user_id, type="fish_keepalive", msg="0")
                    dead_room_rid.append(rid)

        # 批量移除死亡任务
        if len(dead_room_rid) > 0:
            with self._lock:
                for rid in dead_room_rid:
                    logger.info(f"房间 {rid} 任务线程已终止，自动移除任务")
                    del self.jobs[rid]
        return True

    def is_fish_thread_alive(self, room_id: int) -> bool:
        job = self.jobs.get(room_id)
        if job is not None:
            if not job.thread.is_alive():
                # 线程已死亡，删除 job
                del self.jobs[room_id]
                return False
            return True
        return False

    def _exec(self):
        self.loop_interval = self._update_interval
        while True:
            self._refresh_alive_thread()
            if self.jobs.__len__() == 0 and self.loop_interval < self._max_interval:
                self.loop_interval += 1
            else:
                self.loop_interval = self._update_interval
            time.sleep(self.loop_interval)


    def add_task(self, task: TaskStructure):
        with self._lock:
            self.jobs[task.room_id] = task
            self.loop_interval = self._update_interval

    def remove_task(self, room_id: int):
        with self._lock:
            self.jobs.pop(room_id, None)


task_manager = TaskManager()
task_manager.start()
