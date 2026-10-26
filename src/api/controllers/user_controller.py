from flask import Blueprint, request
from psycopg2.errors import UniqueViolation

from api.exception.user_exception import UserException
from api.models.request.login_request import LoginRequest
from api.models.request.register_request import RegisterRequest
from api.models.response.response import error, success
from api.services.user_service import user_service
from src.my_logger import logger

user = Blueprint('user', __name__)

@user.route('/login', methods=['POST'])
def login():
    request_data = request.get_json()
    login_request = LoginRequest.from_dict(request_data)
    if login_request:
        valid, msg = login_request.is_valid()
        if not valid:
            return error(message=msg, code=400)
        try:
            res, data = user_service.login(login_request)
            if not res:
                return error(message=data, code=400)
            else:
                return success(data=data)
        except UserException as e:
            return error(message=str(e), code=400)
        except Exception as e:
            logger.error(e,exc_info=True)
            return error(message="服务器内部错误", code=500)

@user.route('/register', methods=['POST'])
def register():
    request_data = request.get_json()
    register_req = RegisterRequest.from_dict(request_data)
    valid, msg = register_req.is_valid()
    if not valid:
        return error(message=msg, code=400)
    try:
        res, data = user_service.register(register_req)
        if not res:
            return error(message=data, code=400)
        return success(message=data, data=res)
    except UserException as e:
        logger.error(e, exc_info=True)
        return error(message=str(e), code=400)
    except UniqueViolation as e:
        logger.error(str(e), code=400,exc_info=True)
        return error(message=str(e), code=400)
    except Exception as e:
        logger.error(e, exc_info=True)
        return error(message="服务器内部错误", code=500)

@user.route('/name', methods=['POST'])
def check_name():
    try:
        res = user_service.check_user_name(request.get_json().get("username"))
        return success(data=res)
    except UserException as e:
        logger.error(e, exc_info=True)
        return error(message=str(e), code=400)
    except Exception as e:
        logger.error(e, exc_info=True)
        return error(message="服务器内部错误", code=500)

@user.route('/captcha', methods=['GET'])
def get_captcha():
    """
    获取验证码接口
    返回: 验证码图片(base64) 和 captcha_key
    """
    try:
        # 调用service层生成验证码
        result = user_service.generate_captcha()

        if result:
            return success(
                data=result,
                message="获取验证码成功"
            )
        else:
            return error(message="生成验证码失败")

    except Exception as e:
        logger.error(f"获取验证码失败: {e}")
        return error(message="获取验证码失败")

@user.route('/captcha/verify', methods=['POST'])
def verify_captcha():
    """
    验证验证码接口
    请求参数: {"captcha_key": "xxx", "captcha_code": "xxx"}
    """
    try:
        data = request.get_json()
        captcha_key = data.get('captcha_key')
        captcha_code = data.get('captcha_code')

        if not captcha_key or not captcha_code:
            return error(message="参数不完整")

        # 调用service层验证
        token = user_service.verify_captcha(captcha_key, captcha_code)

        if token:
            return success(data=token, message="验证码正确")
        else:
            return error(message="验证码错误或已过期")

    except Exception as e:
        logger.error(f"验证验证码失败: {e}")
        return error(message="验证失败")

@user.route('/info', methods=['GET'])
def get_info():
    try:
        return user_service.get_info()
    except UserException as e:
        logger.error(str(e), exc_info=True)
        return error(message=str(e), code=500)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return error(message="服务器内部错误", code=500)

@user.route('/info/name/<display_uid>', methods=['GET'])
def get_name(display_uid):
    try:
        map = user_service.get_name_by_display_uid(display_uid)
        return success(data=map)
    except UserException as e:
        logger.error(str(e), exc_info=True)
        return error(message=str(e), code=500)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return error(message="服务器内部错误", code=500)

@user.route('/rooms', methods=['GET'])
def get_rooms():
    try:
        room_list = user_service.get_rooms()
        return success(data=room_list)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return error(message="服务器内部错误", code=500)

@user.route('/password', methods=['PUT'])
def update_password():
    try:
        data = request.get_json()
        res, msg = user_service.update_user_password(new_password=data.get('new_password'), old_password=data.get('old_password'))#返回tuple[bool, str]
        if not res:
            return error(message=msg, code=400)
        return success(data=res)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return error(message="服务器内部错误", code=500)

@user.route('/change-name', methods=['PUT'])
def update_username():
    try:
        data = request.get_json()
        res, msg = user_service.update_user_name(username=data.get('username'))#返回tuple[bool, str]
        if not res:
            return error(message=msg, code=400)
        return success(data=res)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return error(message="服务器内部错误", code=500)


@user.route('/logout', methods=['POST'])
def logout():
    try:
        res = user_service.logout()#返回bool
        return success(data=res)
    except UserException as e:
        logger.error(str(e), exc_info=True)
        return error(message=str(e), code=500)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return error(message="服务器内部错误", code=500)

@user.route('/email', methods=['POST'])
def use_email():
    try:
        data = request.get_json()
        user_service.set_email(data.get('email'), data.get('verify_code'))
        return success(data={"email": data.get('email')})
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return error(message=str(e), code=500)

@user.route('/allow-notice', methods=['POST'])
def allow_notice():
    try:
        data = request.get_json()
        user_service.set_allow_notice(data.get('allow_notice'))
        return success(data={"email": data.get('email')})
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return error(message=str(e), code=500)



@user.route('/email-verify', methods=['POST'])
def verify_email():
    try:
        data = request.get_json()
        res = user_service.email_verify(data.get('email'))
        return success(data=res)
    except UserException as e:
        logger.error(str(e), exc_info=True)
        return error(message=str(e), code=500)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return error(message="系统内部错误", code=500)


