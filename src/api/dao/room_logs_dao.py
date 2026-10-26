import json
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, BigInteger, String, DateTime, Integer, Text
from sqlalchemy.orm import declarative_base

from api.api_config import session

Base = declarative_base()


class RoomLogDao(Base):
    __tablename__ = "room_logs"

    log_id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    room_id = Column(BigInteger, nullable=False)
    event_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    event_type = Column(String(30), nullable=False)
    operator_id = Column(Integer)
    operator_name = Column(String(100))
    remark = Column(Text)

    def to_dict(self):
        def fmt_dt(dt):
            return dt.isoformat() if dt else None
        return {
            "log_id": self.log_id,
            "room_id": self.room_id,
            "event_time": fmt_dt(self.event_time),
            "event_type": self.event_type,
            "operator_id": self.operator_id,
            "operator_name": self.operator_name,
            "remark": self.remark
        }

    @classmethod
    def add_log(cls, **kwargs) -> "RoomLogDao":
        try:
            instance = cls(**kwargs)
            session.add(instance)
            session.commit()
            return instance
        except Exception as e:
            session.rollback()
            raise e

    @classmethod
    def get_by_logid(cls, log_id: int) -> Optional["RoomLogDao"]:
        return session.query(cls).filter_by(log_id=log_id).first()

    @classmethod
    def list_by_room(cls, room_id: int, start=None, end=None) -> List["RoomLogDao"]:
        query = session.query(cls).filter_by(room_id=room_id).order_by(cls.event_time.desc())
        if start:
            query = query.filter(cls.event_time >= start)
        if end:
            query = query.filter(cls.event_time <= end)
        return query.all()

    @classmethod
    def list_by_operator(cls, operator_id: int) -> List["RoomLogDao"]:
        return session.query(cls).filter_by(operator_id=operator_id).order_by(cls.event_time.desc()).all()

    def __repr__(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)
