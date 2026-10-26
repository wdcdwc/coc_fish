class GameException(Exception):
    pass

class BattleInterruptError(GameException):
    pass

class OperationConflictException(GameException):
    """操作冲突异常"""
    pass

class GameAssistNotFoundException(GameException):
    """游戏辅助信息不存在异常"""
    default_code = 10301
    default_message = "游戏辅助信息不存在"

class LinkTimeoutException(GameException):
    pass