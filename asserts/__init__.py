import glob
import os
import sys

src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_path = os.path.join(src_path, '../')

if src_path not in sys.path:
    sys.path.insert(0, src_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)
    # print(root_path)
import cv2

from src.my_logger import logger

# 1. 拿到当前 __init__.py 所在目录（asserts/ 的绝对路径）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ========== main_page ==========
chat_room_open_feature_path = os.path.join(BASE_DIR, "main_page", "chat_room_screen_feature.png")
chat_room_open_feature = cv2.imread(chat_room_open_feature_path)
if chat_room_open_feature is None:
    logger.error("chat_room_screen_feature.png 未加载")

room_on_off_path = os.path.join(BASE_DIR, "main_page", "room_on_off.png")
room_on_off = cv2.imread(room_on_off_path)
if room_on_off is None:
    logger.error("room_on_off.png 未加载")

room_clan_signal_path = os.path.join(BASE_DIR, "main_page", "room_clan_signal.png")
room_clan_signal = cv2.imread(room_clan_signal_path)
if room_clan_signal is None:
    logger.error("room_clan_signal.png 未加载")

friendship_war_path = os.path.join(BASE_DIR, "main_page", "friendship_war.png")
friendship_war = cv2.imread(friendship_war_path)
if friendship_war is None:
    logger.error("friendship_war.png 未加载")

water_path = os.path.join(BASE_DIR, "main_page", "water.png")
water = cv2.imread(water_path)
if water is None:
    logger.error("water.png 未加载")

oil_path = os.path.join(BASE_DIR, "main_page", "oil.png")
oil = cv2.imread(oil_path)
if oil is None:
    logger.error("oil.png 未加载")

coin_path = os.path.join(BASE_DIR, "main_page", "coin.png")
coin = cv2.imread(coin_path)
if coin is None:
    logger.error("coin.png 未加载")

input_box_path = os.path.join(BASE_DIR, "main_page", "input_box.png")
input_box = cv2.imread(input_box_path)
if input_box is None:
    logger.error("input_box.png 未加载")

clan_msg_path = os.path.join(BASE_DIR, "main_page", "clan_msg.png")
clan_msg = cv2.imread(clan_msg_path)
if clan_msg is None:
    logger.error("clan_msg.png 未加载")

confirm_path = os.path.join(BASE_DIR, "main_page", "confirm.png")
confirm = cv2.imread(confirm_path)
if confirm is None:
    logger.error("confirm.png 未加载")

open_setting_red_path = os.path.join(BASE_DIR, "main_page", "open_setting_red.png")
open_setting_red = cv2.imread(open_setting_red_path)
if open_setting_red is None:
    logger.error("open_setting_red.png 未加载")

open_setting_path = os.path.join(BASE_DIR, "main_page", "open_setting.png")
open_setting = cv2.imread(open_setting_path)
if open_setting is None:
    logger.error("open_setting.png 未加载")

setting_red_path = os.path.join(BASE_DIR, "main_page", "setting_red.png")
setting_red = cv2.imread(setting_red_path)
if setting_red is None:
    logger.error("setting_red.png 未加载")

setting_path = os.path.join(BASE_DIR, "main_page", "setting.png")
setting = cv2.imread(setting_path)
if setting is None:
    logger.error("setting.png 未加载")


logout_path = os.path.join(BASE_DIR, "main_page", "logout.png")
logout = cv2.imread(logout_path)
if logout is None:
    logger.error("logout.png 未加载")

qr_code_path = os.path.join(BASE_DIR, "main_page", "qr_code.png")
qr_code = cv2.imread(qr_code_path)
if qr_code is None:
    logger.error("qr_code.png 未加载")

open_id_path = os.path.join(BASE_DIR, "main_page", "open_id.png")
open_id = cv2.imread(open_id_path)
if open_id is None:
    logger.error("open_id.png 未加载")

id_setting_path = os.path.join(BASE_DIR, "main_page", "id_setting.png")
id_setting = cv2.imread(id_setting_path)
if id_setting is None:
    logger.error("id_setting.png 未加载")

logout_d_path = os.path.join(BASE_DIR, "main_page", "logout_d.png")
logout_d = cv2.imread(logout_d_path)
if logout_d is None:
    logger.error("logout_d.png 未加载")

