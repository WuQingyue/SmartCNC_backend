from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from utils.config import settings
import uvicorn
from api import auth,file,order,cart,logistics,ga4
from utils.session import test_redis_connection

# 导入模型以确保SQLAlchemy能够识别
from models.user import User
from models.file import Files

app = FastAPI()

# 配置 CORSx    
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由 
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(file.router, prefix="/api/file", tags=["file"])
app.include_router(order.router, prefix="/api/order", tags=["order"])
app.include_router(cart.router, prefix="/api/cart", tags=["cart"])
app.include_router(logistics.router, prefix="/api/logistics", tags=["logistics"])
app.include_router(ga4.router, prefix="/api/ga4", tags=["ga4"])


@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    print("🚀 应用启动中...")
    # 测试Redis连接
    test_redis_connection()

# 启动FastAPI服务器 
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)