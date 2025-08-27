from fastapi import APIRouter, Depends, HTTPException, status, Response,Request
from sqlalchemy.orm import Session
from utils.database import get_db
from utils.config import settings
from utils.session import get_session, SessionManager
from models.user import User
import requests
from datetime import datetime

router = APIRouter()

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
                code=status.HTTP_401_UNAUTHORIZED,
                detail="请检查邮箱是否存在"
            )
        
        # 验证密码 - 前端传来的密码已经哈希处理，直接比较
        frontend_hashed_password = user_data.get('password', '')
        if frontend_hashed_password != user.password_hash:
            # 登录失败，清除session和cookie
            session.clear()
            raise HTTPException(
                code=status.HTTP_401_UNAUTHORIZED,
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
        
        return {
            "success": True,
            "code": 200,
            "user": {
                "id": user.id,
                "email": user.email,
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
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
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
                code=status.HTTP_409_CONFLICT,
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
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )
   

# 验证用户是否登录的接口
@router.get("/check_login")
async def check_login(
    session: SessionManager = Depends(get_session)
    ):
    try:
        # 检查用户是否已登录
        user_email = session.get("user_email")
        user_id = session.get("user_id")
        
        if not user_email or not user_id:
            return {
                "success": False,
                "msg": "登录状态已过期，请重新登录以继续操作"
            }

        # 获取用户信息
        user_role = session.get("user_role")
        login_time = session.get("login_time")

        return {
            "success": True,
            "user_email": user_email,
            "user_role": user_role,
            "login_time": login_time,
            "customer_code": session.get_customer_code()
        }

    except Exception as e:
        print(f"获取用户信息失败: {str(e)}")
        raise HTTPException(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败，请重新登录"
        )


@router.get("/check-permission")
def check_permission(session: SessionManager = Depends(get_session)):
    # 假设 user["permissions"] 是权限列表
    user_role = session.get("user_role")
    if user_role != "admin":
        return {
            "success": False,
            "msg": "权限不足",
        }
    else:
        return {"success": True}



# 登出接口
@router.post("/logout")
async def logout(
    response: Response,
    session: SessionManager = Depends(get_session)
):
    """用户登出"""
    try:
        # 清除session数据
        session.clear()
        return {
            "success": True,
            "code": 200,
            "msg": "登出成功"
        }
    except Exception as e:
        print(f"登出失败: {str(e)}")
        raise HTTPException(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登出失败，请稍后重试"
        )


