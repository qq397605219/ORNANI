from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates

from app import crud
from app.services.openrouter_client import openrouter_client
from config import config

router = APIRouter()
security = HTTPBearer()
templates = Jinja2Templates(directory="templates")

def verify_admin_password(password: str) -> bool:
    return password == config.get('admin.password')

async def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """依赖项，用于验证管理员访问令牌。"""
    if not verify_admin_password(credentials.credentials):
        raise HTTPException(status_code=401, detail="无效的访问令牌")
    return credentials.credentials

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """提供管理后台的HTML页面。"""
    return templates.TemplateResponse("admin.html", {"request": request})

@router.post("/admin/login")
async def admin_login(password: str = Form(...)):
    """处理管理员登录请求。"""
    if verify_admin_password(password):
        return {"success": True, "message": "登录成功"}
    else:
        raise HTTPException(status_code=401, detail="密码错误")

@router.get("/admin/stats", dependencies=[Depends(get_admin_user)])
async def get_stats():
    """获取仪表盘的统计数据。"""
    key_stats = crud.get_api_key_stats()
    today_stats = crud.get_today_stats()
    model_stats = crud.get_model_stats()
    return {
        "key_stats": key_stats,
        "today_stats": today_stats,
        "model_stats": model_stats
    }

@router.post("/admin/keys", dependencies=[Depends(get_admin_user)])
async def add_api_key(key_name: str = Form(...), api_key: str = Form(...), daily_limit: int = Form(-1)):
    """添加一个新的API Key。"""
    try:
        crud.add_api_key(key_name, api_key, daily_limit)
        return {"success": True, "message": "API Key添加成功"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"添加失败: {e}")

@router.delete("/admin/keys/{key_id}", dependencies=[Depends(get_admin_user)])
async def delete_api_key(key_id: int):
    """删除一个API Key。"""
    crud.delete_api_key(key_id)
    return {"success": True, "message": "API Key删除成功"}

@router.put("/admin/keys/{key_id}", dependencies=[Depends(get_admin_user)])
async def update_api_key(key_id: int, key_name: str = Form(...), daily_limit: int = Form(...), is_active: bool = Form(...)):
    """更新一个API Key。"""
    crud.update_api_key(key_id, key_name, daily_limit, is_active)
    return {"success": True, "message": "API Key更新成功"}

@router.post("/admin/refresh-models", dependencies=[Depends(get_admin_user)])
async def refresh_free_models():
    """手动刷新免费模型列表。"""
    try:
        count = await openrouter_client.update_free_models_cache()
        return {"success": True, "message": f"成功更新 {count} 个免费模型"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")

@router.get("/admin/usage-logs", dependencies=[Depends(get_admin_user)])
async def get_usage_logs(page: int = 1, page_size: int = 50, key_filter: str = "", model_filter: str = "", status_filter: str = "", date_filter: str = ""):
    """获取详细的调用记录。"""
    result = crud.get_usage_logs(page, page_size, key_filter=key_filter, model_filter=model_filter, status_filter=status_filter, date_filter=date_filter)
    return {
        "logs": result["logs"],
        "total_records": result["total_records"],
        "total_pages": result["total_pages"],
        "current_page": page,
        "page_size": page_size
    }

@router.get("/admin/filter-options", dependencies=[Depends(get_admin_user)])
async def get_filter_options():
    """获取筛选选项数据。"""
    return crud.get_filter_options()

@router.get("/admin/free-models", dependencies=[Depends(get_admin_user)])
async def get_free_models_list():
    """获取当前免费模型列表。"""
    models = crud.get_all_free_models_with_status()
    return {"models": models}