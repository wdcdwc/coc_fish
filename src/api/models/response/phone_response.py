from pydantic import BaseModel
from typing import List, Optional

from api.dao.cloud_phone_dao import CloudPhonesDao


# 单台云手机返回体
class PhoneInfoResponse(BaseModel):
    id: str
    region: str
    resolution: str
    status: str
    created_at: Optional[str]

    # ORM对象自动转模型
    @classmethod
    def from_dao(cls, dao_obj: CloudPhonesDao):
        return cls(
            id=dao_obj.id,
            region=dao_obj.region,
            resolution=dao_obj.resolution,
            status=dao_obj.status,
            created_at=dao_obj.created_at.isoformat() if dao_obj.created_at else None
        )

# 批量列表返回体
class PhoneListResponse(BaseModel):
    data: List[PhoneInfoResponse]
    total: int

    @classmethod
    def from_dao_list(cls, dao_list: list[CloudPhonesDao]):
        item_list = [PhoneInfoResponse.from_dao(item) for item in dao_list]
        return cls(data=item_list, total=len(item_list))
