from datetime import datetime
import cv2
import os
import smtplib
import time
import numpy as np
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.header import Header
from concurrent.futures import ThreadPoolExecutor, Future
# 读取包内资源标准库
from importlib.resources import read_text

from api.api_config import BACK_END_DOMAIN
from api.dao.rooms_dao import RoomsDao
from api.dao.users_dao import UsersDao
from asserts import dragon
from my_logger import logger
from src.redis_client import redis_cache

# 邮箱正则校验
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9_\-.]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$')

# 需要填写邮箱的发出者
MAIL_CONFIG = {
    "sender": os.getenv("COC_MAIL_SENDER", ""),
    "auth_code": os.getenv("COC_MAIL_AUTH_CODE", ""),
    "smtp_host": os.getenv("COC_SMTP_HOST", "smtp.qq.com"),
    "smtp_port": int(os.getenv("COC_SMTP_PORT", "465")),
    "timeout": 15,
    "max_retry": 2,
    "notify_template": "email_notify.html",
    "code_template": "verify_code.html",
    "fail_template": "fish_fail.html"
}

MAIL_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="mail-sender")

class EmailSender:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "notify_tpl") and hasattr(self, "code_tpl") and hasattr(self, "fail_tpl"):
            return
        self.cfg = MAIL_CONFIG
        # 加载三套模板
        self.notify_tpl = self._load_template(self.cfg["notify_template"])
        self.code_tpl = self._load_template(self.cfg["code_template"])
        self.fail_tpl = self._load_template(self.cfg["fail_template"])
        logger.info("通知模板、验证码模板、失败告警模板全部加载完成")

    def _load_template(self, filename: str) -> str:
        """
        读取 src.resources.template 包下的html资源
        等价Java ClassPath读取资源，任意启动方式均可正常加载
        """
        try:
            # 包路径：resources.template
            content = read_text("resources.template", filename, encoding="utf-8")
            return content
        except Exception as e:
            logger.error(f"模板资源读取失败 {filename}: {e}")
            raise SystemExit("邮件模板缺失，程序终止")

    # 场景1：设备告警推送（带截图）
    def send_notify_mail(
            self, receiver_email: str, screen_img: np.ndarray | None,
            header: str, mail_title: str, username: str, notice_text: str, item_list: list
    ) -> bool:
        retry = 0
        max_retry = self.cfg["max_retry"]
        li_str = "".join([f"<li>{line}</li>" for line in item_list])
        html = self.notify_tpl.format(mail_title=mail_title, username=username, notice_text=notice_text,
                                      item_list=li_str, site_url=BACK_END_DOMAIN)

        while retry <= max_retry:
            try:
                msg = MIMEMultipart("related")
                msg["From"] = Header(header, "utf-8").encode() + f" <{self.cfg['sender']}>"
                msg["To"] = receiver_email
                msg["Subject"] = Header(mail_title, "utf-8")
                msg.attach(MIMEText(html, "html", "utf-8"))

                # 有图片才附加截图
                if screen_img is not None and isinstance(screen_img, np.ndarray) and screen_img.size > 0:
                    ok, buf = cv2.imencode(".png", screen_img)
                    if ok:
                        img_part = MIMEImage(buf.tobytes())
                        img_part.add_header("Content-ID", "<screen_img>")
                        msg.attach(img_part)
                    else:
                        logger.warning("截图编码失败，邮件无图片")

                server = smtplib.SMTP_SSL(self.cfg["smtp_host"], self.cfg["smtp_port"], timeout=self.cfg["timeout"])
                server.login(self.cfg["sender"], self.cfg["auth_code"])
                server.sendmail(self.cfg["sender"], receiver_email, msg.as_string())
                server.quit()
                logger.info(f"告警邮件发送成功 → {receiver_email}")
                return True
            except Exception as err:
                retry += 1
                time.sleep(retry)
                if retry > max_retry:
                    logger.error(f"告警邮件发送失败 {receiver_email}: {err}")
        return False

    # 场景3：打鱼失败告警邮件（带截图+失败原因）
    def send_fail_mail(
            self, receiver_email: str, screen_img: np.ndarray | None,
            header: str, mail_title: str, username: str, notice_text: str,
            fail_reason: str, item_list: list
    ) -> bool:
        retry = 0
        max_retry = self.cfg["max_retry"]
        li_str = "".join([f"<li>{line}</li>" for line in item_list])
        html = self.fail_tpl.format(
            mail_title=mail_title,
            username=username,
            notice_text=notice_text,
            fail_reason=fail_reason,
            item_list=li_str,
            site_url=BACK_END_DOMAIN
        )

        while retry <= max_retry:
            try:
                msg = MIMEMultipart("related")
                msg["From"] = Header(header, "utf-8").encode() + f" <{self.cfg['sender']}>"
                msg["To"] = receiver_email
                msg["Subject"] = Header(mail_title, "utf-8")
                msg.attach(MIMEText(html, "html", "utf-8"))

                # 有图片才附加截图
                if screen_img is not None and isinstance(screen_img, np.ndarray) and screen_img.size > 0:
                    ok, buf = cv2.imencode(".png", screen_img)
                    if ok:
                        img_part = MIMEImage(buf.tobytes())
                        img_part.add_header("Content-ID", "<screen_img>")
                        msg.attach(img_part)
                    else:
                        logger.warning("截图编码失败，邮件无图片")

                server = smtplib.SMTP_SSL(self.cfg["smtp_host"], self.cfg["smtp_port"], timeout=self.cfg["timeout"])
                server.login(self.cfg["sender"], self.cfg["auth_code"])
                server.sendmail(self.cfg["sender"], receiver_email, msg.as_string())
                server.quit()
                logger.info(f"失败告警邮件发送成功 → {receiver_email}")
                return True
            except Exception as err:
                retry += 1
                time.sleep(retry)
                if retry > max_retry:
                    logger.error(f"失败告警邮件发送失败 {receiver_email}: {err}")
        return False

    # 场景2：6位验证码邮件（同步发送，无截图）
    def send_code_mail(
            self, receiver_email: str, header: str, mail_title: str,
            username: str, notice_text: str, verify_code: str, item_list: list
    ) -> bool:
        retry = 0
        max_retry = self.cfg["max_retry"]
        li_str = "".join([f"<li>{line}</li>" for line in item_list])
        html = self.code_tpl.format(
            mail_title=mail_title,
            username=username,
            notice_text=notice_text,
            verify_code=verify_code,
            item_list=li_str
        )

        while retry <= max_retry:
            try:
                msg = MIMEMultipart("related")
                msg["From"] = Header(header, "utf-8").encode() + f" <{self.cfg['sender']}>"
                msg["To"] = receiver_email
                msg["Subject"] = Header(mail_title, "utf-8")
                msg.attach(MIMEText(html, "html", "utf-8"))

                server = smtplib.SMTP_SSL(self.cfg["smtp_host"], self.cfg["smtp_port"], timeout=self.cfg["timeout"])
                server.login(self.cfg["sender"], self.cfg["auth_code"])
                server.sendmail(self.cfg["sender"], receiver_email, msg.as_string())
                server.quit()
                logger.info(f"验证码邮件发送成功 → {receiver_email}")
                return True
            except Exception as err:
                retry += 1
                time.sleep(retry)
                if retry > max_retry:
                    logger.error(f"验证码邮件发送失败 {receiver_email}: {err}")
        return False

    # 对外调用：资源打满通知（异步线程池发送）
    def notify_resource_full(self, user_id, img: np.ndarray | None, room_id):
        user_info = UsersDao.get_by_id(user_id)
        if not user_info:
            logger.error(f"用户{user_id}不存在")
            return
        if not getattr(user_info, "allow_email_notice", True):
            logger.info(f"用户{user_id}关闭邮件通知")
            return

        email = getattr(user_info, "email", "")
        if not email or not email.strip():
            logger.error(f"用户 {user_id} 没有设置通知邮箱")
            return
        if not EMAIL_PATTERN.match(email):
            logger.error(f"用户 {user_id} 邮箱格式错误：{email}")
            return

        room_info = RoomsDao.get_by_id(room_id)
        if not room_info:
            logger.info(f"房间{room_id}不存在")
            return

        items = [
            f"用户：{user_info.name}",
            f"房间：{room_info.rname}",
            f"触发时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ]

        def callback(fut: Future):
            e = fut.exception()
            if e: logger.error(f"邮件任务异常：{e}")

        future = MAIL_POOL.submit(
            self.send_notify_mail,
            receiver_email=email,
            screen_img=img,
            header="挂机监控系统",
            mail_title="资源打满通知",
            username=user_info.name,
            notice_text="您的帐号资源已经打满了",
            item_list=items
        )
        future.add_done_callback(callback)

    # 对外调用：打鱼失败告警（异步线程池发送，1分钟幂等）
    def notify_fish_failed(self, user_id, img: np.ndarray | None, room_id, fail_reason: str):
        user_info = UsersDao.get_by_id(user_id)
        if not user_info:
            logger.error(f"用户{user_id}不存在")
            return
        if not getattr(user_info, "allow_email_notice", True):
            logger.info(f"用户{user_id}关闭邮件通知")
            return

        email = getattr(user_info, "email", "")
        if not email or not email.strip():
            logger.error(f"用户 {user_id} 没有设置通知邮箱")
            return
        if not EMAIL_PATTERN.match(email):
            logger.error(f"用户 {user_id} 邮箱格式错误：{email}")
            return

        room_info = RoomsDao.get_by_id(room_id)
        if not room_info:
            logger.info(f"房间{room_id}不存在")
            return

        # 幂等：同一房间同一用户1分钟内只发一封失败告警
        idem_key = f"fish:fail:mail:{room_id}:{user_id}"
        if not redis_cache.set(idem_key, "1", ex=60, nx=True):
            logger.info(f"失败告警邮件1分钟内已发送过，跳过：{idem_key}")
            return

        items = [
            f"用户：{user_info.name}",
            f"房间：{room_info.rname}",
            f"失败原因：{fail_reason}",
            f"触发时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ]

        def callback(fut: Future):
            e = fut.exception()
            if e: logger.error(f"失败告警邮件任务异常：{e}")

        future = MAIL_POOL.submit(
            self.send_fail_mail,
            receiver_email=email,
            screen_img=img,
            header="挂机监控系统",
            mail_title="打鱼异常告警",
            username=user_info.name,
            notice_text="您的挂机打鱼任务异常终止，错误详情与设备截图如下，请及时查看：",
            fail_reason=fail_reason,
            item_list=items
        )
        future.add_done_callback(callback)

    # 异步发送验证码（如需同步直接调用send_code_mail即可）
    def send_verify_code_notice(self, user_id: int, code: str):
        user_info = UsersDao.get_by_id(user_id)
        if not user_info:
            logger.error(f"用户{user_id}不存在")
            return

        email = getattr(user_info, "email", "").strip()
        if not email:
            logger.error(f"用户 {user_id} 没有设置通知邮箱")
            return
        if not EMAIL_PATTERN.match(email):
            logger.error(f"用户 {user_id} 邮箱格式错误：{email}")
            return

        items = [
            "验证码有效期：5分钟",
            "请勿将验证码告知任何人",
            "如非本人操作，请及时修改账号密码"
        ]

        def callback(fut: Future):
            e = fut.exception()
            if e: logger.error(f"验证码邮件任务异常：{e}")

        future = MAIL_POOL.submit(
            self.send_code_mail,
            receiver_email=email,
            header="挂机系统账号验证",
            mail_title="邮箱验证码",
            username=user_info.name,
            notice_text="您正在进行账号验证，本次验证码如下：",
            verify_code=code,
            item_list=items
        )
        future.add_done_callback(callback)


mail_client = EmailSender()


if __name__ == '__main__':
    mail_client.send_code_mail(receiver_email="you@example.com",
                               header="邮件通知系统", mail_title="验证码通知", username="示例用户",
                               notice_text="您的验证码如下：", verify_code="289586",
                               item_list=[f"触发时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
