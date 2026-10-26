# ===== 设置路径（必须用 sys.path.insert） =====
import os
import sys

src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_path = os.path.join(src_path, '../')

if src_path not in sys.path:
    sys.path.insert(0, src_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)
    print(root_path)
from utils import find_ui_center, find_uis_center
import math
import threading
import time
import traceback
from typing import Optional

import cv2
import numpy as np
import uiautomator2 as u2
from adbutils import adb, AdbError

from src.api.api_config import run_with_timeout, OperationTimeoutError
from src.api.exception.game_exception import GameException
from asserts import oil, coin, water, input_box, clan_msg, man, dark_man, continue_img, confirm, get_box_button, \
    confirm_resource, give_up_battle, end_war, close_ad, choose_reward, choose_reward_end
from src.config import config
from src.my_logger import logger

screen_lock = threading.RLock()


class U2GameAssist:
    def __init__(self, adb_link: str = config.ADB_LINK):
        try:
            # 1. ADB基础连接
            try:
                adb.connect(adb_link)
                logger.info(f"ADB 连接成功: {adb_link}")
            except Exception as e:
                raise GameException(f"ADB 连接失败 [{adb_link}]: {e}")

            # 2. 获取设备实例
            self.device = adb.device(adb_link)
            if self.device is None:
                raise GameException(f"无法获取设备对象，请确认设备已连接: {adb_link}")
            logger.info(f"获取设备对象成功: {adb_link}")

            # 3. 检测设备可用性
            if not self.check_device_health():
                logger.error(f"设备 shell 测试失败，adb_link: {adb_link}")
                raise GameException(f"设备 shell 测试失败")
            try:
                self.u2 = run_with_timeout(u2.connect, 20, self.device.serial)
                logger.info(f"uiautomator2 连接成功: {self.device.serial}")
            except OperationTimeoutError as e:
                logger.error(f"uiautomator2 连接超时 [{adb_link}]: {e}")
                raise GameException(f"uiautomator2 连接超时 [{adb_link}]")
            except Exception as e:
                logger.error(f"uiautomator2 连接失败 [{adb_link}]: {e}")
                raise GameException(f"uiautomator2 连接失败 [{adb_link}]")

            self.operate_lock = screen_lock
            self.adb_link = adb_link
            logger.info(f"云手机客户端初始化完成: {adb_link}")

        except GameException:
            raise
        except Exception as e:
            logger.error(f"ScrcpyGameAssist 初始化发生未知错误: {e}\n{traceback.format_exc()}")
            raise GameException(f"云手机初始化失败: {e}")

    def get_frame_adb(self) -> Optional[np.ndarray]:
        """
        使用 adbutils 截图，返回原始 BGR 格式图像
        不做任何压缩处理，由调用方自行决定如何处理
        :return: OpenCV BGR格式图像，失败返回None
        """
        try:
            # 使用已有的 device 对象截图
            pil_img = self.device.screenshot()

            # PIL(RGB) 转 OpenCV(BGR) 格式
            img_arr = np.array(pil_img)
            frame = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)

            return frame
        except Exception as e:
            logger.error(f"截图失败: {str(e)}")
            return None

    def check_device_health(self) -> bool:
        try:
            result = self.device.shell("echo 'ok'")
            if result.strip() == 'ok':
                logger.info("设备 shell 测试通过")
                return True
            return False
        except Exception as e:
            logger.error("设备检测异常", e)
            return False

    def get_frame(self) -> Optional[np.ndarray]:
        """
        截取手机画面，返回 OpenCV BGR 格式矩阵，异常返回None
        自带5s超时，防止adb僵死卡死协程、CPU满载
        """
        try:
            # 截取画面，得到PIL Image
            pil_img = self.u2.screenshot()
            # PIL(RGB) 转 OpenCV(BGR) 格式
            img_arr = np.array(pil_img)
            frame = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
            return frame

        except (AdbError, TimeoutError, ConnectionResetError, OSError) as e:
            logger.warning(f"截图失败，ADB通道异常: {str(e)}")
            # 触发连接销毁，后续执行重连逻辑
            return None
        except Exception as e:
            logger.error(f"截图未知异常: {str(e)}", exc_info=True)
            return None


    def human_swipe_with_u2(self, start_x, start_y, end_x, end_y):
        start_x, start_y = self._random_offset(start_x, start_y)
        end_x, end_y = self._random_offset(end_x, end_y)
        distance = math.hypot(end_x - start_x, end_y - start_y)
        duration = min(500, max(100, int(distance / 2.5))) / 1000
        self.u2.swipe(start_x, start_y, end_x, end_y, duration=duration)
        time.sleep(0.2)

    def get_clipboard_text(self) -> str:
        try:
            return self.device.shell("clipboard get").strip()
        except Exception as e:
            logger.error("获取剪切板失败:", e)
            return ""

    def click_button(self, x, y, max_offset=12):
        x, y = self._random_offset(x, y, max_offset=max_offset)
        with self.operate_lock:
            logger.info(f"点击({x},{y})")
            try:
                self.device.shell(f"input tap {x} {y}")
                return True
            except Exception as e:
                logger.error(f"ADB点击失败: {e}")
                return False

    def send_msg(self, txt: str):
        logger.info("开启发送消息功能")
        interrupt = True
        for i in range(4):
            x, y, accuracy = self.find_ui_center(self.get_frame(), clan_msg)
            if accuracy > 0.9:
                self.click_button(x, y)
            else:
                logger.warning(f"{i}、找不到‘部落消息’输入框")
            time.sleep(0.3)
            x, y, accuracy = self.find_ui_center(self.get_frame(), input_box)
            if accuracy > 0.9:
                interrupt = False
                logger.debug("找到输入框")
                break
            time.sleep(0.5)
        if interrupt:
            logger.error("发送消息失败：未调出输入框")
            return None

        with self.operate_lock:
            try:
                logger.info(f"发送文本：{txt}")
                self.u2.send_keys(txt, clear=False)
                self.u2.press("enter")
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
        time.sleep(0.5)

    def ramdom_click(self):
        center_x = config.CAP_PROP_FRAME_WIDTH // 2
        center_y = config.CAP_PROP_FRAME_HEIGHT // 2
        self.click_button(center_x, center_y, max_offset=30)

    def _random_offset(self, x: int, y: int, max_offset: int = 12):
        dx = int(np.random.normal(0, max_offset / 3))
        dy = int(np.random.normal(0, max_offset / 3))
        dx = max(-max_offset, min(dx, max_offset))
        dy = max(-max_offset, min(dy, max_offset))
        return x + dx, y + dy

    def long_touch_screen(self, x, y, max_offset=12, duration=0.5):
        x, y = self._random_offset(x, y, max_offset=max_offset)
        with self.operate_lock:
            logger.info(f"长按({x},{y})，时长{duration}秒")
            try:
                self.u2.long_click(x, y, duration=duration)
                return True
            except Exception as e:
                logger.error(f"u2长按失败: {e}")
                return False

    def get_current_activity(self, max_retries: int = 3, retry_delay: float = 0.5) -> Optional[str]:
        for attempt in range(max_retries):
            try:
                res = self.device.shell("dumpsys window | grep mCurrentFocus", timeout=5)
                if res and 'mCurrentFocus' in res:
                    import re
                    match = re.search(r'mCurrentFocus=Window\{[^}]*\s+([^\s/]+)/([^\s}]+)', res)
                    if match:
                        return f"{match.group(1)}/{match.group(2)}"
                res = self.device.shell("dumpsys activity activities | grep mResumedActivity", timeout=5)
                if res:
                    import re
                    match = re.search(r'mResumedActivity: ActivityRecord\{[^}]*\s+([^\s]+)\s+t', res)
                    if match:
                        return match.group(1)
                if attempt < max_retries -1:
                    time.sleep(retry_delay)
            except Exception as e:
                logger.warning(f"获取Activity失败 尝试{attempt+1}: {e}")
                time.sleep(retry_delay)
        return None

    def get_game_region(self, max_retries: int = 3) -> str:
        activity = self.get_current_activity(max_retries) or ""
        if "tencent" in activity.lower():
            return "cn"
        if "supercell" in activity.lower():
            return "global"
        return "cn"

    def zoom_out(self, repeat: int = 4, percent: int = 50, steps: int = 30):
        if not self.u2:
            raise GameException("uiautomator2 未连接，无法执行缩放")
        logger.info("执行画面缩小操作")
        screen = self.u2()
        for _ in range(repeat):
            screen.pinch_in(percent=percent, steps=steps)
            time.sleep(0.5)

    def find_ui_center(self, screen: cv2.Mat, ui: cv2.Mat) -> tuple[int, int, float]:
        if screen is None or ui is None:
            logger.error("画面/模板图片为空，无法匹配")
            return 0, 0, 0
        h, w = ui.shape[:2]
        res = cv2.matchTemplate(screen, ui, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        cx = max_loc[0] + w // 2
        cy = max_loc[1] + h // 2
        return cx, cy, round(max_val, 4)

    def client_stop(self):
        try:
            logger.info("释放adb链接")
            adb.disconnect(self.adb_link)
        except Exception:
            pass


class DaemonThread:
    def activate(self, game_assist):
        t = threading.Thread(target=self._execute, daemon=True, name="daemon_collect", args=(game_assist,))
        t.start()
        logger.info(f"资源收集守护线程 {t.native_id} 已启动".center(30, "="))

    def _execute(self, game_assist):
        cx = config.CAP_PROP_FRAME_WIDTH // 2
        cy = config.CAP_PROP_FRAME_HEIGHT // 2
        while True:
            locked = screen_lock.acquire(blocking=False)
            collected = False
            if locked:
                try:
                    frame = game_assist.get_frame()
                    if frame is None:
                        continue
                    # 依次收集黑油、金币、圣水
                    x, y, acc = self.find_ui_center(frame, oil)
                    if acc > 0.9:
                        game_assist.click_button(x, y)
                        logger.info("收取黑油")
                        collected = True
                    if not collected:
                        x, y, acc = self.find_ui_center(frame, coin)
                        if acc > 0.9:
                            game_assist.click_button(x, y)
                            logger.info("收取金币")
                            collected = True
                    if not collected:
                        x, y, acc = self.find_ui_center(frame, water)
                        if acc > 0.9:
                            game_assist.click_button(x, y)
                            logger.info("收取圣水")
                            collected = True
                    # 无资源可收集，点击屏幕任意处
                    if not collected:
                        game_assist.click_button(cx, cy, max_offset=30)
                finally:
                    screen_lock.release()
            # 随机间隔休眠
            sleep_t = self.get_lognormal_delay(mean_sec=45, min_sec=40, max_sec=50)
            time.sleep(sleep_t)

    def get_lognormal_delay(self, mean_sec: float = 0.5, min_sec: float = 0.1, max_sec: float = 2.0) -> float:
        mu = math.log(mean_sec) - 0.5
        sigma = 0.4
        delay = np.random.lognormal(mu, sigma)
        return float(max(min_sec, min(delay, max_sec)))

    def find_ui_center(self, screen: cv2.Mat, ui: cv2.Mat) -> tuple[int, int, float]:
        if screen is None or ui is None:
            return 0, 0, 0
        h, w = ui.shape[:2]
        res = cv2.matchTemplate(screen, ui, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        cx = max_loc[0] + w // 2
        cy = max_loc[1] + h // 2
        return cx, cy, round(max_val, 4)


if __name__ == "__main__":
    game_assist = U2GameAssist()
    img = game_assist.get_frame()
    # if img is not None:
    #     cv2.imwrite("../asserts/temp_img/bug0.png", img)
    # else:
    #     print("无法截取画面")
    # game_assist.client_stop()

    # img = cv2.imread("../asserts/temp_img/bug0.png")
    print(find_uis_center(img, uis = [continue_img]))
    game_assist.client_stop()