logout_panel_path = os.path.join(BASE_DIR, "main_page", "logout_panel.png")
logout_panel = cv2.imread(logout_panel_path)
if logout_panel is None:
    logger.error("logout_panel.png 未加载")

remember_me_path = os.path.join(BASE_DIR, "main_page", "remember_me.png")
remember_me = cv2.imread(remember_me_path)
if remember_me is None:
    logger.error("remember_me.png 未加载")

logout_final_path = os.path.join(BASE_DIR, "main_page", "logout_final.png")
logout_final = cv2.imread(logout_final_path)
if logout_final is None:
    logger.error("logout_final.png 未加载")

reporting_path = os.path.join(BASE_DIR, "main_page", "reporting.png")
reporting = cv2.imread(reporting_path)
if reporting is None:
    logger.error("reporting.png 未加载")

close_ad_path = os.path.join(BASE_DIR, "main_page", "close_ad.png")
close_ad = cv2.imread(close_ad_path)
if close_ad is None:
    logger.error("close_ad.png 未加载")

# ========== donate_page ==========
donate_button_path = os.path.join(BASE_DIR, "donate_page", "donate_button.png")
donate_button = cv2.imread(donate_button_path)
if donate_button is None:
    logger.error("donate_button.png 未加载")

donate_pop_up_feature_path = os.path.join(BASE_DIR, "donate_page", "donate_pop_up_feature.png")
donate_pop_up_feature = cv2.imread(donate_pop_up_feature_path)
if donate_pop_up_feature is None:
    logger.error("donate_pop_up_feature.png 未加载")

del_donate_button_path = os.path.join(BASE_DIR, "donate_page", "del_donate_button.png")
del_donate_button = cv2.imread(del_donate_button_path)
if del_donate_button is None:
    logger.error("del_donate_button.png 未加载")

donate_rect_right_top_path = os.path.join(BASE_DIR, "donate_page", "right_top.png")
donate_rect_right_top = cv2.imread(donate_rect_right_top_path)
if donate_rect_right_top is None:
    logger.error("donate_rect_right_top.png 未加载")

#==========hit_fish_img==========
HIT_FISH_IMG_DIR = "hit_fish_img"
angel_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "angel.png")
angel = cv2.imread(angel_path)
if angel is None:
    logger.error("angel.png 未加载")

# attack_on_main.png
attack_on_main_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "attack_on_main.png")
attack_on_main = cv2.imread(attack_on_main_path)
if attack_on_main is None:
    logger.error("attack_on_main.png 未加载")

# attack_on_panel.png
attack_on_panel_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "attack_on_panel.png")
attack_on_panel = cv2.imread(attack_on_panel_path)
if attack_on_panel is None:
    logger.error("attack_on_panel.png 未加载")

# big_guard.png
big_guard_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "big_guard.png")
big_guard = cv2.imread(big_guard_path)
if big_guard is None:
    logger.error("big_guard.png 未加载")

# confirm_give_up_battle.png
confirm_give_up_battle_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "confirm_give_up_battle.png")
confirm_give_up_battle = cv2.imread(confirm_give_up_battle_path)
if confirm_give_up_battle is None:
    logger.error("confirm_give_up_battle.png 未加载")

# confirm_resource.png
confirm_resource_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "confirm_resource.png")
confirm_resource = cv2.imread(confirm_resource_path)
if confirm_resource is None:
    logger.error("confirm_resource.png 未加载")

# end_war_button.png
end_war_button_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "end_war_button.png")
end_war_button = cv2.imread(end_war_button_path)
if end_war_button is None:
    logger.error("end_war_button.png 未加载")

# full_coin.png
full_coin_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "full_coin.png")
full_coin = cv2.imread(full_coin_path)
if full_coin is None:
    logger.error("full_coin.png 未加载")

# full_oil.png
full_oil_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "full_oil.png")
full_oil = cv2.imread(full_oil_path)
if full_oil is None:
    logger.error("full_oil.png 未加载")

# give_up_battle.png
give_up_battle_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "give_up_battle.png")
give_up_battle = cv2.imread(give_up_battle_path)
if give_up_battle is None:
    logger.error("give_up_battle.png 未加载")

# man.png
man_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "man.png")
man = cv2.imread(man_path)
if man is None:
    logger.error("man.png 未加载")

# queen.png
queen_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "queen.png")
queen = cv2.imread(queen_path)
if queen is None:
    logger.error("queen.png 未加载")

