from fastapi import APIRouter, Depends, HTTPException, status, Response,Request
from sqlalchemy.orm import Session
from utils.database import get_db
from utils.config import settings
from utils.session import get_session, SessionManager
from models.user import User
import requests
from datetime import datetime

router = APIRouter()

# 谷歌授权url 
@router.get("/get_google_auth_url")
async def get_google_auth_url():
    """返回 Google OAuth URL 而不是直接重定向"""
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?" \
                     f"client_id={settings.GOOGLE_CLIENT_ID}&" \
                     f"response_type=code&" \
                     f"scope=openid%20email%20profile&" \
                     f"redirect_uri={settings.FRONTEND_URL}"
    return {
        "success": True,
        "auth_url": google_auth_url  # 返回 URL 而不是重定向
    }

# 谷歌授权回调
@router.get("/callback") 
async def callback(
    code: str, 
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session),
    response: Response = None,
    ):
    """处理Google OAuth回调"""
    try:
        print('开始处理Google OAuth回调')
        print('code:', code)
        # 获取访问令牌
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"{settings.FRONTEND_URL}"  # 使用前端URL作为重定向地址
        }
        
        # 添加详细的错误日志
        print('Token请求数据:', token_data)
        token_response = requests.post(token_url, data=token_data)
        
        if not token_response.ok:
            print('Token请求失败:', token_response.status_code)
            print('错误响应:', token_response.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get access token from Google"
            )
            
        access_token = token_response.json().get("access_token")

        # 获取用户信息
        userinfo_response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if not userinfo_response.ok:
            print('用户信息请求失败:', userinfo_response.status_code)
            print('错误响应:', userinfo_response.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info from Google"
            )
            
        user_info = userinfo_response.json()

        # 查找或创建用户
        
        # 直接通过邮箱查找用户（因为Gmail用户都是通过Google OAuth创建的）
        user = db.query(User).filter(
            User.email == user_info["email"]
        ).first()

        if not user:
            # 创建新的Google OAuth用户
            # 根据数据库模型，我们只需要设置基本字段
            new_user = User(
                email=user_info["email"],
                password_hash="",  # Google OAuth用户不需要密码
                login_type='google',  # 使用login_type字段标识登录方式
                role='user'
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            user = new_user
            print(f"创建新的Google用户: {user.email}")
        else:
            # 更新现有用户的登录类型为Google（如果之前是其他类型）
            if user.login_type != 'google':
                user.login_type = 'google'
                db.commit()
                print(f"更新用户 {user.email} 的登录类型为Google")

        print(f"为用户 {user.email} (ID: {user.id}) 设置Session。")
        # 登录成功，设置新的session
        session.set("user_id", user.id)
        session.set("user_role", user.role)
        session.set("user_email", user.email)
        session.set("auth_type", "google")
        session.set("login_time", datetime.now().isoformat())  # 添加登录时间戳
        
        # 确保session被保存
        await session.save_session()
        
        # 登录成功后设置 HttpOnly Cookie
        session.set_session_cookie(session.SESSIONID)
        
        # 设置CUSTOMER_CODE Cookie（存储用户email）
        session.set_customer_code_cookie(user.email)
        
        # 设置CUSTOMERID Cookie（存储用户ID）
        session.set_customerid_cookie(user.id)

        return {
            "success": True,
            "code": 200,
            "user": {
                "id": user.id,
                "email": user.email,
            }
        }

    except Exception as e:
        print(f"Google登录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )


# 登录接口
@router.post("/login")
async def login(
    request: Request,
    response: Response,  # 添加Response参数用于设置Cookie
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    """邮箱密码登录"""
    try:
        # 查找用户
        user_data = await request.json()
        print("接收到的登录数据:", user_data.get('email'),user_data.get('password'))
        
        # 修正用户查询逻辑 - 直接查询用户对象
        user = db.query(User).filter(User.email == user_data.get('email')).first()
        
        # 验证用户是否存在
        if not user:
            # 登录失败，清除session和cookie
            session.clear()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="请检查邮箱是否存在"
            )
        
        # 验证密码 - 前端传来的密码已经哈希处理，直接比较
        frontend_hashed_password = user_data.get('password', '')
        if frontend_hashed_password != user.password_hash:
            # 登录失败，清除session和cookie
            session.clear()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="请检查密码是否正确"
            )
        
        # 登录成功，设置新的session
        session.set("user_id", user.id)
        session.set("user_role", user.role)
        session.set("user_email", user.email)
        session.set("auth_type", "email")
        session.set("login_time", datetime.now().isoformat())  # 添加登录时间戳
        
        # 确保session被保存
        await session.save_session()
        
        # 登录成功后设置 HttpOnly Cookie
        session.set_session_cookie(session.SESSIONID)
        
        # 设置CUSTOMER_CODE Cookie（存储用户email）
        session.set_customer_code_cookie(user.email)
        
        # 设置CUSTOMERID Cookie（存储用户ID）
        session.set_customerid_cookie(user.id)
        
        return {
            "success": True,
            "code": 200,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role
            }
        }

    except HTTPException:
        # 重新抛出HTTP异常，不进行额外处理
        raise
    except Exception as e:
        print(f"登录失败: {str(e)}")
        # 其他异常情况下也清除session和cookie
        session.clear()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )

