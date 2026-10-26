import json
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Integer, Text, event
from sqlalchemy.orm import declarative_base

from api.api_config import session, MEMBER_ONLY_USE_HOURS
from api.models.my_enum import RoomPermission
from src.redis_client import redis_cache
from src.my_logger import logger

Base = declarative_base()

class RoomsDao(Base):
    __tablename__ = "rooms"

    # ========== 字段定义 ==========
    id = Column(Integer, primary_key=True, autoincrement=True)
    rname = Column(String(100), nullable=False)
    type = Column(String(20), default='temporary')   #temporary-可进入 closed-已下架
    permission = Column(String(30), default='private')  #权限 仅部落成员、公共， 白名单
    phone_id = Column(String(50), nullable=False)  # 分配的云手机ID
    owner = Column(Integer, nullable=True)  # 房间的房主
    current_user = Column(Integer, nullable=True)  # 房间的当前使用者
    white_list = Column(Text, nullable=True)
    end_time = Column(DateTime)  # 房间关闭的时间
    create_time = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fish_server = Column(String(100), default='cn')  # 鱼服务器标识，默认cn

    # ========== 实例方法 ==========
    def to_dict(self):
        return {
            "id": self.id,
            "rname": self.rname,
            "type": self.type,
            "permission": self.permission,
            "phone_id": self.phone_id,
            "owner": self.owner,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    # ========== 类方法 ==========
    @classmethod
    def add_to_db(cls, room: Optional["RoomsDao"]) -> Optional[int]:
        """更新房间信息到数据库（仅更新已存在的记录）

            Args:
                room: 要更新的房间对象（必须包含id）

            Returns:
                更新成功返回房间ID，失败返回None
            """
        try:
            session.add(room) # 如果id不存在，会插入新记录！
            session.commit()
            session.refresh(room)
            return room.id
        except Exception as e:
            logger.error(e, exc_info=True)
            session.rollback()
            return None

    @classmethod
    def get_by_id(cls, room_id: int) -> Optional["RoomsDao"]:
        return session.query(cls).filter_by(id=room_id).first()

    @classmethod
    def get_by_phone_id(cls, pid: str):
        return session.query(cls).filter_by(phone_id=pid).first()

    @classmethod
    def get_by_owner(cls, owner_id: str):
        return session.query(cls).filter_by(owner=owner_id).all()

    @classmethod
    def get_all(cls):
        return session.query(cls).filter(cls.type != 'closed').all()

    # ========== 字符串表示 ==========
    def __repr__(self):
        return json.dumps(self.to_dict())