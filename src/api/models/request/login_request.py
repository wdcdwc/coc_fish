# models/login_request.py
from dataclasses import dataclass


@dataclass
class LoginRequest:
    """登录请求参数"""
    username: str
    password: str
    remember_me: bool = False  # 记住我，默认 False

    @classmethod
    def from_dict(cls, data: dict):
        if not data:
            return None
        """从字典创建对象"""
        return cls(
            username=data.get('username', '').strip()[:50],
            password=data.get('password', '').strip()[:50],
            remember_me=data.get('remember_me', False)
        )


    def is_valid(self) -> tuple[bool, str]:
        """
        校验登录参数
        返回：(是否合法, 错误信息)
        """
        # 1. 非空校验
        if not self.username:
            return False, "用户名不能为空"

        if not self.password:
            return False, "密码不能为空"

        # 用户名：长度大于2
        if len(self.username) <= 2:
            return False, "用户名长度必须大于2位"

        # 密码：长度大于6 且 小于等于20 → 7~20位
        if len(self.password) < 6 or len(self.password) > 20:
            return False, "密码长度必须是6~20位"

        # 所有校验通过
        return True, "校验成功"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'username': self.username,
            'password': self.password,
            'remember_me': self.remember_me
        }