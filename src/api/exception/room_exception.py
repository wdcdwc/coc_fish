# --------------- 父类（统一基础异常）---------------
class RoomException(Exception):
    """用户相关业务异常基类"""
    pass

class RoomNotFoundException(RoomException):
    pass

class PhoneNotFoundException(RoomException):
    pass

class PermissionDeniedException(RoomException):
    """无权操作异常"""
    pass

class ResourceInsufficientException(RoomException):
    """资源不足异常"""
    pass

class IdempotencyException(RoomException):
    pass

class CloudPhoneNotAvailableException(RoomException):
    pass

class ParamInvalidException(RoomException):
    """请求参数不合法异常"""
    pass