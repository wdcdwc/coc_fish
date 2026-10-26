from flask import Blueprint, request, Response, g

from api.exception.room_exception import RoomException
from api.exception.user_exception import UserException
from api.models.request.room_request import CreateRoomRequest
from api.models.response.response import error, success
from api.services.enter_room_service import enter_room_service
from api.services.room_fish_service import room_action_service
from api.services.room_service import room_service, RoomService
from src.my_logger import logger

room = Blueprint('room', __name__)

@room.route('/list', methods=['GET'])
def room_list():
    try:
        res = room_service.room_list()
        return success(data=res)
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route("/sse/<int:room_id>", methods=['GET'])
def subscribe_sse(room_id):
    print(f"进入subscribe_sse")
    if room_id is None:
        logger.error(f"Room id is None")
        return error(message="参数不合法")
    resp = Response(
        room_service.sse_stream(room_id, uid = g.uid),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # "Connection": "close", # WSGI 规范（PEP 3333）禁止应用层设置这个头
            "Access-Control-Allow-Origin": "*",  # 手动添加 CORS 头
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        }
    )
    return resp

@room.route('/message', methods=['POST'])
def send_message():
    request_data = request.get_json()
    RoomService.send_room_msg(room_id=request_data["room_id"], target_user_id=request_data["user_id"] ,
                              type=request_data["type"],msg=request_data["message"])
    return success(message="发送成功")

@room.route('/apply-operate', methods=['PUT'])
def apply_operate():
    request_data = request.get_json()
    try:
        res = room_service.apply_operate(room_id=request_data["room_id"])
        return success(data=res)
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/init/', methods=['POST'])
def get_room():
    body = request.get_json()
    try:
        return success(data=enter_room_service.get_room(room_id = body.get('room_id'), room_name = body.get('room_name')))
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/hit_fish', methods=['POST'])
def hit_fish():
    body = request.get_json()
    room_id = body.get('room_id')
    is_aboard_version = body.get('aboard')
    ranking = body.get('ranking')
    logger.debug(f"hit fish room_id:{room_id} is_aboard_version:{is_aboard_version}")
    if room_id is None:
        logger.error(f"Room id is None")
        return error(message="房间不存在")
    try:
        res = room_action_service.exec_hit_fish(room_id, is_aboard_version=is_aboard_version, ranking=ranking)
        if res is None or not res:
            return error("打鱼失败，请查看具体日志")
        else:
            return success(data=res)
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/hit_fish_dark', methods=['POST'])
def hit_fish_dark():
    body = request.get_json()
    room_id = body.get('room_id')
    is_aboard_version = body.get('aboard')
    logger.debug(f"hit fish dark room_id:{room_id} is_aboard_version:{is_aboard_version}")
    if room_id is None:
        logger.error(f"Room id is None")
        return error(message="房间不存在")
    try:
        res = room_action_service.exec_hit_fish_dark(room_id, is_aboard_version=is_aboard_version)
        print(f"返回结果为：{res}")
        if res is None or not res:
            return error("打鱼失败，请查看具体日志")
        else:
            return success(data=res)
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route("/is-fish/<int:room_id>", methods=['GET'])
def is_fish(room_id):
    try:
        return success(data=room_action_service.is_hit_fish_thread_alive(room_id))
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/hit_fish', methods=['PUT'])
def stop_fish():
    try:
        body = request.get_json()
        room_id = body.get('room_id')
        res = room_action_service.stop_hit_fish(room_id)
        return success(data=res)
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/hit_fish_dark', methods=['PUT'])
def stop_fish_dark():
    try:
        body = request.get_json()
        room_id = body.get('room_id')
        res = room_action_service.stop_hit_fish(room_id)
        return success(data=res)
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/create', methods=['POST'])
def create_room():
    try:
        body = request.get_json()
        c_r = CreateRoomRequest(body.get('room_name'), body.get('phone_id'), body.get('type'), body.get('permission'), body.get('duration'))
        if c_r.is_valid():
            res = room_service.create_room(c_r)
            if res is None:
                return error(message="创建房间失败")
            else:
                return success(data=res)
        else:
            return error(message="参数不合法", code=400)

    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/leave/<int:room_id>', methods=['POST'])
def leave_room(room_id):
    try:
        res = room_service.leave_room(room_id)
        return success(data=res)
    except RoomException as e:
        logger.error(e, exc_info=True)
        return error(message=str(e))
    except Exception as e:
        logger.error(e, exc_info=True)
    return error(message="服务器内部错误", code=500)

@room.route('/task/status/<int:room_id>', methods=['GET'])
def task_status(room_id):
    try:
        res = room_action_service.get_task_status(room_id)
        return success(data=res)
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
    return error(message="服务器内部错误", code=500)

@room.route('/formate', methods=['POST'])
def formate_village():
    request_data = request.get_json()
    try:
        res = room_action_service.build_formation(room_id=request_data["room_id"], shell_url=request_data["url"])
        return success(data=res)
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/white_list', methods=['POST'])
def add_white_list():
    request_data = request.get_json()
    try:
        res = room_service.update_room_white_list(room_id=request_data["room_id"], d_uids=request_data["white_uid_list"])
        return success(data=res)
    except (RoomException, UserException) as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/white_list/<int:room_id>', methods=['GET'])
def get_white_list(room_id):
    try:
        res = room_service.get_room_white_list(room_id)
        return success(data=res)
    except (RoomException, UserException) as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/white_list/apply', methods=['POST'])
def apply_white_list():
    request_data = request.get_json()
    try:
        res = room_service.apply_white_list(room_id=request_data["room_id"])
        return success(data=res)
    except (RoomException, UserException) as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/permission', methods=['PUT'])
def update_permission():
    request_data = request.get_json()
    try:
        res = room_service.update_room_permission(room_id=request_data["room_id"], permission=request_data["permission"])
        return success(data=res)
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)


@room.route('/rname', methods=['PUT'])
def update_name():
    request_data = request.get_json()
    try:
        res = room_service.update_room_name(room_id=request_data["room_id"],
                                                  new_name=request_data["rname"])
        return success(data=res)
    except RoomException as e:
        logger.error(e)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/refresh/<int:room_id>', methods=['POST'])
def refresh(room_id):
    try:
        room_action_service.refresh_scrcpy(room_id)
        return success()
    except RoomException as e:
        logger.error(e, exc_info=True)
        return error(message=str(e))
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/url/<name>', methods=['GET'])
def bug_report_url(name:str):
    try:
        url = room_action_service.get_url(name)
        return success(data=url)
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route('/ads/<type>', methods=['GET'])
def get_ads(type):
    try:
        res = room_service.get_ads(type)
        return success(data=res)
    except Exception as e:
        logger.error(e)
        return error(message="服务器内部错误", code=500)

@room.route("/solders", methods=['POST'])
def specific_fish_solders():
    request_data = request.get_json()
    try:
        room_action_service.specific_fish_solders(request_data["room_id"], request_data["solder_name"])
        return success()
    except RoomException as e:
        logger.error(e)
        return error(message=str(e), code=500)
    except Exception as e:
        logger.error(e, exc_info=True)
        return error(message="服务器内部错误", code=500)
