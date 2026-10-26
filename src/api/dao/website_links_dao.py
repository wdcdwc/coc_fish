import json
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, DateTime, BigInteger
from sqlalchemy.orm import declarative_base

from api.api_config import session

Base = declarative_base()


class WebsiteLinksDao(Base):
    __tablename__ = "website_links"

    # 字段定义，完全对齐你PostgreSQL建表语句
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    link_name = Column(String(128), nullable=False)
    url = Column(Text, nullable=False)
    remark = Column(Text, nullable=True)
    create_at = Column(DateTime, default=datetime.utcnow)
    update_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 转为字典序列化
    def to_dict(self):
        return {
            "id": self.id,
            "link_name": self.link_name,
            "url": self.url,
            "remark": self.remark,
            "create_at": self.create_at.isoformat() if self.create_at else None,
            "update_at": self.update_at.isoformat() if self.update_at else None
        }

    # 根据主键ID查询单条
    @classmethod
    def get_by_id(cls, link_id: int) -> Optional["WebsiteLinksDao"]:
        return session.query(cls).filter_by(id=link_id).first()

        # 根据主键ID查询单条
    @classmethod
    def get_by_name(cls, link_name: str) -> Optional["WebsiteLinksDao"]:
        return session.query(cls).filter_by(link_name=link_name).first()

    # 查询全部链接
    @classmethod
    def get_all(cls):
        return session.query(cls).all()

    # 新增一条链接
    @classmethod
    def create(cls, link_name: str, url: str, remark: str = None):
        new_link = cls(
            link_name=link_name,
            url=url,
            remark=remark
        )
        session.add(new_link)
        session.commit()
        return new_link

    # 根据id删除链接
    @classmethod
    def delete_by_id(cls, link_id: int):
        item = cls.get_by_id(link_id)
        if item:
            session.delete(item)
            session.commit()
        return item

    # 字符串打印
    def __repr__(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)
