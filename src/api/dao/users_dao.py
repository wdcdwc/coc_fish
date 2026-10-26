import json
from datetime import datetime
from typing import Optional

import bcrypt
from sqlalchemy import Column, BigInteger, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base

from api.api_config import session

Base = declarative_base()


class UsersDao(Base):
    __tablename__ = "users"

    # ========== 字段定义 ==========
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    portrait = Column(String(500))
    email = Column(String(100))
    # 新增：是否允许邮件通知，默认开启
    allow_email_notice = Column(Boolean, nullable=False, default=False)
    display_uid = Column(String(20), nullable=False)
    total_duration = Column(BigInteger, nullable=False, default=0)
    create_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_time = Column(DateTime)
    is_deleted = Column(Boolean, nullable=False, default=False)

    # ========== 实例方法 ==========
    def to_dict(self):
        """转换为字典（返回给前端）"""
        return {
            'id': self.id,
            'name': self.name,
            'portrait': self.portrait,
            'email': self.email,
            'allow_email_notice': self.allow_email_notice,
            'display_uid': self.display_uid,
            'total_duration': self.total_duration,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'last_login_time': self.last_login_time.isoformat() if self.last_login_time else None
        }

    def set_password(self, password):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def set_email(self, email_addr: str):
        self.email = email_addr.strip() if email_addr else None

    # 快捷开关通知
    def toggle_email_notice(self, status: bool):
        self.allow_email_notice = status

    @classmethod
    def get_by_name(cls, name) -> Optional["UsersDao"]:
        return session.query(cls).filter_by(name=name, is_deleted=False).first()

    @classmethod
    def get_by_id(cls, uid) -> Optional["UsersDao"]:
        return session.query(cls).filter_by(id=uid, is_deleted=False).first()

    @classmethod
    def get_by_display_uid(cls, display_uid) -> Optional["UsersDao"]:
        return session.query(cls).filter_by(display_uid=display_uid, is_deleted=False).first()

    @classmethod
    def get_by_email(cls, email_addr: str) -> Optional["UsersDao"]:
        return session.query(cls).filter_by(email=email_addr, is_deleted=False).first()

    @classmethod
    def batch_get_by_id(cls, uid_list: list[int]) -> dict[int, Optional["UsersDao"]]:
        if not uid_list:
            return {}
        rows = session.query(cls).filter(
            cls.id.in_(uid_list),
            cls.is_deleted == False
        ).all()
        result_map = {row.id: row for row in rows}
        return result_map

    @classmethod
    def batch_get_by_display_uid(cls, display_uid_list: list[str]) -> dict[str, Optional["UsersDao"]]:
        if not display_uid_list:
            return {}
        rows = session.query(cls).filter(
            cls.display_uid.in_(display_uid_list),
            cls.is_deleted == False
        ).all()
        result_map = {row.display_uid: row for row in rows}
        return result_map

    @classmethod
    def get_active_users(cls):
        return session.query(cls).filter_by(is_deleted=False).all()

    def __repr__(self):
        return json.dumps(self.to_dict())


users_dao = UsersDao()

if __name__ == '__main__':
    print(type(users_dao.get_active_users()[0]))
