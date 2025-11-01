# main.py

from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates

# user_db.py와 classroom_db.py에서 함수 가져오기
from user_db import register_user, get_user, get_user_role, Role
from classroom_db import (
    create_classroom, get_classroom, get_all_classrooms,
    update_classroom, delete_classroom
)
from reservation_db import (
    create_reservation, get_user_reservations, 
    get_classroom_reservations, cancel_reservation
)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")

templates = Jinja2Templates(directory="templates")

# =============================================================
# 헬퍼 함수
# =============================================================

def get_current_user(request: Request) -> dict | None:
    """현재 로그인한 사용자 정보 반환"""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    
    user = get_user(user_id)
    if user:
        return {
            "user_id": user_id,
            "role": user.get("role")
        }
    return None

def require_auth(request: Request) -> dict:
    """인증이 필요한 엔드포인트에서 사용"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user

def require_admin(request: Request) -> dict:
    """관리자 권한이 필요한 엔드포인트에서 사용"""
    user = require_auth(request)
    if user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return user

# =============================================================
# 1. 인증 관련 엔드포인트
# =============================================================

# GET: 회원가입 폼 페이지 제공
@app.get("/register", response_class=HTMLResponse)
async def get_register_form(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("register.html", {"request": request, "error_message": None})

# POST: 폼 데이터 처리 및 사용자 등록
@app.post("/register")
async def post_register(
    request: Request,
    user_id: str = Form(...),
    password: str = Form(...),
    role: Role = Form(...)
):
    if not user_id or not password:
        error_msg = "ID와 비밀번호를 모두 입력해야 합니다."
        return templates.TemplateResponse("register.html", {"request": request, "error_message": error_msg})
    
    if register_user(user_id, password, role):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    else:
        error_msg = f"'{user_id}'는 이미 사용 중인 ID입니다."
        return templates.TemplateResponse("register.html", {"request": request, "error_message": error_msg})

# GET: 로그인 폼 페이지 제공
@app.get("/login", response_class=HTMLResponse)
async def get_login_form(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request, "error_message": None})

# POST: 폼 데이터 처리 및 사용자 인증
@app.post("/login")
async def post_login(
    request: Request,
    user_id: str = Form(...),
    password: str = Form(...)
):
    user = get_user(user_id)
    
    if not user or user.get("password") != password:
        error_msg = "ID 또는 비밀번호가 올바르지 않습니다."
        return templates.TemplateResponse("login.html", {"request": request, "error_message": error_msg})
    
    # 세션에 사용자 정보 저장
    request.session["user_id"] = user_id
    request.session["role"] = user.get("role")
    
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

# 로그아웃
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

# =============================================================
# 2. 메인 페이지
# =============================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user
    })

# =============================================================
# 3. 강의실 관리
# =============================================================

# 강의실 목록 조회 (모든 로그인 사용자 가능)
@app.get("/classrooms", response_class=HTMLResponse)
async def list_classrooms(request: Request):
    require_auth(request)  # 로그인만 필요 (학생도 조회 가능)
    classrooms = get_all_classrooms()
    return templates.TemplateResponse("classrooms.html", {
        "request": request,
        "classrooms": classrooms,
        "user": get_current_user(request)
    })

# 강의실 생성 폼
@app.get("/classrooms/create", response_class=HTMLResponse)
async def create_classroom_form(request: Request):
    require_admin(request)
    return templates.TemplateResponse("classroom_form.html", {
        "request": request,
        "user": get_current_user(request),
        "classroom": None,
        "mode": "create"
    })

# 강의실 생성
@app.post("/classrooms/create")
async def create_classroom_post(
    request: Request,
    name: str = Form(...),
    location: str = Form(...),
    capacity: int = Form(...),
    projector: bool = Form(default=False),
    whiteboard: bool = Form(default=False)
):
    require_admin(request)
    
    equipment = {}
    if projector:
        equipment["projector"] = True
    if whiteboard:
        equipment["whiteboard"] = True
    
    classroom_id = create_classroom(name, location, capacity, equipment)
    return RedirectResponse(url="/classrooms", status_code=status.HTTP_303_SEE_OTHER)

# 강의실 수정 폼
@app.get("/classrooms/{classroom_id}/edit", response_class=HTMLResponse)
async def edit_classroom_form(request: Request, classroom_id: int):
    require_admin(request)
    classroom = get_classroom(classroom_id)
    if not classroom:
        raise HTTPException(status_code=404, detail="강의실을 찾을 수 없습니다.")
    
    return templates.TemplateResponse("classroom_form.html", {
        "request": request,
        "user": get_current_user(request),
        "classroom": classroom,
        "classroom_id": classroom_id,
        "mode": "edit"
    })

# 강의실 수정
@app.post("/classrooms/{classroom_id}/edit")
async def edit_classroom_post(
    request: Request,
    classroom_id: int,
    name: str = Form(...),
    location: str = Form(...),
    capacity: int = Form(...),
    projector: bool = Form(default=False),
    whiteboard: bool = Form(default=False)
):
    require_admin(request)
    
    equipment = {}
    if projector:
        equipment["projector"] = True
    if whiteboard:
        equipment["whiteboard"] = True
    
    if not update_classroom(classroom_id, name, location, capacity, equipment):
        raise HTTPException(status_code=404, detail="강의실을 찾을 수 없습니다.")
    
    return RedirectResponse(url="/classrooms", status_code=status.HTTP_303_SEE_OTHER)

# 강의실 삭제
@app.post("/classrooms/{classroom_id}/delete")
async def delete_classroom_post(request: Request, classroom_id: int):
    require_admin(request)
    
    if not delete_classroom(classroom_id):
        raise HTTPException(status_code=404, detail="강의실을 찾을 수 없습니다.")
    
    return RedirectResponse(url="/classrooms", status_code=status.HTTP_303_SEE_OTHER)

# =============================================================
# 4. 예약 관리
# =============================================================

# 예약 생성 폼
@app.get("/reservations/create", response_class=HTMLResponse)
async def create_reservation_form(request: Request, classroom_id: int = Query(None)):
    user = require_auth(request)  # 로그인 사용자만 예약 가능
    classrooms = get_all_classrooms()
    
    return templates.TemplateResponse("reservation_form.html", {
        "request": request,
        "user": user,
        "classrooms": classrooms,
        "error_message": None,
        "selected_classroom_id": classroom_id
    })

# 예약 생성
@app.post("/reservations/create")
async def create_reservation_post(
    request: Request,
    classroom_id: int = Form(...),
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...)
):
    user = require_auth(request)
    classrooms = get_all_classrooms()
    
    # 강의실 존재 확인
    if classroom_id not in classrooms:
        return templates.TemplateResponse("reservation_form.html", {
            "request": request,
            "user": user,
            "classrooms": classrooms,
            "error_message": "존재하지 않는 강의실입니다."
        })
    
    # 예약 생성 시도
    success, message = create_reservation(
        user["user_id"],
        classroom_id,
        date,
        start_time,
        end_time
    )
    
    if success:
        return RedirectResponse(url="/classrooms", status_code=status.HTTP_303_SEE_OTHER)
    else:
        return templates.TemplateResponse("reservation_form.html", {
            "request": request,
            "user": user,
            "classrooms": classrooms,
            "error_message": message
        })

# 내 예약 조회
@app.get("/reservations", response_class=HTMLResponse)
async def list_my_reservations(request: Request):
    user = require_auth(request)
    reservations = get_user_reservations(user["user_id"])
    classrooms = get_all_classrooms()
    
    # 예약 데이터에 강의실 정보 추가
    for reservation in reservations:
        classroom_id = reservation["classroom_id"]
        classroom = get_classroom(classroom_id)
        reservation["classroom_name"] = classroom["name"] if classroom else f"강의실 {classroom_id}"
        reservation["classroom_location"] = classroom["location"] if classroom else ""
    
    # 날짜와 시간 순으로 정렬 (최신순)
    reservations.sort(key=lambda r: (r["date"], r["start_time"]), reverse=True)
    
    return templates.TemplateResponse("my_reservations.html", {
        "request": request,
        "user": user,
        "reservations": reservations
    })

# 강의실별 예약 현황 (타임라인)
@app.get("/classrooms/{classroom_id}/reservations", response_class=HTMLResponse)
async def classroom_reservations_timeline(request: Request, classroom_id: int, date: str = Query(None)):
    user = require_auth(request)
    classroom = get_classroom(classroom_id)
    
    if not classroom:
        raise HTTPException(status_code=404, detail="강의실을 찾을 수 없습니다.")
    
    # 날짜가 지정되지 않았으면 오늘 날짜 사용
    if not date:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
    
    reservations = get_classroom_reservations(classroom_id, date)
    
    # 예약 데이터에 사용자 정보 추가 (선택적)
    from user_db import get_user
    for reservation in reservations:
        user_info = get_user(reservation["user_id"])
        reservation["user_name"] = reservation["user_id"]  # 사용자 ID를 이름으로 사용
    
    return templates.TemplateResponse("classroom_reservations.html", {
        "request": request,
        "user": user,
        "classroom": classroom,
        "classroom_id": classroom_id,
        "reservations": reservations,
        "selected_date": date
    })

# 예약 취소
@app.post("/reservations/{reservation_id}/cancel")
async def cancel_reservation_post(request: Request, reservation_id: int):
    user = require_auth(request)
    
    success, message = cancel_reservation(reservation_id, user["user_id"])
    
    if success:
        return RedirectResponse(url="/reservations", status_code=status.HTTP_303_SEE_OTHER)
    else:
        # 에러 메시지와 함께 내 예약 페이지로 리다이렉트 (간단한 구현)
        reservations = get_user_reservations(user["user_id"])
        classrooms = get_all_classrooms()
        
        for reservation in reservations:
            classroom_id = reservation["classroom_id"]
            classroom = get_classroom(classroom_id)
            reservation["classroom_name"] = classroom["name"] if classroom else f"강의실 {classroom_id}"
            reservation["classroom_location"] = classroom["location"] if classroom else ""
        
        reservations.sort(key=lambda r: (r["date"], r["start_time"]), reverse=True)
        
        return templates.TemplateResponse("my_reservations.html", {
            "request": request,
            "user": user,
            "reservations": reservations,
            "error_message": message
        })
