import json
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import declarative_base

from api.api_config import session

Base = declarative_base()
class CloudPhonesDao(Base):
    __tablename__ = "cloud_phones"

    # ========== 字段定义 ==========
    id = Column(String(50), primary_key=True, nullable=False)
    region = Column(String(50), nullable=False)
    resolution = Column(String(20), nullable=False)
    address = Column(String(50), nullable=False)
    status = Column(String(20), default='active')
    created_at = Column(DateTime, default=datetime.utcnow)

    # ========== 实例方法 ==========
    def to_dict(self):
        return {
            "id": self.id,
            "region": self.region,
            "resolution": self.resolution,
            "address": self.address,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    # ========== 类方法 ==========

    @classmethod
    def get_by_id(cls, phone_id: str) -> Optional["CloudPhonesDao"]:
        return session.query(cls).filter_by(id=phone_id).first()

    @classmethod
    def get_all(cls):
        return session.query(cls).all()

    @classmethod
    def get_idles(cls):
        return session.query(cls).filter_by(status="idle").all()

    # ========== 字符串表示 ==========
    def __repr__(self):
        return json.dumps(self.to_dict())