# run_tu.png
run_tu_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "run_tu.png")
run_tu = cv2.imread(run_tu_path)
if run_tu is None:
    logger.error("run_tu.png 未加载")

fly_king_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "fly_king.png")
fly_king = cv2.imread(fly_king_path)
if fly_king is None:
    logger.error("fly_king.png 未加载")

# search_fish.png
search_fish_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "search_fish.png")
search_fish = cv2.imread(search_fish_path)
if search_fish is None:
    logger.error("search_fish.png 未加载")

# stove.png
stove_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "stove.png")
stove = cv2.imread(stove_path)
if stove is None:
    logger.error("stove.png 未加载")

# toothpick_soldier.png
toothpick_soldier_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "toothpick_soldier.png")
toothpick_soldier = cv2.imread(toothpick_soldier_path)
if toothpick_soldier is None:
    logger.error("toothpick_soldier.png 未加载")

small_guard_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "small_guard.png")
small_guard = cv2.imread(small_guard_path)
if small_guard is None:
    logger.error("small_guard.png 未加载")

end_war_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "end_war.png")
end_war = cv2.imread(end_war_path)
if end_war is None:
    logger.error("end_war.png 未加载")

dragon_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "dragon.png")
dragon = cv2.imread(dragon_path)
if dragon is None:
    logger.error("dragon.png 未加载")

valkyrie_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "valkyrie.png")
valkyrie = cv2.imread(valkyrie_path)
if valkyrie is None:
    logger.error("valkyrie.png 未加载")

off_line_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "off_line.png")
off_line = cv2.imread(off_line_path)
if off_line is None:
    logger.error("off_line.png 未加载")

get_box_button_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "get_box.png")
get_box_button = cv2.imread(get_box_button_path)
if get_box_button is None:
    logger.error("get_box_button.png 未加载")

hammer_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "hammer.png")
hammer = cv2.imread(hammer_path)
if hammer is None:
    logger.error("hammer.png 未加载")

continue_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "continue.png")
continue_img = cv2.imread(continue_path)
if continue_img is None:
    logger.error("continue.png 未加载")

speed_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "speed.png")
speed = cv2.imread(speed_path)
if speed is None:
    logger.error("speed.png 未加载")

fat_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "fat.png")
fat = cv2.imread(fat_path)
if fat is None:
    logger.error("fat.png 未加载")

archer_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "archer.png")
archer = cv2.imread(archer_path)
if archer is None:
    logger.error("archer.png 未加载")

dragon_king_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "dragon_king.png")
dragon_king = cv2.imread(dragon_king_path)
if dragon_king is None:
    logger.error("dragon_king.png 未加载")

e_dragon_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "e_dragon.png")
e_dragon = cv2.imread(e_dragon_path)
if e_dragon is None:
    logger.error("e_dragon.png 未加载")

machine_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "machine.png")
machine = cv2.imread(machine_path)
if machine is None:
    logger.error("machine.png 未加载")

rank_confirm_attack_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "rank_confirm_attack.png")
rank_confirm_attack = cv2.imread(rank_confirm_attack_path)
if rank_confirm_attack is None:
    logger.error("rank_confirm_attack.png 未加载")

sign_up_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "sign_up.png")
sign_up = cv2.imread(sign_up_path)
if sign_up is None:
    logger.error("sign_up.png 未加载")

jian_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "jian.png")
jian = cv2.imread(jian_path)
if jian is None:
    logger.error("jian.png 未加载")

auto_fight_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "auto_fight.png")
auto_fight = cv2.imread(auto_fight_path)
if auto_fight is None:
    logger.error("auto_fight.png 未加载")

choose_solder_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "choose_solder.png")
choose_reward = cv2.imread(choose_solder_path)
if choose_reward is None:
    logger.error("choose_solder.png 未加载")

choose_reward_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "choose_reward.png")
choose_reward_end = cv2.imread(choose_reward_path)
if choose_reward_end is None:
    logger.error("choose_reward.png 未加载")

# ============= 活动兵种 ===========
activity_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "activity")
png_pattern = os.path.join(activity_path, "*.png")
png_file_list = glob.glob(png_pattern)

# 按文件名排序（可选，让顺序固定）
png_file_list.sort()

# 存放所有读取出来的图片
activity_solders_list = []

