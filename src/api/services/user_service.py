import base64
import random
import re
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

import jwt
from captcha.image import ImageCaptcha
from flask import request, g

from api.api_config import SECRET_KEY, ALGORITHM, EXPIRE_SEC, session
from api.dao.rooms_dao import RoomsDao
from api.dao.users_dao import users_dao, UsersDao
from api.exception.user_exception import UserNotFoundException, \
    PasswordWrongException, UsernameExistException, UserException
from api.models.request.login_request import LoginRequest
from api.models.request.register_request import RegisterRequest
from api.models.response.user_response import RoomResp
from api.services.email_sender import mail_client
from src.my_logger import logger
from src.redis_client import redis_cache

# 邮箱正则
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_\-.]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$')

class UserService:
    def __init__(self):
        self.captcha_expire_seconds = 300  # 5分钟过期
        self.captcha_length = 4  # 验证码长度
        self.captcha_width = 160  # 图片宽度
        self.captcha_height = 60
    pass

    def login(self, login_request: LoginRequest) -> tuple[bool, dict]:
        # 校验验证码
        if redis_cache.sismember("waning:ip",request.remote_addr):
            token = request.headers.get("Captcha-Token")
            if not token:
                raise UserException("请填写验证码")
            else:
                if not redis_cache.get(f"Captcha-Token:{request.remote_addr}:{token}"):
                    raise UserException("验证码错误或者已经过期")

        user = users_dao.get_by_name(name=login_request.username)
        if user is None or user.is_deleted:
            raise UserNotFoundException("用户不存在")
        if not user.check_password(login_request.password):
            raise PasswordWrongException("密码错误")
        user.last_login_time = datetime.now()
        payload = {
            "uid": user.id,
            "uname": user.name,
            "last_login_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "exp":datetime.utcnow() + timedelta(seconds=EXPIRE_SEC)
        }
        jwt_str = jwt.encode(payload=payload, key=SECRET_KEY, algorithm=ALGORITHM)
        session.commit()
        return True, {"token":jwt_str}

    def register(self, req: RegisterRequest) -> tuple[bool, Any]:
        exist_user = UsersDao.get_by_name(req.username)
        if exist_user:
            logger.error(f"{req.username}:用户名已被占用")
            raise UsernameExistException("用户名已被占用")

        # 循环生成，直到不重复
        display_uid = None
        for _ in range(20):  # 最多尝试20次，基本不可能耗尽
            temp_uid = self._generate_display_uid()
            if not UsersDao.get_by_display_uid(temp_uid):
                display_uid = temp_uid
                break
        if display_uid is None:
            raise Exception("系统繁忙，注册失败，请稍后重试")

        new_user = UsersDao()
        new_user.name = req.username
        new_user.portrait = req.portrait
        new_user.set_password(req.password)
        new_user.display_uid = display_uid
        new_user.create_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        session.add(new_user)
        session.commit()
        return True, "注册成功"

    def _generate_display_uid(self) -> str:
        # 固定6位，不足补0
        return f"{random.randint(0, 999999):06d}"

    def generate_captcha(self):
        """
        生成验证码

        Returns:
            dict: {
                'captcha_key': 'uuid',  # 用于验证的key
                'captcha_image': 'base64编码的图片'
            }
        """
        try:
            # 1. 生成唯一的captcha_key
            captcha_key = str(uuid.uuid4())

            # 2. 生成随机验证码
            captcha_code = self._generate_random_code()

            # 3. 将验证码存入Redis
            redis_key = f"captcha:{captcha_key}"
            redis_cache.setex(
                redis_key,
                self.captcha_expire_seconds,
                captcha_code.lower()  # 统一转小写存储
            )

            # 4. 生成验证码图片
            captcha_image_base64 = self._generate_captcha_image(captcha_code)

            logger.info(f"生成验证码成功, key: {captcha_key}, code: {captcha_code}")

            return {
                'captcha_key': captcha_key,
                'captcha_image': captcha_image_base64
            }

        except Exception as e:
            logger.error(f"生成验证码失败: {e}")
            return None

    def verify_captcha(self, captcha_key, captcha_code):
        """
        验证验证码

        Args:
            captcha_key: 验证码key
            captcha_code: 用户输入的验证码

        Returns:
            bool: 验证是否成功
        """
        try:
            if not captcha_key or not captcha_code:
                return False

            redis_key = f"captcha:{captcha_key}"
            stored_code = redis_cache.get(redis_key)

            if not stored_code:
                logger.warning(f"验证码不存在或已过期, key: {captcha_key}")
                return False

            # 验证码使用后立即删除（一次性使用）
            redis_cache.delete(redis_key)

            # 验证（忽略大小写）
            is_valid = stored_code.lower() == captcha_code.lower()

            if is_valid:
                token = uuid.uuid4()
                redis_cache.setex(f"Captcha-Token:{request.remote_addr}:{token}", 5 * 60, 1)
                return token
            return None

        except Exception as e:
            logger.error(f"验证验证码失败: {e}")
            return False

    def _generate_random_code(self):
        """生成随机验证码（数字+字母）"""
        # 排除容易混淆的字符: 0, O, 1, I, l
        chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
        code = ''.join(random.choices(chars, k=self.captcha_length))
        return code

    def _generate_captcha_image(self, captcha_code):
        """生成验证码图片并返回base64编码"""
        # 创建图片生成器
        image = ImageCaptcha(width=self.captcha_width, height=self.captcha_height)

        # 生成图片
        img_data = image.generate_image(captcha_code)

        # 转换为base64
        buffer = BytesIO()
        img_data.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return f"data:image/png;base64,{img_base64}"

    def get_info(self):
        user = UsersDao.get_by_id(g.uid)
        if not user:
            logger.error(f"用户 {g.uid} 不存在")
            raise UserNotFoundException("用户不存在")
        return {
            "uid": user.id,
            "uname": user.name,
            "display_uid": user.display_uid,
            "total_duration": user.total_duration,
            "portrait": user.portrait,
            "email": user.email,
            "allow_notice": user.allow_email_notice,
        }

    def get_name_by_display_uid(self, display_uid:str):
        if not display_uid or len(display_uid.strip()) != 6:
            raise UserException("参数不合法")
        user = UsersDao.get_by_display_uid(display_uid)
        if not user:
            return None
        return {"name":user.name, "uid":user.id}


    def check_user_name(self, uname) -> bool:
        if not uname:
            raise UserException("参数不合法")
        user = UsersDao.get_by_name(uname)
        return not user



    def update_user_name(self, username) -> tuple:
        if not username:
            return False, "用户名不能为空"
        uname_len = len(username)
        if uname_len < 2 or uname_len > 10:
            return False, "用户名长度需为2-10位"
        if not re.fullmatch(r'[\u4e00-\u9fa5a-zA-Z0-9_]+', username):
            return False, "用户名仅允许中文、字母、数字、下划线"
        user = UsersDao.get_by_id(g.uid)
        user.name = username
        session.commit()
        return True, "用户名更新成功"

    def delete_account(self) -> bool:
        user = UsersDao.get_by_id(g.uid)
        if not user:
            logger.error(f"用户 {g.uid} 不存在")
            raise UserNotFoundException("用户不存在")
        user.is_deleted = True
        session.commit()
        return True

    def logout(self) -> bool:
        token = request.headers.get("Authorization")
        if token:
            token = token.split(" ")[1]

            try:
                # 解码JWT（不验证过期时间，因为可能已经过期）
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})

                # 获取JWT中的过期时间戳
                exp_timestamp = payload.get("exp")
                if exp_timestamp:
                    # 计算剩余过期时间（秒）
                    current_time = datetime.utcnow().timestamp()
                    current_ttl = max(0, exp_timestamp - current_time)

                    if current_ttl > 0:
                        # 将token加入黑名单，设置过期时间为current_ttl
                        redis_cache.sadd("black_token", token)

                        # 获取当前黑名单Set的剩余过期时间
                        set_ttl = redis_cache.ttl("black_token")  # 可能返回 -1, -2, 或正数

                        # 这里的问题：如果 set_ttl <= 0，max_ttl = current_ttl
                        # 但如果 current_ttl 不是整数呢？
                        max_ttl = max(current_ttl, set_ttl) if set_ttl > 0 else current_ttl
                        redis_cache.expire("black_token", int(max_ttl))

                        return True

            except jwt.InvalidTokenError:
                # token无效
                pass

        return False

    def get_rooms(self):
        rooms_list = RoomsDao.get_by_owner(g.uid)
        resp = []
        for room in rooms_list:
            resp.append(RoomResp.from_orm(room))
        return resp

    def update_user_password(self, new_password, old_password) -> tuple:
        if not new_password or not old_password:
            raise UserException("参数不合法")
        """
            密码校验规则：
            1. 长度6~20位
            2. 必须包含：大写/小写字母、数字、特殊字符至少各一种
            特殊字符：!@#$%^&*()_+-=[]{}|;:,.<>?
            """
        if not (6 <= len(new_password) <= 20):
            return False, "密码长度必须6-20位"
        # 小写字母
        if not re.search(r"[a-z]", new_password):
            return False, "密码需包含小写字母"
        # 大写字母
        if not re.search(r"[A-Z]", new_password):
            return False, "密码需包含大写字母"
        # 数字
        if not re.search(r"\d", new_password):
            return False, "密码需包含数字"
        # 特殊字符
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", new_password):
            return False, "密码需包含特殊字符 !@#$%^&*()_+-=[]{}|;:,.<>?"

        user = UsersDao.get_by_id(g.uid)
        if not user.check_password(old_password):
            return False, "原密码校验错误"

        user.set_password(new_password)
        session.commit()
        return True, "密码更新成功"

    def set_email(self, email: str, verify_code: str):
        # 校验验证码非空
        if not verify_code.strip():
            raise UserException("验证码不能为空")

        # 清洗并校验邮箱格式
        email = email.strip()
        if not email or not EMAIL_REGEX.fullmatch(email):
            raise UserException("邮箱地址格式不正确")

        # 拼接Redis键，校验验证码
        key = f"email_verify_code:{g.uid}:{email}"
        stored_code = redis_cache.get(key)
        if not stored_code:
            raise UserException("验证码已过期或未发起验证")
        if verify_code.strip().lower() != stored_code.lower():
            raise UserException("验证码错误，请重新输入")

        # 查询用户
        user_info = UsersDao.get_by_id(g.uid)
        if not user_info:
            raise UserException(f"用户{g.uid}不存在")

        # 更新邮箱并提交事务
        user_info.email = email
        session.commit()

        # 验证通过后删除Redis验证码，防止重复使用
        redis_cache.delete(key)

    def set_allow_notice(self, allow_notice: bool=False):
        key = f"allow_notice:{g.uid}"
        val = redis_cache.get(key)
        if val:
            raise UserException("您的操作太频繁，请稍候再试")
        else:
            redis_cache.setex(name=key, value="1", time=3)
        user_info = UsersDao.get_by_id(g.uid)
        if not user_info:
            raise UserException("用户不存在")
        if not user_info.email:
            raise UserException("您还没有添加邮箱")
        user_info.allow_email_notice = allow_notice
        session.commit()

    def email_verify(self, email: str) -> bool:
        # 1. 校验邮箱格式
        email = email.strip()
        if not email or not EMAIL_REGEX.match(email):
            raise UserException("邮箱地址格式不正确")
        key = f"email_verify_code:{g.uid}:{email}"
        val = redis_cache.get(key)
        if val:
            raise UserException("验证码还在有效期，请勿频繁获取")

        user_info = UsersDao.get_by_id(g.uid)
        if not user_info:
            raise UserException("用户不存在")

        code = self._generate_random_code()
        # 存入redis 有效期5分钟
        redis_cache.setex(key, 5 * 60, code)

        # 同步发送验证码邮件
        send_result = mail_client.send_code_mail(
            receiver_email=email,
            header="挂机系统账号验证",
            mail_title="验证码通知",
            username=user_info.name,
            notice_text="您的验证码如下：",
            verify_code=code,
            item_list=[
                f"触发时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "有效期：5分钟",
                "切勿将验证码泄露给他人"
            ]
        )
        if not send_result:
            raise UserException("验证码邮件发送失败，请稍后重试")

        return True



user_service = UserService()
if __name__ == '__main__':
    # print(user_service._generate_captcha_image(captcha_code="12345"))
    print(user_service.generate_captcha())