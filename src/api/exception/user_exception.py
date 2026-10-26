# --------------- 父类（统一基础异常）---------------
class UserException(Exception):
    """用户相关业务异常基类"""
    pass

# --------------- 子类（验证码相关）---------------
class CaptchaRequiredException(UserException):
    pass

class CaptchaInvalidException(UserException):
    pass

# --------------- 子类（登录认证相关）---------------
class UserNotFoundException(UserException):
    pass

class PasswordWrongException(UserException):
    pass

# -------------- 注册 --------------------
class UsernameExistException(UserException):
    pass

class ParamInvalidException(UserException):
    pass
