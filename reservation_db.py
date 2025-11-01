import json
import os
from datetime import datetime, date, time
from typing import Optional, List

# 예약 데이터 저장소
# 구조: {reservation_id: {"user_id": str, "classroom_id": int, "date": str, "start_time": str, "end_time": str}}
RESERVATIONS_FILE = "reservations.json"
RESERVATIONS: dict[int, dict] = {}
_next_id = 1

def _load_reservations() -> tuple[dict[int, dict], int]:
    """파일에서 예약 데이터 로드"""
    if os.path.exists(RESERVATIONS_FILE):
        try:
            with open(RESERVATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                reservations = {int(k): v for k, v in data.get("reservations", {}).items()}
                next_id = data.get("next_id", 1)
                return reservations, next_id
        except (json.JSONDecodeError, IOError, ValueError, KeyError):
            return {}, 1
    return {}, 1

def _save_reservations() -> None:
    """예약 데이터를 파일에 저장"""
    try:
        data = {
            "reservations": {str(k): v for k, v in RESERVATIONS.items()},
            "next_id": _next_id
        }
        with open(RESERVATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError:
        pass

# 서버 시작 시 데이터 로드
loaded_reservations, loaded_next_id = _load_reservations()
RESERVATIONS.update(loaded_reservations)
_next_id = loaded_next_id

def _parse_time(time_str: str) -> time:
    """시간 문자열을 time 객체로 변환 (예: "14:00" -> time(14, 0))"""
    try:
        hour, minute = map(int, time_str.split(":"))
        return time(hour, minute)
    except (ValueError, AttributeError):
        raise ValueError(f"잘못된 시간 형식: {time_str}")

def _parse_date(date_str: str) -> date:
    """날짜 문자열을 date 객체로 변환 (예: "2024-01-15" -> date(2024, 1, 15))"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError(f"잘못된 날짜 형식: {date_str}")

def _is_past_datetime(reservation_date: date, start_time: time) -> bool:
    """예약 날짜와 시간이 과거인지 확인"""
    now = datetime.now()
    reservation_datetime = datetime.combine(reservation_date, start_time)
    return reservation_datetime < now

def _is_valid_time_slot(start_time: time, end_time: time) -> bool:
    """정시~정시 1시간 단위인지 확인"""
    # 시작 시간과 종료 시간이 정시(분이 0)인지 확인
    if start_time.minute != 0 or end_time.minute != 0:
        return False
    # 종료 시간이 시작 시간 + 1시간인지 확인
    expected_end_hour = (start_time.hour + 1) % 24
    return end_time.hour == expected_end_hour

def _is_time_overlap(start1: time, end1: time, start2: time, end2: time) -> bool:
    """두 시간 구간이 겹치는지 확인"""
    # 시간 객체를 비교 가능한 형태로 변환 (분 단위로)
    def time_to_minutes(t: time) -> int:
        return t.hour * 60 + t.minute
    
    start1_min = time_to_minutes(start1)
    end1_min = time_to_minutes(end1)
    start2_min = time_to_minutes(start2)
    end2_min = time_to_minutes(end2)
    
    # 겹치는 경우: start1 < end2 and start2 < end1
    return start1_min < end2_min and start2_min < end1_min

def create_reservation(user_id: str, classroom_id: int, reservation_date: str, start_time_str: str, end_time_str: str) -> tuple[bool, str]:
    """
    예약을 생성하고 성공 여부와 메시지를 반환
    
    Returns:
        (success: bool, message: str)
    """
    global _next_id
    
    # 1. 날짜 및 시간 파싱
    try:
        reservation_date_obj = _parse_date(reservation_date)
        start_time_obj = _parse_time(start_time_str)
        end_time_obj = _parse_time(end_time_str)
    except ValueError as e:
        return False, str(e)
    
    # 2. 정책 검증: 과거 시간 예약 불가
    if _is_past_datetime(reservation_date_obj, start_time_obj):
        return False, "과거 시간은 예약할 수 없습니다."
    
    # 3. 정책 검증: 1시간 단위 정시~정시만 가능
    if not _is_valid_time_slot(start_time_obj, end_time_obj):
        return False, "예약은 정시~정시 1시간 단위로만 가능합니다. (예: 14:00~15:00)"
    
    # 4. 해당 강의실의 같은 날짜 예약들 확인
    for reservation in RESERVATIONS.values():
        if (reservation["classroom_id"] == classroom_id and 
            reservation["date"] == reservation_date):
            existing_start = _parse_time(reservation["start_time"])
            existing_end = _parse_time(reservation["end_time"])
            
            # 시간 겹침 확인
            if _is_time_overlap(start_time_obj, end_time_obj, existing_start, existing_end):
                return False, "해당 시간에 이미 예약이 존재합니다."
    
    # 5. 예약 생성
    reservation_id = _next_id
    _next_id += 1
    
    RESERVATIONS[reservation_id] = {
        "user_id": user_id,
        "classroom_id": classroom_id,
        "date": reservation_date,
        "start_time": start_time_str,
        "end_time": end_time_str
    }
    _save_reservations()
    
    return True, "예약이 성공적으로 생성되었습니다."

def get_reservation(reservation_id: int) -> Optional[dict]:
    """예약 정보를 조회"""
    return RESERVATIONS.get(reservation_id)

def get_user_reservations(user_id: str) -> List[dict]:
    """특정 사용자의 모든 예약을 조회"""
    return [
        {**reservation, "id": res_id}
        for res_id, reservation in RESERVATIONS.items()
        if reservation["user_id"] == user_id
    ]

def get_classroom_reservations(classroom_id: int, date: Optional[str] = None) -> List[dict]:
    """특정 강의실의 예약을 조회 (날짜 필터링 옵션)"""
    reservations = [
        {**reservation, "id": res_id}
        for res_id, reservation in RESERVATIONS.items()
        if reservation["classroom_id"] == classroom_id
    ]
    
    if date:
        reservations = [r for r in reservations if r["date"] == date]
    
    # 날짜와 시간 순으로 정렬
    reservations.sort(key=lambda r: (r["date"], r["start_time"]))
    return reservations

def cancel_reservation(reservation_id: int, user_id: str) -> tuple[bool, str]:
    """예약을 취소 (본인 예약만 취소 가능)"""
    if reservation_id not in RESERVATIONS:
        return False, "존재하지 않는 예약입니다."
    
    reservation = RESERVATIONS[reservation_id]
    if reservation["user_id"] != user_id:
        return False, "본인의 예약만 취소할 수 있습니다."
    
    del RESERVATIONS[reservation_id]
    _save_reservations()
    return True, "예약이 취소되었습니다."

def delete_reservation(reservation_id: int) -> bool:
    """예약을 삭제 (관리자용)"""
    if reservation_id in RESERVATIONS:
        del RESERVATIONS[reservation_id]
        _save_reservations()
        return True
    return False
