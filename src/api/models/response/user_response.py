from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from pydantic import Field

from api.dao.users_dao import UsersDao


@dataclass
class RoomResp():
    """房间信息响应模型"""

    # ========== 基础字段 ==========
    id: int = Field(..., description="房间ID")
    rname: str = Field(..., description="房间名称", max_length=100)
    type: str = Field(..., description="房间类型: temporary-临时房间, monthly-包月房间")
    permission: str = Field(..., description="权限类型: private-私有, public-公共, whitelist-白名单")
    phone_id: str = Field(..., description="分配的云手机ID", max_length=50)

    # ========== 用户相关字段 ==========
    owner: Optional[int] = Field(None, description="房主用户ID")
    current_user: Optional[int] = Field(None, description="当前使用者用户ID")
    current_user_name: Optional[str] = Field(None, description="当前使用者用户名称", max_length=50)  # ✅ 改为 Optional

    # ========== 权限相关 ==========
    white_list: Optional[str] = Field(None, description="白名单(JSON格式或逗号分隔的用户ID)")

    # ========== 时间字段 ==========
    end_time: Optional[datetime] = Field(None, description="房间关闭时间")
    create_time: datetime = Field(..., description="创建时间")

    # ========== Pydantic 配置 ==========
    class Config:
        from_attributes = True  # Pydantic v2 支持 ORM 对象转换
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

    # ========== 实例方法 ==========
    @classmethod
    def from_orm(cls, room) -> "RoomResp":
        """从ORM对象创建响应对象"""
        current_user_name = None
        if room.current_user:
            user = UsersDao.get_by_id(room.current_user)
            current_user_name = user.name if user else None  # ✅ 增加空值判断

        return cls(
            id=room.id,
            rname=room.rname,
            type=room.type,
            permission=room.permission,
            phone_id=room.phone_id,
            owner=room.owner,
            current_user=room.current_user,
            current_user_name=current_user_name,
            white_list=room.white_list,
            end_time=(room.end_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S") if room.end_time else None,
            create_time=(room.create_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
        )
