"""
ETF预测系统 - 认证模块

提供基于秘钥的身份认证功能，使用FastAPI SessionMiddleware管理会话。
"""
import hashlib
import time
import logging
from datetime import datetime
from fastapi import Request, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Optional
import config

# 创建认证日志记录器
auth_logger = logging.getLogger('auth')
if not auth_logger.handlers:
    # 创建文件处理器
    handler = logging.FileHandler('logs/auth.log', encoding='utf-8')
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    auth_logger.addHandler(handler)
    auth_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# 内存存储登录失败记录 {client_ip: [(timestamp, success), ...]}
login_attempts: Dict[str, list] = {}

# 认证路由器
from fastapi import APIRouter
router = APIRouter()


def verify_key(input_key: str) -> bool:
    """验证输入的秘钥是否正确

    Args:
        input_key: 用户输入的秘钥

    Returns:
        bool: 秘钥是否正确
    """
    try:
        input_hash = hashlib.sha256(input_key.encode()).hexdigest()
        # 使用 hmac.compare_digest 防止时序攻击
        import hmac
        return hmac.compare_digest(input_hash, config.AUTH_KEY_HASH)
    except Exception as e:
        logger.error(f"秘钥验证错误: {e}")
        return False


def check_login_attempts(client_ip: str) -> tuple[bool, Optional[int]]:
    """检查IP地址是否被锁定

    Args:
        client_ip: 客户端IP地址

    Returns:
        (is_locked, remaining_seconds): 是否被锁定及剩余锁定时间
    """
    if client_ip not in login_attempts:
        return False, None

    current_time = time.time()
    # 清理过期的尝试记录
    login_attempts[client_ip] = [
        (ts, success) for ts, success in login_attempts[client_ip]
        if current_time - ts < config.LOGIN_ATTEMPT_WINDOW + config.LOCKOUT_DURATION
    ]

    if not login_attempts[client_ip]:
        del login_attempts[client_ip]
        return False, None

    # 检查时间窗口内的失败次数
    recent_attempts = [
        ts for ts, success in login_attempts[client_ip]
        if current_time - ts < config.LOGIN_ATTEMPT_WINDOW and not success
    ]

    if len(recent_attempts) >= config.MAX_LOGIN_ATTEMPTS:
        # 检查最后一次失败时间，计算剩余锁定时间
        last_failure = max(recent_attempts)
        remaining = config.LOCKOUT_DURATION - (current_time - last_failure)
        if remaining > 0:
            return True, int(remaining)
        else:
            # 锁定时间已过，清除记录
            del login_attempts[client_ip]
            return False, None

    return False, None


def record_login_attempt(client_ip: str, success: bool):
    """记录登录尝试

    Args:
        client_ip: 客户端IP地址
        success: 是否登录成功
    """
    if client_ip not in login_attempts:
        login_attempts[client_ip] = []

    login_attempts[client_ip].append((time.time(), success))

    # 使用专门的认证日志记录器
    if success:
        auth_logger.info(f"登录成功 | IP: {client_ip} | 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        auth_logger.warning(f"登录失败 | IP: {client_ip} | 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    logger.info(f"记录登录尝试: IP={client_ip}, 成功={success}")


async def require_auth(request: Request) -> RedirectResponse | None:
    """检查用户是否已认证，未认证则重定向到登录页

    Args:
        request: FastAPI请求对象

    Returns:
        如果未认证，返回重定向响应；否则返回None
    """
    if not request.session.get("authenticated"):
        # 保存原始URL，登录后跳转回来
        request.session["redirect_after_login"] = str(request.url)
        return RedirectResponse(url="/login", status_code=303)
    return None


async def require_api_auth(request: Request):
    """API路由认证检查依赖

    用于API路由，未认证时返回JSON错误而非重定向

    Args:
        request: FastAPI请求对象

    Raises:
        HTTPException: 401 Unauthorized
    """
    if not request.session.get("authenticated"):
        raise HTTPException(
            status_code=401,
            detail="未认证，请先登录"
        )
    return True


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面 GET 端点"""
    # 如果已经登录，重定向到主页
    if request.session.get("authenticated"):
        return RedirectResponse(url="/", status_code=303)

    # 获取错误消息
    error_msg = request.session.pop("login_error", None)

    return config.templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error_msg
        }
    )


@router.post("/login")
async def login_submit(
    request: Request,
    auth_key: str = Form(..., alias="auth_key")
):
    """登录表单 POST 处理

    Args:
        request: FastAPI请求对象
        auth_key: 用户输入的秘钥
    """
    client_ip = request.client.host if request.client else "unknown"

    # 检查是否被锁定
    is_locked, remaining = check_login_attempts(client_ip)
    if is_locked:
        logger.warning(f"IP {client_ip} 被锁定，尝试登录")
        request.session["login_error"] = f"登录尝试次数过多，请在 {remaining} 秒后重试"
        return RedirectResponse(url="/login", status_code=303)

    # 验证秘钥
    if verify_key(auth_key):
        # 登录成功
        request.session["authenticated"] = True
        request.session["login_time"] = time.time()
        record_login_attempt(client_ip, True)
        logger.info(f"用户登录成功，IP: {client_ip}")

        # 清除失败记录
        if client_ip in login_attempts:
            del login_attempts[client_ip]

        # 跳转到原访问页面或主页
        redirect_url = request.session.pop("redirect_after_login", "/")
        return RedirectResponse(url=redirect_url, status_code=303)
    else:
        # 登录失败
        record_login_attempt(client_ip, False)
        request.session["login_error"] = "秘钥错误，请重试"
        logger.warning(f"用户登录失败，IP: {client_ip}")
        return RedirectResponse(url="/login", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    """登出端点

    清除会话并重定向到登录页
    """
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"用户登出，IP: {client_ip}")
    auth_logger.info(f"用户登出 | IP: {client_ip} | 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
