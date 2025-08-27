from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from utils.config import settings
import uvicorn
from api import auth,file
from utils.session import test_redis_connection

app = FastAPI()

# 配置 CORS
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

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    print("🚀 应用启动中...")
    # 测试Redis连接
    test_redis_connection()

# 启动FastAPI服务器
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)