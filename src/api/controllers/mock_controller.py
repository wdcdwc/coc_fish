from flask import Blueprint

from api.models.response.response import success

# 创建蓝图（相当于一个"子路由器"）
mock = Blueprint('mock', __name__)


@mock.route('/rooms', methods=['GET'])
def get_rooms():
    data = [
        {
            "id": 11,
            "type": "temporary",
            "name": "爱我中华部落",
            "permission": "member_only",
            "status": "busy"
        },
        {
            "id": 12,
            "type": "monthly",
            "name": "所有人都能用",
            "permission": "everyone",
            "status": "idle"
        },
        {
            "id": 13,
            "type": "monthly",
            "name": "所有人都能用",
            "permission": "everyone",
            "status": "idle"
        },
        {
            "id": 14,
            "type": "monthly",
            "name": "所有人都能用",
            "permission": "everyone",
            "status": "idle"
        },
        {
            "id": 15,
            "type": "monthly",
            "name": "所有人都能用",
            "permission": "everyone",
            "status": "idle"
        },
        {
            "id": 16,
            "type": "monthly",
            "name": "所有人都能用",
            "permission": "everyone",
            "status": "idle"
        },
        {
            "id": 17,
            "type": "monthly",
            "name": "所有人都能用",
            "permission": "everyone",
            "status": "idle"
        },
        {
            "id": 18,
            "type": "monthly",
            "name": "所有人都能用",
            "permission": "everyone",
            "status": "idle"
        },
        {
            "id": 19,
            "type": "monthly",
            "name": "所有人都能用",
            "permission": "everyone",
            "status": "idle"
        },
        {
            "id": 20,
            "type": "monthly",
            "name": "所有人都能用",
            "permission": "everyone",
            "status": "idle"
        }
    ]
    return success(data=data)

@mock.route('/phone', methods=['GET'])
def get_phone():
    # 本地调试用的假数据，替换成你自己的云手机控制台直连地址
    url = "https://console.chinac.com/front/#/CloudMobile/Single?Code=<your-console-code>&ShowBottomBar=false&Resolution=720P"

    return success(data={"url": url})
