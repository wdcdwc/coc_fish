from enum import Enum

class RoomType(Enum):
    TEMPORARY = "temporary"
    MONTHLY = "monthly"

class RoomPermission(Enum):
    MEMBER_ONLY = "member_only"
    SHARE = "share"
    PUBLIC = "public"
    PRIVATE = "private"

    @classmethod
    def is_valid_perm(cls, val: str) -> bool:
        return val in {item.value for item in cls}
