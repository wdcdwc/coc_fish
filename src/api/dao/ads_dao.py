import json
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, String, DateTime, Text, BigInteger
from sqlalchemy.orm import declarative_base

from api.api_config import session

Base = declarative_base()


class AdsDao(Base):
    __tablename__ = "ads"

    # ========== 字段定义 ==========
    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    content = Column(Text, nullable=False)
    ad_type = Column(String(20), nullable=False, default='text')
    created_at = Column(DateTime, default=datetime.utcnow)

    # ========== 实例方法 ==========
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "ad_type": self.ad_type,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    # ========== 类方法 ==========

    @classmethod
    def get_by_id(cls, ad_id: int) -> Optional["AdsDao"]:
        """根据ID获取广告"""
        return session.query(cls).filter_by(id=ad_id).first()

    @classmethod
    def get_all(cls) -> List["AdsDao"]:
        """获取所有广告"""
        return session.query(cls).all()

    @classmethod
    def get_by_type(cls, ad_type: str) -> List["AdsDao"]:
        """根据类型获取广告"""
        return session.query(cls).filter_by(ad_type=ad_type).order_by(cls.id.asc()).all()

    @classmethod
    def get_home_ads(cls) -> List["AdsDao"]:
        """获取首页广告"""
        return session.query(cls).filter_by(ad_type='首页广告').order_by(cls.id.asc()).all()

    @classmethod
    def create(cls, content: str, ad_type: str = 'text') -> "AdsDao":
        """创建新广告"""
        ad = cls(
            content=content,
            ad_type=ad_type
        )
        session.add(ad)
        session.commit()
        return ad

    @classmethod
    def delete(cls, ad_id: int) -> bool:
        """删除广告"""
        ad = cls.get_by_id(ad_id)
        if not ad:
            return False
        session.delete(ad)
        session.commit()
        return True

    # ========== 字符串表示 ==========
    def __repr__(self) -> str:
        return json.dumps(self.to_dict())