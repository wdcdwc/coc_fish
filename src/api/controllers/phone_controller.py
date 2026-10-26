from flask import Blueprint

from api.dao.cloud_phone_dao import CloudPhonesDao

phone = Blueprint('phone', __name__)

@phone.get("/list")
def list():
    phones = CloudPhonesDao.get_all()
    resp = []
    for phone in phones:
        resp.append(phone.to_dict())
    return resp