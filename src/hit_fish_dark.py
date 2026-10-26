import threading
import time
from typing import Any

import cv2

from api.exception.game_exception import BattleInterruptError
from asserts import main_page_d, search_now, switch_solders, arch, go_back, dark_man, confirm, x1, attack_on_main, \
    open_setting_red, open_setting, setting_red, setting, logout, qr_code, open_id, id_setting, logout_panel, logout_d, \
    remember_me, logout_final
from game_assist_uiautomator import U2GameAssist
from hit_fish import HitFishLogger
from src.redis_client import redis_cache
from utils import contains_ui, find_ui_center, loop_find_ui, click_if_exist


class HitFishDark:
    def __init__(self, game_assist:U2GameAssist, is_aboard_version:bool, room_id, current_user_id):
        self.game_assist = game_assist
        self.logger = HitFishLogger(room_id, current_user_id)
        self.evt = threading.Event()
        self.is_aboard_version = is_aboard_version
        self.room_id = room_id
        self.current_user_id = current_user_id
        pass

    def sleep(self, duration: float):
        # 原生threading.Event.wait，完美兼容终止逻辑，无需修改
        self.evt.wait(duration)
        if self.evt.is_set():
            self.logger.info("检测到停止打鱼任务终止")
            raise BattleInterruptError("外部触发停止")

    def loop_fish(self):
        loop_time = 60
        frame = self.game_assist.get_frame()
        x, y, accuracy = find_ui_center(screen=frame, ui=main_page_d)
        if accuracy < 0.9:
            self.logger.error(f"当前不是夜世界主界面")
            return
        for i in range(0, loop_time):
            res = self._execute()
            if not res:
                self.logger.error("打鱼终止")
                break
            else:
                self.logger.info("返回打鱼成功信息")

            tag = redis_cache.get(f"fish:logout:{self.room_id}:{self.current_user_id}")
            if tag:
                self.logger.info("检测到打鱼时长即将耗尽，推出打鱼循环")
                break
        self.logger.info("1.5分钟之后执行退出游戏帐号")
        self.sleep(90)
        HitFishDark.logout(self.is_aboard_version, game_assist=self.game_assist, fish_logger=self.logger)

    def _execute(self) -> bool:
        for i in range(0, 3):
            frame = self.game_assist.get_frame()
            x, y, accuracy = find_ui_center(screen=frame, ui=main_page_d)
            if accuracy < 0.9:
                self.logger.error(f"{i}、当前不是夜世界主界面")
            else:
                self.game_assist.click_button(x, y)
                self.logger.info("点击进攻按钮")
                self.sleep(1)
                frame = self.game_assist.get_frame()

            x, y, accuracy = find_ui_center(screen=frame, ui=search_now)
            if accuracy < 0.9:
                self.logger.error(f"{i}、当前不是夜世界立即寻找界面")
                x, y, accuracy = find_ui_center(screen=frame, ui=confirm)
                if accuracy > 0.9:
                    self.logger.info("点击确认胜利之星资源")
                    self.sleep(1)
                    frame = self.game_assist.get_frame()
            else:
                self.game_assist.click_button(x, y)
                self.logger.info("点击立即寻找按钮")
                self.sleep(7)
                frame = self.game_assist.get_frame()

            x, y, accuracy = find_ui_center(screen=frame, ui=switch_solders)
            if accuracy < 0.9:
                self.logger.error(f"{i}、当前不是夜世界进攻界面")
            else:
                self.logger.info("开始打鱼")
                break

            self.sleep(2)

        frame = self.game_assist.get_frame()
        x, y, accuracy = find_ui_center(screen=frame, ui=switch_solders)
        if accuracy < 0.9:
            self.logger.error(f"{i}、当前不是夜世界进攻界面")
            return False

        self.game_assist.zoom_out(repeat=2) #(329, 509)

        # 下兵种
        self._put_solders_in_order(frame)

        begin_time = time.time()
        while time.time() - begin_time < 3 * 60 * 2:
            self.sleep(2)
            frame = self.game_assist.get_frame()
            if int(time.time()) % 5 == 0:
                self.logger.info("程序执行中..")
            if contains_ui(frame, switch_solders):
                self.logger.info("开始打夜市界的第二个部落")
                self.sleep(10)
                self.game_assist.zoom_out(repeat=2)
                self._put_solders_in_order(frame)
            else:
                x, y, accuracy = find_ui_center(frame, go_back)
                if accuracy > 0.9:
                    self.logger.info("点击回营")
                    self.game_assist.click_button(x, y)
                    break
                x, y, accuracy = find_ui_center(frame, x1)
                if accuracy > 0.9:
                    self.logger.info("点击倍速")
                    self.game_assist.click_button(x, y)

        self.sleep(1)
        if click_if_exist(game_assist=self.game_assist, ui=confirm):
            self.logger.info("点击确认胜利之星资源")
        return loop_find_ui(game_assist=self.game_assist, ui=main_page_d) is not None

    def _put_solders_in_order(self, frame:cv2.Mat):
        solder_list = self._getSoldersPointer(frame)
        if not solder_list or len(solder_list) == 0:
            self.logger.error("找不到兵种")
            return False

        self.logger.info("开始下兵")
        multi_solders = [arch, dark_man]
        # cv2.imwrite("./frame.png", frame)
        for i, img in enumerate(multi_solders):
            x, y, accuracy = find_ui_center(frame, img, gray=False)
            if accuracy < 0.9:
                print(f"识别不到多兵种 {i}, accuracy = {accuracy}")
            else:
                print(f"识别到多兵种 {i}, accuracy = {accuracy}")
                self._put_solders(x, y - 20, multi=True)
        print(f"识别到兵种单位数量:{len(solder_list)}")
        for i, pointer in enumerate(solder_list):
            self._put_solders(*pointer)
            if i == 0:
                self.logger.info("下战争机器")

    def _put_solders(self, x, y, multi:bool=False):
        self.game_assist.click_button(x, y)
        self.sleep(0.5)
        if not multi:
            self.game_assist.click_button(156, 367)
        else:
            self.game_assist.long_touch_screen(156, 367, duration=5)

    def _getSoldersPointer(self, img: cv2.Mat) -> list[Any]:
        cropped_img = img[585:, :]
        hsv = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        _, binary = cv2.threshold(v, thresh=150, maxval=255, type=cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(image=binary, mode=cv2.RETR_TREE, method=cv2.CHAIN_APPROX_SIMPLE)
        res = []

        # 定义偏移量（裁剪时去掉的上方像素数）
        OFFSET_Y = 585

        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if 85 <= w <= 120 and h > 30:
                cx, cy = x + w / 2, y + h / 2
                cx_original, cy_original = x + w / 2, y + OFFSET_Y + h / 2

                res.append((cx_original, cy_original - 30))  # -30是为了避开切换兵种按钮

                # 如果需要画在原始图像上，也要调整
                # img_copy = img.copy()
                # cv2.circle(img_copy, (int(cx_original), int(cy_original)), 6, (255, 255, 255), thickness=-1)
                # cv2.rectangle(img_copy, (x, y), (x + w, y + h), (255, 255, 255), 2)
        # cv2.imwrite("./bug.png", img_copy)
        # img_show_origin(img_copy)
        res.sort(key=lambda p: p[0])
        return res

    def stop(self):
        self.logger.info("终止打鱼任务")
        self.evt.set()

    @classmethod
    def logout(cls, is_aboard_version:bool, game_assist:U2GameAssist, fish_logger:HitFishLogger):
        fish_logger.info("开始执行退出帐号")
        if not is_aboard_version:
            for i in range(0, 4):
                if not contains_ui(screen=game_assist.get_frame(), ui=attack_on_main):
                    fish_logger.info(f"{i}、当前不是主界面")
                threading.Event.wait(1)
                if not (click_if_exist(game_assist=game_assist, ui=open_setting_red)
                        or click_if_exist(game_assist=game_assist,ui=open_setting)):
                    fish_logger.info(f"{i}、找不到设置弹出框")
                else:
                    fish_logger.info(f"点击设置弹出框")
                threading.Event.wait(1)
                if not (click_if_exist(game_assist=game_assist, ui=setting_red)
                        or click_if_exist(game_assist=game_assist, ui=setting)):
                    fish_logger.info(f"{i}、找不到设置按钮")
                else:
                    fish_logger.info(f"打开设置")
                threading.Event.wait(1)
                if not click_if_exist(game_assist=game_assist, ui=logout):
                    fish_logger.info(f"{i}、找不到退出登录按钮")
                else:
                    fish_logger.info(f"退出登录")
                threading.Event.wait(1)
                frame = game_assist.get_frame()
                if contains_ui(screen=frame, ui=qr_code):
                    fish_logger.info("退出登录程序执行完毕")
                    return
                elif (frame[200, 200] <= 70).all():
                        fish_logger.info("正在过度回到登录界面")
                        return
                threading.Event.wait(2)
        else:
            # 国际服退出登录
            for i in range(0, 3):
                if not contains_ui(screen=game_assist.get_frame(), ui=attack_on_main):
                    fish_logger.info(f"{i}、当前不是主界面")
                threading.Event.wait(1)
                if not (click_if_exist(game_assist=game_assist, ui=setting_red)
                        or click_if_exist(game_assist=game_assist, ui=setting)):
                    fish_logger.info(f"{i}、找不到设置按钮")
                else:
                    fish_logger.info(f"打开设置")
                threading.Event.wait(1)

                if not click_if_exist(game_assist=game_assist, ui=open_id):
                    fish_logger.info(f"{i}、找不到蓝色打开设置按钮")
                threading.Event.wait(1)

                if contains_ui(screen=game_assist.get_frame(), ui=id_setting):
                    if contains_ui(screen=game_assist.get_frame(), ui=logout_panel):
                        game_assist.human_swipe_with_u2( 762, 568, 688, 226)
                        time.sleep(1)
                        if click_if_exist(game_assist=game_assist, ui=logout_d):
                            fish_logger.info("点击退出登录")
                            time.sleep(1)
                        else:
                            fish_logger.info("找不到退出登录黑色按钮")
                            return
                        if not click_if_exist(game_assist=game_assist, ui=remember_me):
                            fish_logger.info("没有弹出确定登出界面")
                            return
                        else:
                            fish_logger.info("点击取消‘记住我’")
                        threading.Event.wait(0.5)
                        if not click_if_exist(game_assist=game_assist, ui=logout_final):
                            fish_logger.info("找不到最终确认登出蓝色按钮")
                        else:
                            fish_logger.info("点击确认登出蓝色按钮")
                            return

                    else:
                        click_if_exist(game_assist=game_assist, ui=id_setting)
                else:
                    fish_logger.info(f"{i}、没有弹出个人ID界面设置面板")

if __name__ == '__main__':
    game_assist = U2GameAssist()
    fish_logger = HitFishLogger(room_id=8, current_user_id=9)
    hit_fish = HitFishDark(game_assist, fish_logger)
    hit_fish.loop_fish()




