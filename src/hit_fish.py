import datetime
import os
import sys
import threading
from game_assist_uiautomator import U2GameAssist
from src.redis_client import redis_cache

src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_path = os.path.join(src_path, '../')
if src_path not in sys.path:
    print(src_path)
    sys.path.insert(0, src_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)
    print(root_path)

from api.exception.game_exception import BattleInterruptError, GameAssistNotFoundException
from asserts import attack_on_main, search_fish, attack_on_panel, end_war_button, confirm_resource, \
    give_up_battle, confirm_give_up_battle, end_war, confirm, allocation_panel, save_army, \
    import_use, ignore_confirm, close_allocation_panel, activity_solders_list, tooth_import, dragon_import, \
    e_dragon_import, \
    valkyrie_import, off_line, get_box_button, hammer, continue_img, speed, fat_import, open_setting_red, setting_red, \
    logout, qr_code, open_setting, setting, id_setting, logout_panel, logout_d, open_id, remember_me, logout_final, \
    rank_confirm_attack, sign_up, jian, reporting, rank_finish, close_ad, auto_fight, choose_reward, choose_reward_end
from config import config
from utils import *


class HitFishLogger:
    def __init__(self, room_id, current_user_id):
        self.room_id = room_id
        self.current_user_id = current_user_id
        # 最近一条日志是否成功推送到前端SSE（True=前端在线看得到日志）
        self.last_deliver_res = False

    def _send(self, level, msg):
        from api.services.room_service import RoomService
        full_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level.upper()}] {msg}"

        # logger.debug(f"打鱼线程发送日志：room_id:{self.room_id}, user_id:{self.current_user_id}, msg:{full_msg}")
        send_res = RoomService.send_room_msg(self.room_id, self.current_user_id, type="log", msg=full_msg)
        self.last_deliver_res = bool(send_res)
        # logger.debug("send_res=" + str(send_res))

        if level == "info":
            logger.info(f"房间 {self.room_id} 的用户 {self.current_user_id} - 发送结果 {str(send_res)} - " + full_msg)
        elif level == "error":
            logger.error(f"房间 {self.room_id} 的用户 {self.current_user_id} - 发送结果 {str(send_res)} - " + full_msg)
        elif level == "debug":
            logger.debug(f"房间 {self.room_id} 的用户 {self.current_user_id} - 发送结果 {str(send_res)} - " + full_msg)


    def info(self, str):
        self._send("info", str)

    def error(self, str):
        self._send("error", str)

    def debug(self, str):
        self._send("debug", str)


army_strs = {
    "铅笔天使": "h4p4e40_13-1p9e17_20-2p16e4_24-0p10e32_14i4x84-3x10-1x135-1x1-1x87d1x9-1x53-1x5u12x132-2x150-5x7-1x97-4x4-4x1-2x5-3x10-1x135-1x75-1x92s2x120-1x70-1x3-5x35",
    "龙流": "h1p9e20_17-2m1p16e4_34-6p4e49_43-7p11e52_53i4x84-1x10-1x5-1x52-1x62d1x9-1x5-1x98u17x8-1x75-1x91-1x87s1x70-5x120-2x10-1x2",
    # "电龙流": "h0p7e32_14-2m1p16e4_34-6p4e49_43-7p11e52_53i4x84-1x10-1x5-1x52-1x62d1x9-1x5-1x98u11x59-2x5-1x75-1x91-1x87s1x70-5x120-2x10-1x2",
    "武神流": "h4p4e40_13-1p3e15_20-2p16e4_24-0p7e8_14u42x12-2x10",
    "胖子弓箭手流": "h0p0e32_14-1p3e17_20-6p2e42_43-2p1e4_24u55x3-53x1-2x75-1x51s3x2-4x0"
}


