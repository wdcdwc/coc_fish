import re


class RegisterRequest:
    username: str
    password: str
    portrait: str | None = None
    captcha_code: str
    captcha_key: str

    @classmethod
    def from_dict(cls, d: dict):
        req = cls()
        req.username = d.get("username", "").strip()
        req.password = d.get("password", "").strip()
        req.portrait = d.get("portrait","小学男生").strip()
        return req
    def is_valid(self) -> tuple[bool, str]:
        # 用户名校验：2-10位，中文、字母、数字、下划线
        if not self.username:
            return False, "用户名不能为空"
        uname_len = len(self.username)
        if uname_len < 2 or uname_len > 10:
            return False, "用户名长度需为2-10位"
        if not re.fullmatch(r'[\u4e00-\u9fa5a-zA-Z0-9_]+', self.username):
            return False, "用户名仅允许中文、字母、数字、下划线"

        # 密码校验：6-20位，字母、数字、特殊字符
        if not self.password:
            return False, "密码不能为空"
        pwd_len = len(self.password)
        if pwd_len < 6 or pwd_len > 20:
            return False, "密码长度需为6-20位"
        return True, ""

