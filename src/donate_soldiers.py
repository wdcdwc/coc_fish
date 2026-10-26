"""
捐兵功能，待完善
"""
from typing import Any

from asserts import donate_button, del_donate_button, donate_pop_up_feature, donate_rect_right_top
from game_assist_uiautomator import screen_lock
from utils import *


class Donate:

    def check_donate_button(self, pic:MatLike) -> bool:
            if not contains_ui(pic, donate_button):
                # logger.info("界面不包含捐兵按钮，无法捐兵")
                return False

            if contains_ui(pic, del_donate_button):
                logger.info("包含删除捐兵按钮，是自己发的捐兵无需处理")
                return False
            logger.info("界面包含捐兵按钮并且没有删除按钮，执行捐兵")
            with screen_lock:

                self._execute_v3()
            logger.debug("退出捐兵流程")
            pic = None
            return True

    def _execute_v3(self):
        frame = game_assist.get_frame()
        x, y, accuracy = find_ui_center(frame, donate_button)
        if accuracy < 0.8:
            logger.error("无法获取捐兵图标的坐标位置")
            return False

        game_assist.click_button(x, y)
        donat_win_position = loop_find_ui(game_assist, ui=donate_pop_up_feature)
        if donat_win_position is None:
            logger.error("点击捐兵按钮之后没有弹出捐兵弹窗")
            return False
        for i in range(0, 20):
            frame = game_assist.get_frame()
            if not contains_ui(frame, donate_pop_up_feature, threshold=0.9):
                break
            list = self.get_soldier_card(frame)
            if list is not None and len(list) > 0:
                for x, y in list:
                    if not contains_ui(game_assist.get_frame(), donate_pop_up_feature, threshold=0.9):
                        break
                    game_assist.click_button(x, y)
                time.sleep(2)
            else:
                break

        if loop_find_ui(game_assist, ui=donate_pop_up_feature) is not None:
            # 捐工程机器
            logger.debug("滑动捐兵窗口")
            for i in range(0, 5):
                game_assist.human_swipe_with_u2(start_x=1079, start_y=292, end_x=581, end_y=306)
            for i in range(0, 3):
                frame = game_assist.get_frame()
                if not contains_ui(frame, donate_pop_up_feature, threshold=0.9):
                    break
                list = self.get_soldier_card(frame)
                if list is not None and len(list) > 0:
                    for x, y in list:
                        if not contains_ui(game_assist.get_frame(), donate_pop_up_feature, threshold=0.9):
                            break
                        game_assist.click_button(x, y)
                    time.sleep(2)
                else:
                    break
        # 恢复主界面
        x, y, accuracy = find_ui(game_assist.get_frame(), ui=donate_pop_up_feature)
        if accuracy > 0.9:
            logger.debug("恢复主界面")
            game_assist.click_button(x=420, y=360)


    def get_soldier_card(self, img: MatLike) -> list[Any] | None:
        logger.debug("获取捐兵卡片视图锚点")
        base_img = img.copy()
        #找到捐兵弹窗的左上角
        x, y = loop_find_ui_xy(base_img, donate_pop_up_feature)
        #左上角的左边和上面全部涂黑
        img[0:y, :] = (0, 0, 0)
        img[:, 0:x] = (0, 0, 0)
        #找到捐兵弹窗的右上角
        x, y, _ = find_ui(img, donate_rect_right_top)
        x += round(donate_rect_right_top.shape[1] / 2)
        #右上角的右边全部涂黑
        img[:, x:img.shape[1]] = (0, 0, 0)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)  # 饱和度通道（0~255）
        _, binary = cv2.threshold(s, thresh=50, maxval=255, type=cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(image=binary, mode=cv2.RETR_TREE, method=cv2.CHAIN_APPROX_SIMPLE)
        res = []
        # cv2.drawContours(image=base_img, contours=contours, contourIdx=-1, color=(255, 0, 0), thickness=3)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if 84 -10 <= w <= 84 + 10 and 110 - 10 <= h <= 110 + 10:
                cv2.rectangle(base_img, (x, y), (x + w, y + h), (255, 255, 255), 2)
                res.append((x + w / 2, y + h / 2))
        return res



donate_task = Donate()

if __name__ == "__main__":
    img = cv2.imread("../asserts/temp_img/bug_hate_spell.png")
    donate_task.get_soldier_card(img)
    game_assist.client_stop()



