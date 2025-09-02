import redis
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Request, Response, HTTPException
from utils.config import settings

# Redis连接
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=True
)

def test_redis_connection():
    """测试Redis连接"""
    try:
        redis_client.ping()
        print("✅ Redis连接成功")
        return True
    except Exception as e:
        print(f"❌ Redis连接失败: {str(e)}")
        print("请检查Redis服务是否启动，或检查配置是否正确")
        return False

class SessionManager:
    def __init__(self, request: Request = None, response: Response = None):
        self.request = request
        self.response = response
        self.SESSIONID = None
        self.CUSTOMER_CODE = None  # 添加CUSTOMER_CODE属性
        self.CUSTOMERID = None  # 添加CUSTOMERID属性
        self.session_data = {}
    
    def is_session_expired(self, session_id: str) -> bool:
        """
        检查session是否已过期
        通过检查Redis中是否存在该session来判断
        """
        try:
            # 检查Redis中是否存在该session
            exists = redis_client.exists(f"session:{session_id}")
            return not exists
        except Exception as e:
            print(f"检查session过期状态失败: {str(e)}")
            # 如果Redis连接失败，认为session已过期
            return True
    
    def clear_expired_cookies(self):
        """
        清除过期的Cookie
        当检测到session过期时，主动删除浏览器中的Cookie
        """
        if not self.response:
            return
            
        try:
            print("🔄 检测到session已过期，正在清除浏览器Cookie...")
            
            # 删除SESSIONID Cookie
            self.response.delete_cookie(
                "SESSIONID",
                domain=settings.SESSION_COOKIE_DOMAIN,
                path="/"
            )
            
            # 删除CUSTOMER_CODE Cookie
            self.response.delete_cookie(
                "CUSTOMER_CODE",
                domain=settings.SESSION_COOKIE_DOMAIN,
                path="/"
            )
            
            # 删除CUSTOMERID Cookie
            self.response.delete_cookie(
                "CUSTOMERID",
                domain=settings.SESSION_COOKIE_DOMAIN,
                path="/"
            )
            
            print("✅ 过期Cookie清除完成")
        except Exception as e:
            print(f"清除过期Cookie失败: {str(e)}")
    
    def set_session_cookie(self, session_id: str = None):
        """
        统一的设置会话Cookie的方法
        支持 HttpOnly、Secure、SameSite 等安全配置
        """
        if not self.response:
            return

        # 如果没有传入 session_id，使用当前的 SESSIONID
        if session_id is None:
            session_id = self.SESSIONID

        if not session_id:
            return

        try:
            # 设置安全的 HttpOnly Cookie
            self.response.set_cookie(
                key="SESSIONID",
                value=session_id,
                max_age=settings.SESSION_EXPIRE_SECONDS,
                domain=settings.SESSION_COOKIE_DOMAIN,
                path="/",
                secure=settings.SESSION_COOKIE_SECURE,
                samesite=settings.SESSION_COOKIE_SAMESITE,
                httponly=True
            )
        except Exception as e:
            print(f"设置Cookie失败: {str(e)}")
    
    def set_customer_code_cookie(self, email: str):
        """
        设置CUSTOMER_CODE Cookie的方法
        """
        if not self.response or not email:
            return

        try:
            # 设置CUSTOMER_CODE属性
            self.CUSTOMER_CODE = email
            print(email)
            print(f"🔧 设置CUSTOMER_CODE Cookie - 原始值: '{self.CUSTOMER_CODE}'")
            
            # 设置CUSTOMER_CODE Cookie（非HttpOnly，允许前端访问）
            self.response.set_cookie(
                key="CUSTOMER_CODE",
                value=email,
                max_age=settings.SESSION_EXPIRE_SECONDS,
                domain=settings.SESSION_COOKIE_DOMAIN,
                path="/",
                secure=settings.SESSION_COOKIE_SECURE,
                samesite=settings.SESSION_COOKIE_SAMESITE,
                httponly=False  # 允许JavaScript访问
            )
        except Exception as e:
            print(f"设置CUSTOMER_CODE Cookie失败: {str(e)}")
    
    def set_customerid_cookie(self, user_id: int):
        """
        设置CUSTOMERID Cookie的方法
        """
        if not self.response or not user_id:
            return

        try:
            # 设置CUSTOMERID属性
            self.CUSTOMERID = str(user_id)
            print(f"🔧 设置CUSTOMERID Cookie - 用户ID: {self.CUSTOMERID}")
            
            # 设置CUSTOMERID Cookie（非HttpOnly，允许前端访问）
            self.response.set_cookie(
                key="CUSTOMERID",
                value=str(user_id),
                max_age=settings.SESSION_EXPIRE_SECONDS,
                domain=settings.SESSION_COOKIE_DOMAIN,
                path="/",
                secure=settings.SESSION_COOKIE_SECURE,
                samesite=settings.SESSION_COOKIE_SAMESITE,
                httponly=False  # 允许JavaScript访问
            )
        except Exception as e:
            print(f"设置CUSTOMERID Cookie失败: {str(e)}")
    
    def get_customer_code(self) -> Optional[str]:
        """获取CUSTOMER_CODE"""
        return self.CUSTOMER_CODE
    
    def get_customerid(self) -> Optional[str]:
        """获取CUSTOMERID"""
        return self.CUSTOMERID
    
    async def load_session(self):
        """
        加载或创建session数据。
        如果session不存在或无效，会创建一个新的并设置Cookie。
        新增：自动检测session过期并清除浏览器Cookie
        """
        self.SESSIONID = self.request.cookies.get("SESSIONID")
        self.CUSTOMER_CODE = self.request.cookies.get("CUSTOMER_CODE")  # 加载CUSTOMER_CODE
        self.CUSTOMERID = self.request.cookies.get("CUSTOMERID")  # 加载CUSTOMERID
        
        session_is_valid = False
        
        # 检查session是否存在且未过期
        if self.SESSIONID:
            try:
                # 首先检查session是否已过期
                if self.is_session_expired(self.SESSIONID):
                    print(f"⚠️ 检测到过期的session: {self.SESSIONID}")
                    # session已过期，清除浏览器Cookie
                    self.clear_expired_cookies()
                    # 重置session相关数据
                    self.SESSIONID = None
                    self.CUSTOMER_CODE = None
                    self.CUSTOMERID = None
                    self.session_data = {}
                else:
                    # session未过期，尝试加载数据
                    data = redis_client.get(f"session:{self.SESSIONID}")
                    if data:
                        self.session_data = json.loads(data)
                        session_is_valid = True
                        print(f"✅ 成功加载有效session: {self.SESSIONID}")
            except Exception as e:
                print(f"❌ 加载session时发生错误: {str(e)}")
                # Redis连接失败时，认为session无效
                session_is_valid = False
        
        # SESSIONID不存在或无效，创建新的session
        if not session_is_valid:
            self.SESSIONID = str(uuid.uuid4())
            self.CUSTOMER_CODE = None  # 重置CUSTOMER_CODE
            self.CUSTOMERID = None  # 重置CUSTOMERID
            self.session_data = {}
            
            print(f"🆕 创建新session: {self.SESSIONID}")
            
            # 使用统一的方法设置带有正确属性的Cookie
            if self.response:
                self.set_session_cookie(self.SESSIONID)
    
    async def save_session(self):
        """保存session数据到Redis"""
        try:
            if self.SESSIONID and self.session_data:
                redis_client.setex(
                    f"session:{self.SESSIONID}",
                    settings.SESSION_EXPIRE_SECONDS,
                    json.dumps(self.session_data)
                )
                print(f"💾 保存session数据: {self.SESSIONID}")
        except Exception as e:
            print(f"❌ 保存session失败: {str(e)}")
            # 不抛出异常，避免影响主流程
            pass
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取session值"""
        return self.session_data.get(key, default)

    def set(self, key: str, value: Any):
        """设置session值"""
        self.session_data[key] = value

    def delete(self, key: str):
        """删除session值"""
        if key in self.session_data:
            del self.session_data[key]
    

    def clear(self):
        """清除本地session数据并从Redis中删除"""
        try:
            if self.SESSIONID:
                redis_client.delete(f"session:{self.SESSIONID}")
                print(f"🗑️ 从Redis删除session: {self.SESSIONID}")
        except Exception as e:
            print(f"❌ 从Redis删除session失败: {str(e)}")
            # 不抛出异常，确保Cookie删除操作能执行
            pass
        
        # 清除本地session数据
        self.session_data = {}
        self.SESSIONID = None
        self.CUSTOMER_CODE = None  # 清除CUSTOMER_CODE
        self.CUSTOMERID = None  # 清除CUSTOMERID
        
        # 删除浏览器中的Cookie
        if self.response:
            self.response.delete_cookie(
                "SESSIONID",
                domain=settings.SESSION_COOKIE_DOMAIN,
                path="/"
            )
            # 同时删除CUSTOMER_CODE Cookie
            self.response.delete_cookie(
                "CUSTOMER_CODE",
                domain=settings.SESSION_COOKIE_DOMAIN,
                path="/"
            )
            # 同时删除CUSTOMERID Cookie
            self.response.delete_cookie(
                "CUSTOMERID",
                domain=settings.SESSION_COOKIE_DOMAIN,
                path="/"
            )
            print("🧹 已清除浏览器Cookie")

async def get_session(request: Request, response: Response) -> SessionManager:
    """Session依赖注入"""
    session = SessionManager(request, response)
    await session.load_session()
    try:
        yield session
    finally:
        await session.save_session()