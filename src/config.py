import os


class Config:
    # 云手机的adb地址
    ADB_LINK = os.getenv("COC_ADB_LINK", "192.168.0.10:5555")
    ANDROID_DPI = 240
    CAP_PROP_FRAME_WIDTH = 1280 #游戏截屏的宽
    CAP_PROP_FRAME_HEIGHT = 720 #游戏截屏的高

    ENABLE_DONATION = True
    USE_ACTIVITY_SOLDERS = True
    DIY_STRATEGY = False


config = Config()