# 登出接口
@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: SessionManager = Depends(get_session)
    ):
    """用户登出 - 要求用户必须处于有效登录状态"""
    try:
        print("🔄 用户请求登出")
        
        # 验证会话ID
        session_id = request.cookies.get("SESSIONID")
        print(f"📝 验证session_id: {session_id}")
        
        # 检查SESSIONID是否存在
        if session_id is None:
            print("❌ 未找到SESSIONID Cookie")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未登录，无需登出"
            )
        
        # 检查SESSIONID是否在Redis中存在（会话是否过期）
        if session.is_session_expired(session_id):
            print(f"🔴 Session已过期: {session_id}")
            # 清除过期的Cookie
            session.clear_expired_cookies()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="会话已过期，无需登出"
            )
        
        print(f"✅ Session验证通过: {session_id}")
        
        # 获取用户信息用于日志
        user_id = session.get("user_id")
        user_email = session.get("user_email", "未知用户")
        customer_code = request.cookies.get("CUSTOMER_CODE", "未知")
        
        print(f"📝 登出用户信息 - ID: {user_id}, 邮箱: {user_email}, CUSTOMER_CODE: {customer_code}")
        
        # 验证用户信息是否完整
        if not user_id:
            print("❌ 用户ID无效")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效"
            )
        
        if not customer_code or customer_code == "未知":
            print("❌ CUSTOMER_CODE无效")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户信息无效"
            )
        
        # 用户处于有效登录状态，执行登出操作
        print(f"✅ 用户 {user_email} 处于有效登录状态，开始登出...")
        
        # 清除session和所有相关Cookie
        session.clear()
        
        print(f"✅ 用户 {user_email} 登出成功，已清除所有session和Cookie")
        
        return {
            "success": True,
            "code": 200,
            "message": "登出成功"
        }
        
    except HTTPException:
        # 重新抛出HTTP异常，让前端知道具体的错误原因
        raise
    except Exception as e:
        print(f"❌ 登出过程中发生未知错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登出失败，请稍后重试"
        )

# 注册接口
@router.post("/register")
async def register(
    request: Request,
    db: Session = Depends(get_db)
    ):
    """用户注册"""
    try:
        user_data = await request.json()
        print("接收到的注册数据:", user_data)  # 添加调试日志

        # 检查邮箱是否已存在
        existing_user = db.query(User).filter(User.email == user_data.get('email')).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="邮箱已被注册"
            )
        
        # 创建新用户
        user = User(
            email=user_data.get('email'),
            password_hash=user_data.get('password'),
            login_type='email',
            role='user'
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return {
            "success": True,
            "code": 200,
            "user": {
                "email": user.email,
            }
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"注册失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )

# 用户身份验证接口
@router.post("/check_user_identity")
async def check_user_identity(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    session: SessionManager = Depends(get_session)
    ):
    """
    验证用户身份状态
    检查用户是否已登录，session是否有效，并返回用户基本信息
    """
    try:
        # 获取请求中的email
        user_data = await request.json()
        user_id = user_data.get('user_id')
        print(f"接收到的用户数据: {user_id}")
        # 验证email是否提供
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供完整信息"
            )
        
        
        # 从数据库中查找用户
        user = db.query(User).filter(User.id == user_id).first()
        print(f"数据库中找到的用户: {user}")
        if not user:
            print(f"❌ 数据库中未找到用户: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        # 返回用户信息
        return {
            "success": True,
            "code": 200,
            "user": {
                "user_id": user.id,
                "user_email": user.email,
                "user_name": user.email.split('@')[0] if '@' in user.email else user.email,
                "role": user.role
            }
            }
        
        
    except HTTPException:
        # 重新抛出HTTP异常，让前端知道具体的错误原因
        raise
    except Exception as e:
        print(f"❌ 身份验证过程中发生未知错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="身份验证失败，请稍后重试"
        )
