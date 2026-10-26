from gevent.monkey import patch_all
from gevent.pywsgi import WSGIServer

patch_all()
import sys
import os
import time

# ===== 设置路径（必须用 sys.path.insert） =====
src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_path = os.path.join(src_path, '../')

if src_path not in sys.path:
    sys.path.insert(0, src_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)
    # print(root_path)

import traceback
import jwt
from flask import Flask, request, g, jsonify
from flask_cors import CORS

from api.api_config import SECRET_KEY, ALGORITHM, DATABASE_URL, RateLimiter, session
from api.controllers.mock_controller import mock
from api.controllers.phone_controller import phone
from api.controllers.room_controller import room
from api.controllers.user_controller import user
from api.models.response.response import error
from src.my_logger import logger
from src.redis_client import redis_cache

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization", "Token", "captcha-token"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)
app.register_blueprint(mock, url_prefix='/mock')
app.register_blueprint(user, url_prefix='/user')
app.register_blueprint(room, url_prefix='/room')
app.register_blueprint(phone, url_prefix='/phone')


# 每次请求进来：打印auth调试日志（对应 2026-xx-xx - DEBUG - auth=xxx）
@app.before_request
def print_auth_log():
    auth_val = request.headers.get("Authorization", "None")
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} - DEBUG - auth={auth_val}")


@app.before_request
def jwt_token_filter():
    white_paths = {"/login", "/register", '/captcha/verify', '/captcha', "/ping", "/user/name", "/room/list", "/room/ads", "/room/url"}
    for path in white_paths:
        if request.path.endswith(path) or request.path.startswith(path):

            if request.headers.get("Captcha-Token"):
                return

            if path == "/login":
                ip_key = "login_ip_limiter:" + str(request.remote_addr)
                RateLimiter.incr(key=ip_key, redis_cli=redis_cache, window_sec=1)
                if RateLimiter.get_count(key=ip_key, redis_cli=redis_cache, window_sec=1) > 3:
                    redis_cache.sadd("waning:ip", request.remote_addr)
                    current_ttl = redis_cache.ttl("waning:ip")
                    if current_ttl < 10:
                        redis_cache.expire("waning:ip", 10)
                    return error(message="需要进行验证码校验", code=40301)
                else:
                    return
            RateLimiter.incr(key="filter_limiter:" + path, redis_cli=redis_cache, window_sec=3)
            if RateLimiter.get_count(key="filter_limiter:" + path, redis_cli=redis_cache, window_sec=1) > 400:
                return error(message="服务繁忙", code=429)
            else:
                return

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        logger.debug(f"auth={auth}")
        return error(message="未登录，请登录", code=401)
    token = auth.split(" ")[1]

    if redis_cache.sismember("black_token", token):
        logger.debug(f"auth={auth}")
        return error(message="未登录，请登录", code=401)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        g.uid = payload["uid"]
        g.uname = payload["uname"]
        key = "user_limiter:" + str(g.uid)
        RateLimiter.incr(key, redis_cli=redis_cache, window_sec=1)
        if RateLimiter.get_count(key, redis_cli=redis_cache, window_sec=1) > 4:
            return error(message="操作频繁，请稍候再试", code=429)
    except Exception as e:
        logger.error(e, exc_info=True)
        return error(message="Token失效或错误", code=401)


# 请求结束后：打印标准Nginx/Werkzeug格式访问日志
@app.after_request
def record_access_log(resp):
    # 格式化日期：28/Jul/2026 21:45:03
    time_fmt = time.strftime("%d/%b/%Y %H:%M:%S")
    method = request.method
    full_path = request.full_path.rstrip('?')
    status_code = resp.status_code
    client_ip = request.remote_addr or "127.0.0.1"
    # 日志格式完全对齐本地输出
    print(f'{client_ip} - - [{time_fmt}] "{method} {full_path} HTTP/1.1" {status_code} -')
    return resp


@app.teardown_request
def close_session(exception=None):
    session.remove()


@app.errorhandler(Exception)
def handle_global_exception(e):
    stack_trace = traceback.format_exc()
    print(f"异常信息: {str(e)}")
    print(f"堆栈信息:\n{stack_trace}")
    app.logger.error(f"异常: {str(e)}\n堆栈: {stack_trace}")
    return jsonify({
        'error': 'Internal Server Error',
        'message': str(e),
        'path': request.path
    }), 500


@app.route('/ping')
def ping():
    return "pong"

# 程序入口
if __name__ == '__main__':
    if not SECRET_KEY or not DATABASE_URL:
        raise SystemExit("请先配置环境变量 COC_JWT_SECRET_KEY 与 COC_DATABASE_URL（参考 .env.example）")
    # app.run(host='0.0.0.0', port=8848, debug=False, threaded=True)
    server = WSGIServer(("0.0.0.0", 8848), app)
    logger.info("服务启动 0.0.0.0:8848")
    server.serve_forever()
