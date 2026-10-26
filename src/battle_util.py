from typing import Callable

from cv2.typing import MatLike

from asserts import big_guard, angel, stove, man, queen, run_tu, toothpick_soldier, small_guard, dragon, valkyrie, \
    fly_king, fat, archer, dragon_king, e_dragon, machine
from utils import loop_find_ui, human_gauss_click_position, human_like_press_duration, find_ui_center


class BattleUtil:
    left = (90, 318, 125, 330)
    right = (1108, 297, 1157, 340)
    from hit_fish import HitFishLogger
    def __init__(self, game_assist, my_logger:HitFishLogger, sleep_fuc:Callable):
        self.game_assist = game_assist
        self.my_logger = my_logger
        self.sleep_fuc = sleep_fuc
        pass

    def tooth_flow(self):
        has_guard = self.put_solders(solder_card=big_guard, iterator=8, delay=1, solder_name="大守护者")
        if not has_guard:
            self.put_car()
            self.put_solders(solder_card=toothpick_soldier, place=self.left, solder_name="牙签", duration=5)
            self.put_solders(solder_card=angel, place=self.left, solder_name="天使")
            self.put_solders(solder_card=stove,place=self.left, solder_name="火炉子")
            self.put_solders(solder_card=small_guard, place=self.left, solder_name="小守护者")

            self.put_solders(solder_card=man, place=self.right, solder_name="蛮王")
            self.put_solders(solder_card=run_tu, place=self.right, solder_name="润土",
                             double_clisk=True)
            self.put_solders(solder_card=queen, place=self.right, solder_name="女皇",
                                    double_clisk=True)
        else:
            self.put_solders(solder_card=angel, solder_name="天使")
            self.put_solders(solder_card=stove, solder_name="火炉子")
            self.put_solders(solder_card=man, place=self.right, solder_name="蛮王")
            if has_guard:
                self.put_solders(solder_card=queen, place=self.right, solder_name="女皇",
                                        double_clisk=True)
            self.put_solders(solder_card=run_tu, place=self.right, solder_name="润土",
                                            double_clisk=True),
            self.put_car()
            self.put_solders(solder_card=toothpick_soldier, solder_name="牙签", duration=5)
            self.put_solders(solder_card=small_guard, solder_name="小守护者")

    def dragon_flow(self):
        self.put_solders(solder_card=dragon, place=self.left, solder_name="火龙",duration=7)
        self.put_car()
        self.put_solders(solder_card=fly_king, place=self.left, solder_name="苍蝇王子")
        self.put_solders(solder_card=big_guard, place=self.left, solder_name="大守护者")
        self.put_solders(solder_card=queen, place=self.left, solder_name="女皇",
                                double_clisk=True)
        self.put_solders(solder_card=dragon_king, place=self.right, solder_name="龙王")

    def e_dragon_flow(self):#缺少真正的电龙ui
        self.put_solders(solder_card=e_dragon, place=self.left, solder_name="电龙", duration=7)
        self.put_solders(solder_card=big_guard, place=self.left, solder_name="大守护者")
        self.put_solders(solder_card=fly_king, place=self.left, solder_name="苍蝇王子")
        self.put_solders(solder_card=dragon_king, place=self.right, solder_name="龙王")
        self.put_solders(solder_card=man, place=self.right, solder_name="蛮王")

    def valkyrie_flow(self):
        self.put_solders(solder_card=valkyrie, place=self.left, solder_name="女武神", duration=10)
        self.put_solders(solder_card=big_guard, place=self.left, solder_name="大守护者")
        self.put_solders(solder_card=run_tu, place=self.left, solder_name="润土", double_clisk=True)
        self.put_solders(solder_card=queen, place=self.right, solder_name="女皇",
                                double_clisk=True)
        self.put_solders(solder_card=man, place=self.right, solder_name="蛮王")

    def man_flow(self):
        self.put_solders(solder_card=fat, place=self.left, solder_name="胖子", duration=10)
        self.put_solders(solder_card=queen, place=self.left, solder_name="女皇",
                         double_clisk=True)
        self.put_solders(solder_card=big_guard, place=self.left, solder_name="大守护者")
        self.put_solders(solder_card=fly_king, place=self.left, solder_name="苍蝇王", double_clisk=True)
        self.put_solders(solder_card=archer, place=self.left, solder_name="弓箭手",duration=10)
        self.put_solders(solder_card=man, place=self.right, solder_name="蛮王")

    def put_solders(self,solder_card:MatLike, solder_name:str,iterator=3, delay=1,
                    place:tuple=left, double_clisk=False, duration=2.0) -> bool:
        x, y, accuracy = find_ui_center(self.game_assist.get_frame(), ui=solder_card)
        if accuracy > 0.9:
            self.game_assist.click_button(x, y)
            if solder_name is not None:
                self.my_logger.info(f"下{solder_name}")
            drop_x, drop_y = human_gauss_click_position(*place)
            self.game_assist.long_touch_screen(x=drop_x, y=drop_y, duration=human_like_press_duration(duration))
            self.sleep_fuc(human_like_press_duration(1.2))
            if double_clisk:
                self.my_logger.info("双击")
                self.game_assist.click_button(x, y)
            return True
        else:
            if solder_name is not None:
                self.my_logger.info(f"找不到{solder_name}")
                return False

    def put_car(self, place:tuple=left) -> bool:
        x, y, accuracy = find_ui_center(self.game_assist.get_frame(), ui=machine)
        if accuracy < 0.8:
            return False
        self.my_logger.info("下工程机器")
        self.game_assist.click_button(x, y - 40)
        drop_x, drop_y = human_gauss_click_position(*place)
        self.game_assist.long_touch_screen(x=drop_x, y=drop_y, duration=human_like_press_duration(2.0))
        self.sleep_fuc(human_like_press_duration(1.2))
        return True