# 遍历所有 png 并用 cv2.imread 读取
for img_path in png_file_list:
    # 用 OpenCV 读取图片
    img = cv2.imread(img_path)

    # 判断是否读取成功（防止损坏图片）
    if img is not None:
        activity_solders_list.append(img)
    else:
        print(f"读取失败：{img_path}")

# ============= 导入配兵 =============
allocation_panel_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "allocation_panel.png")
allocation_panel = cv2.imread(allocation_panel_path)
if allocation_panel is None:
    logger.error("allocation_panel.png 未加载")

save_army_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "save_army.png")
save_army = cv2.imread(save_army_path)
if save_army is None:
    logger.error("save_army.png 未加载")

tooth_import_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "tooth_import.png")
tooth_import = cv2.imread(tooth_import_path)
if tooth_import is None:
    logger.error("tooth_import.png 未加载")

dragon_import_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "dragon_import.png")
dragon_import = cv2.imread(dragon_import_path)
if dragon_import is None:
    logger.error("dragon_import.png 未加载")

e_dragon_import_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "e_dragon_import.png")
e_dragon_import = cv2.imread(e_dragon_import_path)
if e_dragon_import is None:
    logger.error("e_dragon_import.png 未加载")

valkyrie_import_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "valkyrie_import.png")
valkyrie_import = cv2.imread(valkyrie_import_path)
if valkyrie_import is None:
    logger.error("valkyrie_import.png 未加载")

fat_import_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "fat_import.png")
fat_import = cv2.imread(fat_import_path)
if fat_import is None:
    logger.error("fat_import.png 未加载")

fat_import_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "fat_import.png")
fat_import = cv2.imread(fat_import_path)
if fat_import is None:
    logger.error("fat_import.png 未加载")

small_man_import_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "small_man_import.png")
small_man_import = cv2.imread(small_man_import_path)
if small_man_import is None:
    logger.error("small_man_import.png 未加载")

import_use_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "import_use.png")
import_use = cv2.imread(import_use_path)
if import_use is None:
    logger.error("import_use.png 未加载")


ignore_confirm_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "ignore_confirm.png")
ignore_confirm = cv2.imread(ignore_confirm_path)
if ignore_confirm is None:
    logger.error("ignore_confirm.png 未加载")

close_allocation_panel_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "close_allocation_panel.png")
close_allocation_panel = cv2.imread(close_allocation_panel_path)
if close_allocation_panel is None:
    logger.error("close_allocation_panel.png 未加载")

rank_finish_path = os.path.join(BASE_DIR, HIT_FISH_IMG_DIR, "rank_finish.png")
rank_finish = cv2.imread(rank_finish_path)
if rank_finish is None:
    logger.error("rank_finish.png 未加载")

#=========== 夜市界 ================
main_page_d_path = os.path.join(BASE_DIR, "dark_main_page", "main_page.png")
main_page_d = cv2.imread(main_page_d_path)
if main_page_d is None:
    logger.error("main_page_d.png 未加载")

search_now_path = os.path.join(BASE_DIR, "dark_main_page", "search_now.png")
search_now = cv2.imread(search_now_path)
if search_now is None:
    logger.error("search_now.png 未加载")

switch_solders_path = os.path.join(BASE_DIR, "dark_main_page", "switch_solders.png")
switch_solders = cv2.imread(switch_solders_path)
if switch_solders is None:
    logger.error("switch_solders.png 未加载")

arch_path = os.path.join(BASE_DIR, "dark_main_page", "arch.png")
arch = cv2.imread(arch_path)
if arch is None:
    logger.error("arch.png 未加载")

go_back_path = os.path.join(BASE_DIR, "dark_main_page", "go_back.png")
go_back = cv2.imread(go_back_path)
if go_back is None:
    logger.error("go_back.png 未加载")

dark_man_path = os.path.join(BASE_DIR, "dark_main_page", "man.png")
dark_man = cv2.imread(dark_man_path)
if dark_man is None:
    logger.error("dark_man.png 未加载")

confirm_path = os.path.join(BASE_DIR, "dark_main_page", "confirm.png")
confirm = cv2.imread(confirm_path)
if confirm is None:
    logger.error("confirm.png 未加载")

x1_path = os.path.join(BASE_DIR, "dark_main_page", "1x.png")
x1 = cv2.imread(x1_path)
if x1 is None:
    logger.error("x1.png 未加载")


if __name__ == "__main__":
    pass