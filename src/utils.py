import inspect
import random
import re
import time
from datetime import datetime
from pathlib import Path
from PIL import Image
from typing import List

import cv2
from Levenshtein import ratio
from cv2.typing import MatLike

from src.my_logger import logger


def get_valid_time_str():
    # 年_月_日_时_分_秒
    return datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

def unify_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = text.replace('0', 'o')
    text = text.replace('1', 'i')
    text = text.replace('l', 'i')
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text)
    return text

def is_str_similarity(str1:str, str2:str, threshold = 0.8) -> bool:
    if str1 is None or str2 is None or len(str1) == 0 or len(str2) == 0:
        return False
    str1 = unify_text(str1)
    str2 = unify_text(str2)
    similarity = ratio(str1, str2)
    # print(similarity)
    return similarity > threshold

def contains_ui(screen:MatLike, ui:MatLike, threshold:float=0.8, gray:bool=True) -> bool:
    if screen is None or ui is None:
        logger.error("screen 或者 ui 为None,无法比较包含关系")
        return False
    if len(screen.shape) == 3 and gray:
        screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    if len(ui.shape) == 3 and gray:
        ui = cv2.cvtColor(ui, cv2.COLOR_BGR2GRAY)
    res_list = cv2.matchTemplate(image=screen, templ=ui, method=cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res_list)
    return max_val > threshold


def clean_string(s):
    """
    去除字符串中除了数字、英文字母和汉字以外的所有字符。
    """
    # 正则表达式：保留数字、字母（大小写）、汉字
    pattern = r'[^0-9A-Za-z\u4e00-\u9fff]'
    cleaned = re.sub(pattern, '', s)
    return cleaned

