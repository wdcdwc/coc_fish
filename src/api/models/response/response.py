def success(data=None, message='success'):
    return {
        'code': 200,
        'message': message,
        'data': data
    }

def error(data=None, message='error', code: int = 500):
    return {
        'code': code,
        'message': message,
        'data': data
    }