class HitFish:
    def __init__(self, game_assist: U2GameAssist, room_id, current_user_id, is_aboard_version: bool = False, ranking: bool = False):
        self.box_mode = False
        self.strategy = None
        if game_assist is None:
            raise GameAssistNotFoundException("self.game_assist 初始化失败")
        self.game_assist = game_assist
        self.room_id = room_id
        self.current_user_id = current_user_id
        # 原生threading.Event，完全无需修改，唤醒机制正常
        self.evt = threading.Event()
        self.logger = HitFishLogger(room_id, self.current_user_id)
        from battle_util import BattleUtil
        self.battle_util = BattleUtil(game_assist, self.logger, self.sleep)
        self.is_aboard_version = is_aboard_version
        self.ranking = ranking
        self.army_attack = {
            "铅笔天使": lambda: self.battle_util.tooth_flow(),
            "电龙流": lambda: self.battle_util.e_dragon_flow(),
            "龙流": lambda: self.battle_util.dragon_flow(),
            "武神流": lambda: self.battle_util.valkyrie_flow(),
            "胖子弓箭手流": lambda: self.battle_util.man_flow(),
        }
        self.army_icons = {
            "铅笔天使": tooth_import,
            "龙流": dragon_import,
            "电龙流": e_dragon_import,
            "武神流": valkyrie_import,
            "胖子弓箭手流": fat_import
        }

    def _notify_fish_fail(self, reason: str):
        """
        打鱼失败邮件告警：
        1. 外部API主动触发停止（evt被置位）不发
        2. 前端SSE在线（失败日志已成功推送给用户）不发
        3. 邮件侧同一房间同一用户1分钟幂等
        注意：调用前需先 self.logger.error/info(...) 推送失败日志，last_deliver_res 才对应当前这条
        """
        try:
            if self.evt.is_set():
                self.logger.info("外部主动停止打鱼任务，不发送失败告警邮件")
                return
            if getattr(self.logger, "last_deliver_res", False):
                self.logger.info("前端用户在线可查看日志，不发送失败告警邮件")
                return
            from api.services.email_sender import mail_client
            img = None
            try:
                img = self.game_assist.get_frame()
            except Exception as e:
                logger.error(f"打鱼失败告警截图获取失败: {e}")
            mail_client.notify_fish_failed(
                user_id=self.current_user_id,
                img=img,
                room_id=self.room_id,
                fail_reason=reason
            )
        except Exception as e:
            logger.error(f"打鱼失败告警异常: {e}")

    def execute(self) -> bool:
        record_time = time.time()
        x, y, accuracy = find_ui(screen=self.game_assist.get_frame(), ui=attack_on_main)
        if accuracy < 0.8:
            self.logger.error(f"当前不是主界面 {accuracy}")
            self._notify_fish_fail(f"启动打鱼时不在村庄主界面（进攻按钮匹配度{accuracy:.2f}）")
            return False

        max_hit_fish_times = 70

        # 打鱼大循环
        while True:

            max_hit_fish_times -= 1
            if max_hit_fish_times <= 0:
                self.logger.info("达到单次打鱼次数的上限，直接退出")
                self.logout()
                break

            if not self._execute_flow():
                self.logger.info("打鱼失败，直接退出")
                break

            # 检查是否应该下线帐号
            tag = redis_cache.get(f"fish:logout:{self.room_id}:{self.current_user_id}")
            if tag:
                self.logger.info("检测到打鱼时长即将耗尽，执行登出代码")
                self.logout()
                break

            if self.check_resource_full():
                stop_auto_logout = redis_cache.get(name=f"stop:autoLogout:{self.current_user_id}")
                if not stop_auto_logout:
                    self.logger.info("资源已经满了，1.5分钟后执行退出登录操作")
                    self.sleep(90)
                    # 发送通知邮箱
                    from api.services.email_sender import mail_client
                    mail_client.notify_resource_full(self.current_user_id, self.game_assist.get_frame(), self.room_id)
                    self.logout()
                    redis_cache.setex(name=f"hit_fish:finish:{self.room_id}:{self.current_user_id}", time=5 * 60, value=1)
                break
            else:
                self.logger.info("资源没满")

        self.logger.info(f"打鱼花费时间:{int(time.time() - record_time)}")
        return True

    def check_resource_full(self) -> bool:
        flag = False
        for i in range(0, 3):
            if loop_find_ui(game_assist=self.game_assist, ui=attack_on_main, iterator=15,
                            delay=2) is None:
                self.logger.error("当前不是主界面")
                if not click_if_exist(self.game_assist, ui=confirm):
                    self.game_assist.click_button(200, 200)
            else:
                flag = True
                break
        if not flag:
            return False
        frame = self.game_assist.get_frame()
        # frame = cv2.imread("../asserts/temp_img/bug.png")
        if not self.is_aboard_version:
            b, g, r = frame[53, 1017]
        else:
            b, g, r = frame[52, 1023]
        logger.info("金币：b={},g={},r={}".format(b, g, r))
        is_coin_full = r > 200 and g > 170 and b < 50
        if is_coin_full:
            self.logger.info("金币满了")
        if not self.is_aboard_version:
            b, g, r = frame[102, 1017]
        else:
            b, g, r = frame[119, 1023]
        logger.info("圣水：b={},g={},r={}".format(b, g, r))
        is_water_full = r > 150 and b > 150
        if is_water_full:
            self.logger.info("圣水满了")
        if not self.is_aboard_version:
            b, g, r = frame[156, 1084]
        else:
            b, g, r = frame[186, 1090]
        logger.info("黑油：b={},g={},r={}".format(b, g, r))
        is_oil_full = b < 60 and g < 22 and r < 45
        if is_oil_full:
            self.logger.info("黑油满了")

        return is_oil_full and is_coin_full and is_water_full

    def _execute_flow(self) -> bool:

        if not config.DIY_STRATEGY and self.strategy is None:
            self.strategy = self.solders_allocation()
        if self.strategy is None:
            self.logger.error("无法选择合适的流派")
            self._notify_fish_fail("自动配兵失败，无法选择合适的兵种流派")
            return False

        i = 0
        max_try_enter_war = 6
        # 进入打鱼循环过程
        while i < max_try_enter_war:
            self.logger.info("排位赛" if self.ranking else "匹配赛" + "模式")
            frame = self.game_assist.get_frame()
            res = find_uis_center(frame, uis=[confirm, close_allocation_panel, reporting, close_ad])
            if res:
                x, y = res
                self.game_assist.click_button(x, y)
                self.sleep(1)
                frame = self.game_assist.get_frame()

            x, y, accuracy = find_ui_center(frame, ui=attack_on_main)
            if accuracy > 0.9:
                self.logger.info("点击进入进攻面板")
                self.game_assist.click_button(x, y)
                self.sleep(1)
                frame = self.game_assist.get_frame()
            else:
                self.logger.info(f"{i}、当前不是主界面，找不到地图进攻按钮")

            if i == 4 and self.ranking:
                self.logger.error("始终无法进入排位赛，降级为匹配赛打鱼")
                self.ranking = False
                i = 0

            if self.ranking:
                res = find_uis_center(frame, uis=[sign_up, rank_finish])
                if res:
                    self.logger.error("排位没有报名或者刀数已经达到上线，降级为匹配赛打鱼")
                    self.ranking = False

            h, w, c = frame.shape
            if not self.ranking:
                # 把排位站部分切除掉
                frame = frame[0:h, 0:int(w / 3)]
            else:
                # 把匹配赛部分涂黑
                frame[0:h, 0:int(w / 3)] = 0

            center_x, center_y, accuracy = find_ui_center(screen=frame, ui=search_fish)
            if accuracy > 0.9:
                self.logger.info("点击搜索对手")
                self.game_assist.click_button(center_x, center_y)
                self.sleep(1)
                frame = self.game_assist.get_frame()
            else:
                self.logger.info(f"{i}、找不到常规战面板")

            x, y, accuracy = find_ui_center(frame, ui=attack_on_panel)
            if accuracy < 0.9:
                self.logger.info(f"{i}、找不到配兵界面")
            else:
                self.logger.info("点击发起进攻")
                self.game_assist.click_button(x, y)
                self.sleep(1)
                frame = self.game_assist.get_frame()


            if self.ranking:
                x, y, accuracy = find_ui_center(frame, ui=rank_confirm_attack)
                if accuracy < 0.9:
                    self.logger.info(f"{i}、找不到确认进攻界面")
                else:
                    self.logger.info("点击确认进攻")
                    self.game_assist.click_button(x, y)
                    self.sleep(1)
                    frame = self.game_assist.get_frame()

            b, g, r = frame[180, 257]
            if (b > 240 and g > 240 and r > 240) or contains_ui(frame, end_war_button):
                self.logger.info("结束备战")
                break
            i += 1
            self.sleep(1)

        result = loop_find_uis(game_assist=self.game_assist, uis=[end_war_button, give_up_battle], iterator=24, delay=3)
        if result is None:
            self.logger.error("搜不到对手，打鱼失败")
            self._notify_fish_fail("多次尝试后仍搜不到对手（找不到结束战斗/放弃战斗按钮图标）")
            return False

        self.logger.info("开始打鱼")
        # 缩放屏幕至最小
        self.game_assist.zoom_out(repeat=3)

        frame = self.game_assist.get_frame()
        # 检查有没有自动打鱼按钮
        x, y, accuracy = find_ui(frame, auto_fight)
        if accuracy < 0.9:
            attack_flow = self.army_attack.get(self.strategy)
            if attack_flow is None:
                self.logger.error("匹配不到该流派打法")
                self._notify_fish_fail(f"找不到自动战斗按钮图标，且流派[{self.strategy}]无对应手动打法")
                return False
            if config.USE_ACTIVITY_SOLDERS and activity_solders_list:
                for i, activity_solder in enumerate(activity_solders_list):
                    if self.battle_util.put_solders(
                            solder_card=activity_solder,
                            solder_name=f"活动兵种{i}",
                            duration=10
                    ):
                        self.logger.info(f"成功部署活动兵种{i}")
                    else:
                        self.logger.info(f"部署活动兵种{i}失败")
            # 进入下兵种过程
            attack_flow()
        else:
            self.logger.info("点击自动战斗")
            self.game_assist.click_button(x, y)
            self.sleep(1)

        begin_fight_time = time.time()
        destroy_rate_area = None
        check_time = 20

        # 持续监控打鱼结果
        while True:
            if time.time() - begin_fight_time > 3 * 62:
                self.logger.info("超出对战时间，结束对战")
                self._notify_fish_fail("对战超过186秒仍未检测到结束标识，判定超时")
                return False
            elif time.time() - begin_fight_time > 3 * 21 and check_time > 13:
                if click_if_exist(self.game_assist, ui=speed) and check_time > 3:
                    self.logger.info("点击快进，检查时间缩短至3s")
                    check_time = 3
                else:
                    self.logger.info("缩短检查时间至13s")
                    check_time = 13

            elif time.time() - begin_fight_time > 3 * 28 and check_time > 8:
                if click_if_exist(self.game_assist, ui=speed) and check_time > 3:
                    self.logger.info("点击快进，检查时间缩短至3s")
                    check_time = 3
                else:
                    self.logger.info("缩短检查时间至7s")
                    check_time = 7

            frame = self.game_assist.get_frame()
            if contains_ui(frame, off_line):
                self.logger.info(f"号主顶号，终止打鱼")
                self._notify_fish_fail("战斗过程中检测到号主顶号/掉线（离线图标），打鱼终止")
                return False

            res = find_uis_center(frame, uis=[confirm_resource, get_box_button])
            if res:
                x, y = res
                self.game_assist.click_button(x, y)
                self.logger.info("点击结束对战")
                break

            res = find_uis_center(frame, uis=[speed])
            if res:
                x, y = res
                self.game_assist.click_button(x, y)
                self.logger.info("点击倍速")

            res = find_uis_center(frame, uis=[choose_reward,choose_reward_end])
            if res:
                x, y = res
                self.logger.info("点击选择奖励")
                self.game_assist.click_button(x, y + 200, max_offset=20) #点击“选择奖励下面具体的选项”
                self.sleep(4)
                check_time -= 2

            finish_fight = False

            roi_destroy_area = frame[555:587, 1191:1265]
            if destroy_rate_area is None:
                logger.info("填充摧毁率首图")
            else:
                result = cv2.matchTemplate(image=destroy_rate_area, templ=roi_destroy_area,
                                           method=cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                accuracy = round(max_val, 4)
                self.logger.info(f"精确度:{accuracy}")

                if accuracy > 0.90:
                    # 退出战斗过程
                    for i in range(0, 4):
                        self.logger.info(f"{i}、摧毁率{check_time}s内没有变动，直接退出")
                        res = find_uis_center(screen=frame, uis=[choose_reward, choose_reward_end])
                        if res:
                            x, y = res
                            self.game_assist.click_button(x, y + 200, max_offset=20)
                            self.logger.info("点击领取奖励")
                            self.sleep(5)
                            frame = self.game_assist.get_frame()
                        res = find_uis_center(frame, uis = [give_up_battle, end_war])
                        if not res:
                            self.logger.info(f"{i}、找不到放弃或者结束战斗标识")
                        else:
                            x, y = res
                            self.game_assist.click_button(x, y)
                            self.logger.info("点击放弃按钮或者结束战斗按钮")
                            self.evt.wait(1)
                            frame = self.game_assist.get_frame()

                        x, y, accuracy = find_ui_center(screen=frame, ui=confirm_give_up_battle)
                        if accuracy < 0.85:
                            self.logger.info(f"{i}、找不到确认结束战斗标识")
                        else:
                            self.game_assist.click_button(x, y)
                            self.logger.info("点击确认结束战斗")
                            self.evt.wait(5)
                            frame = self.game_assist.get_frame()

                        res = find_uis_center(frame, uis = [confirm_resource, get_box_button, hammer, attack_on_main])
                        if not res:
                            self.logger.info(f"{i}、找不到确认资源标识")
                        else:
                            x, y = res
                            self.logger.info("点击回营")
                            self.game_assist.click_button(x, y)
                            finish_fight = True
                            break
                        self.sleep(2)
                        frame = self.game_assist.get_frame()
            if finish_fight:
                break
            destroy_rate_area = roi_destroy_area
            self.sleep(check_time)

        # 结束战斗之后回到主界面
        self.logger.debug("进入回复至主界面过程")
        for i in range(0, 5):
            if i > 1:
                self.logger.debug(f"{i}、再次尝试回复至主界面")
                # self.game_assist.ramdom_click()
            frame = self.game_assist.get_frame()
            if contains_ui(frame, attack_on_main):
                self.logger.info(f"{i}、当前处于主界面")
                break

            if contains_ui(frame, off_line):
                self.logger.info(f"{i}、号主顶号")
                self._notify_fish_fail("战斗结束返回主界面时检测到号主顶号/掉线（离线图标）")
                return False

            b, g, r = frame[200, 200]
            if (b > 240 and g > 240 and r > 240):
                self.logger.info(f"{i}、正在过渡回到主界面")
                self.sleep(3)
            else:
                self.sleep(1)

            frame = self.game_assist.get_frame()

            res = find_uis_center(frame, uis = [reporting, close_ad, continue_img])
            if res:
                x, y = res
                self.game_assist.click_button(x, y)

            if find_uis_center(frame, uis=[hammer, jian]):
                self.logger.info(f"{i}、检查开箱子")
                for i in range(0, 6):
                    res = find_uis_center(frame, uis=[hammer, jian])
                    if res is None:
                        self.logger.info(f"开箱子完毕")
                        self.sleep(2)
                        break
                    else:
                        x, y = res
                        self.game_assist.click_button(x, y, max_offset=20)
                        self.game_assist.click_button(x, y, max_offset=20)
                        self.sleep(1)
                        frame = self.game_assist.get_frame()

                x, y, accuracy = find_ui(frame, continue_img)
                if accuracy > 0.9:
                    self.game_assist.click_button(x, y, max_offset=20)
                    self.logger.info("点击继续按钮")
                    self.sleep(1)
                    frame = self.game_assist.get_frame()
                else:
                    self.logger.info("还没有出现继续按钮")

                if contains_ui(frame, attack_on_main):
                    self.logger.info("已经回到主界面")
                    break
            else:
                self.sleep(3)
            self.sleep(1)

        self.logger.info("返回打鱼成功信息")
        return True

    def solders_allocation(self) -> str | None:
        self.logger.info("开始自动配兵")
        flag = False
        strategy = None
        ordered = redis_cache.get(f"fish:solders:{self.room_id}:{self.current_user_id}")
        for key, value in army_strs.items():
            # 使用用户指定的配兵
            if ordered and key not in ordered:
                continue
            if not self.is_aboard_version:  # 国服
                cmd = (
                    'am start -n "com.tencent.tmgp.supercell.clashofclans/com.supercell.titan.tencent.GameAppTencent" '
                    f'-d "clashofclans://action=CopyArmy&army={value}"'
                )
            else:  # 国际服
                cmd = (
                    'am start -a android.intent.action.VIEW '
                    '-n "com.supercell.clashofclans/com.supercell.titan.GameApp" '
                    f'-d "clashofclans://action=CopyArmy&army={value}"'
                )
            self.game_assist.device.shell(cmd)
            self.sleep(2)
            frame = self.game_assist.get_frame()
            if not contains_ui(frame, ui=allocation_panel):
                self.logger.error("未弹出军队配置面板")
                continue
            frame = frame[0:350, :]
            x, y, accuracy = find_ui_center(frame, ui=save_army)
            if accuracy < 0.85:
                self.logger.error("找不到保存军队按钮")
                continue
            self.game_assist.click_button(x, y)
            self.sleep(1)
            ui = self.army_icons[key]
            frame = self.game_assist.get_frame()[0:350, :]
            if contains_ui(frame, ui=ui, threshold=0.91, gray=False):
                strategy = key
                flag = True
                x, y, accuracy = find_ui_center(ui=import_use, screen=frame)
                if accuracy < 0.85:
                    self.logger.error("无法点击使用配兵")
                else:
                    self.game_assist.click_button(x, y)
                    self.logger.info(f"使用配兵{strategy}")
                    self.sleep(0.5)

                    finish_allocate = False
                    for j in range(0, 4):
                        frame = self.game_assist.get_frame()
                        res = find_uis_center(frame, uis=[ignore_confirm, close_allocation_panel])
                        if res is None:
                            self.logger.error("结束流派选择程序")
                            finish_allocate = True
                            break
                        else:
                            x, y = res
                            self.logger.info("点击关闭流派面板")
                            self.game_assist.click_button(x, y)
                    if finish_allocate:
                        break
            else:
                self.logger.info(f"无法找到'{key}'流派的标志性兵种")

        if not flag:
            return None

        return strategy

    def logout(self):
        self.logger.info("开始执行退出帐号")
        if not self.is_aboard_version:
            for i in range(0, 4):
                if not contains_ui(screen=self.game_assist.get_frame(), ui=attack_on_main):
                    self.logger.info(f"{i}、当前不是主界面")
                self.sleep(1)
                if not (click_if_exist(game_assist=self.game_assist, ui=open_setting_red)
                        or click_if_exist(game_assist=self.game_assist,ui=open_setting)):
                    self.logger.info(f"{i}、找不到设置弹出框")
                else:
                    self.logger.info(f"点击设置弹出框")
                self.sleep(1)
                if not (click_if_exist(game_assist=self.game_assist, ui=setting_red)
                        or click_if_exist(game_assist=self.game_assist, ui=setting)):
                    self.logger.info(f"{i}、找不到设置按钮")
                else:
                    self.logger.info(f"打开设置")
                self.sleep(1)
                if not click_if_exist(game_assist=self.game_assist, ui=logout):
                    self.logger.info(f"{i}、找不到退出登录按钮")
                else:
                    self.logger.info(f"退出登录")
                self.sleep(1)
                frame = self.game_assist.get_frame()
                if contains_ui(screen=frame, ui=qr_code):
                    self.logger.info("退出登录程序执行完毕")
                    return
                elif (frame[200, 200] <= 70).all():
                        self.logger.info("正在过度回到登录界面")
                        return
                self.sleep(2)
        else:
            # 国际服退出登录
            for i in range(0, 3):
                if not contains_ui(screen=self.game_assist.get_frame(), ui=attack_on_main):
                    self.logger.info(f"{i}、当前不是主界面")
                self.sleep(1)
                if not (click_if_exist(game_assist=self.game_assist, ui=setting_red)
                        or click_if_exist(game_assist=self.game_assist, ui=setting)):
                    self.logger.info(f"{i}、找不到设置按钮")
                else:
                    self.logger.info(f"打开设置")
                self.sleep(1)

                if not click_if_exist(game_assist=self.game_assist, ui=open_id):
                    self.logger.info(f"{i}、找不到蓝色打开设置按钮")
                self.sleep(1)

                if contains_ui(screen=self.game_assist.get_frame(), ui=id_setting):
                    if contains_ui(screen=self.game_assist.get_frame(), ui=logout_panel):
                        self.game_assist.human_swipe_with_u2( 762, 568, 688, 226)
                        time.sleep(1)
                        if click_if_exist(game_assist=self.game_assist, ui=logout_d):
                            self.logger.info("点击退出登录")
                            time.sleep(1)
                        else:
                            self.logger.info("找不到退出登录黑色按钮")
                            return
                        if not click_if_exist(game_assist=self.game_assist, ui=remember_me):
                            self.logger.info("没有弹出确定登出界面")
                            return
                        else:
                            self.logger.info("点击取消‘记住我’")
                        self.sleep(0.5)
                        if not click_if_exist(game_assist=self.game_assist, ui=logout_final):
                            self.logger.info("找不到最终确认登出蓝色按钮")
                        else:
                            self.logger.info("点击确认登出蓝色按钮")
                            return

                    else:
                        click_if_exist(game_assist=self.game_assist, ui=id_setting)
                else:
                    self.logger.info(f"{i}、没有弹出个人ID界面设置面板")


    def sleep(self, duration: float):
        # 原生threading.Event.wait，完美兼容终止逻辑，无需修改
        self.evt.wait(duration)
        if self.evt.is_set():
            self.logger.info("检测到停止打鱼任务终止")
            raise BattleInterruptError("外部触发停止")

    def stop(self):
        self.logger.info("终止打鱼任务")
        self.evt.set()


if __name__ == "__main__":
    game_assist = U2GameAssist()
    hit_fish = HitFish(game_assist, room_id=-1, current_user_id=1, is_aboard_version=False, ranking=False)
    hit_fish.logout()
    game_assist.client_stop()