def img_show(img):
    img = cv2.resize(img, dsize=(0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    cv2.namedWindow("win", cv2.WINDOW_AUTOSIZE)
    cv2.imshow("win", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def img_show_origin(img):
    if len(img.shape) == 3:
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        img_rgb = img
    pil_img = Image.fromarray(img_rgb)
    pil_img.show()

def roi_msg_center(gray:MatLike) -> MatLike:
    if len(gray.shape) == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    start_y = h // 5
    end_y = h * 7 // 8  # 修正计算
    start_x = w // 10
    end_x = w - 135

    center_crop = gray[start_y:end_y, start_x:end_x]
    return center_crop

def find_ui(screen:MatLike, ui: cv2.Mat) -> tuple[int, int, float]:
    if screen is None or ui is None:
        logger.error("screen 或者 ui 为None,无法获取ui的左上角位置")
        return 0,0,0
    if len(screen.shape) == 3:
        screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    if len(ui.shape) == 3:
        ui = cv2.cvtColor(ui, cv2.COLOR_BGR2GRAY)
    # 模板匹配（使用相关性系数方法，最常用、最稳定）
    result = cv2.matchTemplate(screen, ui, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    accuracy = round(max_val, 4)  # 匹配准确度 0~1
    # 计算中心点
    top_left_x, top_left_y = max_loc
    return top_left_x, top_left_y, accuracy

def find_ui_center(screen: cv2.Mat, ui: cv2.Mat, gray:bool=True) -> tuple[int, int, float]:
    if screen is None or ui is None:
        logger.error("screen 或者 ui 为None,无法获取ui的中心位置")
        return 0,0,0
    if gray and len(screen.shape) == 3:
        screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    if gray and len(ui.shape) == 3:
        ui = cv2.cvtColor(ui, cv2.COLOR_BGR2GRAY)

    ui_height, ui_width = ui.shape[:2]

    # 模板匹配（使用相关性系数方法，最常用、最稳定）
    result = cv2.matchTemplate(screen, ui, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    accuracy = round(max_val, 4)  # 匹配准确度 0~1
    # 计算中心点
    top_left_x, top_left_y = max_loc
    center_x = top_left_x + ui_width // 2
    center_y = top_left_y + ui_height // 2

    return center_x, center_y, accuracy

def find_uis_center(screen: cv2.Mat, uis: List[MatLike], gray: bool = True) -> tuple[int, int] | None:
    if screen is None or uis is None:
        logger.error("screen 或者 ui 为None,无法获取ui的中心位置")
        return None

    # 1. 统一先把截图转为灰度（只执行一次）
    screen_gray = screen
    if gray and len(screen.shape) == 3:
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

    for ui in uis:
        template = ui
        # 2. 每次循环单独复制转换，不改动原列表元素，彻底同步
        if gray and len(template.shape) == 3:
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        ui_height, ui_width = template.shape[:2]

        result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        accuracy = round(max_val, 4)

        top_left_x, top_left_y = max_loc
        center_x = top_left_x + ui_width // 2
        center_y = top_left_y + ui_height // 2
        if accuracy > 0.9:
            return center_x, center_y

    return None

def loop_find_ui_xy(frame:MatLike,ui:MatLike, delay:float=0.6) -> tuple|None:
    for i in range(0, 3):
        x, y, threshold = find_ui(frame, ui)
        if threshold > 0.9:
            return x, y
        time.sleep(delay)
    return None

def path_help(relative_path):
    """
    使用 pathlib 将相对路径转换为绝对路径
    基准路径为**调用者**所在的目录（全项目通用）
    """
    # 获取调用者的文件路径（不是当前函数所在的文件）
    caller_frame = inspect.currentframe().f_back
    caller_file = caller_frame.f_code.co_filename
    script_dir = Path(caller_file).parent

    absolute_path = (script_dir / relative_path).resolve()
    return str(absolute_path)

def click_if_exist(game_assist,ui:MatLike, gray:bool=True, threshold:float=0.9) -> bool:
    x, y, accuracy = find_ui_center(game_assist.get_frame(), ui, gray=gray)
    if accuracy > threshold:
        game_assist.click_button(x, y)
        time.sleep(1)
        return True
    return False

def click_if_exist_uis(game_assist,uis:List[MatLike], gray:bool=True, threshold:float=0.9) -> bool:
    res = find_uis_center(game_assist.get_frame(), uis, gray=gray)
    if res is None:
        return False
    x, y = res
    game_assist.click_button(x, y)
    time.sleep(1)
    return True

def wait_ui_and_click(game_assist, ui:MatLike, delay = 0.6, metadata=None, iterator=3) -> bool:
    result = loop_find_ui(game_assist=game_assist,ui=ui, delay=delay, iterator=iterator)
    if result is not None:
        x, y = result
        game_assist.click_button(x, y)
        time.sleep(0.2)
        return True
    else:
        if metadata is None:
            logger.debug("未显示该ui标志")
        else:
            logger.debug(f"未显示该UI:{metadata} 标识")
        return False

def loop_find_ui(game_assist, ui:MatLike, delay:float=1, iterator=3, gray:bool=True) -> tuple|None:
    for i in range(0, iterator):
        frame = game_assist.get_frame()
        x, y, threshold = find_ui_center(frame, ui, gray=gray)
        if threshold > 0.9:
            return x, y
        time.sleep(delay)
    return None

def loop_find_uis(game_assist, uis:List[MatLike], delay:float=1, iterator=3, gray:bool=True) -> tuple|None:
    for i in range(0, iterator):
        for ui in uis:
            frame = game_assist.get_frame()
            x, y, threshold = find_ui_center(frame, ui, gray=gray)
            if threshold > 0.9:
                return x, y
        time.sleep(delay)
    return None

def human_gauss_click_position(x1: int, y1: int, x2: int, y2: int) -> tuple[int, int]:
    # 计算中心点（浮点没问题）
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2

    # 计算宽高
    w = x2 - x1
    h = y2 - y1

    # 高斯分布标准差
    sigma_x = w / 5
    sigma_y = h / 5

    # 生成高斯随机数
    x = random.gauss(cx, sigma_x)
    y = random.gauss(cy, sigma_y)

    # 先四舍五入成 int，再限制范围 → 解决类型报错
    x = round(x)
    y = round(y)

    # 现在都是 int，不会报错
    x = max(x1, min(x, x2))
    y = max(y1, min(y, y2))

    return x, y


def human_like_press_duration(base_sec: float) -> float:
    factor = random.lognormvariate(0, 0.18)

    # 以基础时长为中心波动
    duration = base_sec * factor

    # 合理上下限，避免极端值
    min_dur = base_sec * 0.6
    max_dur = base_sec * 1.6
    duration = max(min_dur, min(duration, max_dur))

    return round(duration, 3)

if __name__ == "__main__":
    # frame = game_assist.u2_capture_frame()
    # img_show_origin(frame)
    # game_assist.client_stop()
    pass