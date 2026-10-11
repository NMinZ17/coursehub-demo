from __future__ import annotations
from . import schemas
import logging

from multiprocessing.dummy import connection
from fastapi import FastAPI, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import engine
from .schemas import EnrollmentCreate

logger = logging.getLogger(__name__)

app = FastAPI(
    title="CourseHub API",
    version="0.3.0",
    description="API thuc hanh Buoi 3 - Co so du lieu Web va he thong thong tin",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "CourseHub API dang hoat dong"}

@app.get("/health")
def health_check() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("Khong ket noi duoc co so du lieu")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Khong ket noi duoc co so du lieu",
        ) from exc
    return {"status": "ok", "database": "connected"}

@app.get("/courses")
def list_courses(
    q: str | None = Query(default=None, min_length=1),
) -> list[dict[str, object]]:
    sql = """
        SELECT code, name, credits
        FROM courses
    """
    parameters: dict[str, object] = {}
    
    if q is not None:
        keyword = q.strip().lower()
        if not keyword:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tu khoa tim kiem khong duoc rong",
            )
        
        sql += """
            WHERE LOWER(code) LIKE :keyword
               OR LOWER(name) LIKE :keyword
        """
        parameters["keyword"] = f"%{keyword}%"
        
    sql += " ORDER BY code"
    
    with engine.connect() as connection:
        rows = connection.execute(text(sql), parameters).mappings().all()
        
    return [dict(row) for row in rows]

@app.get("/courses")
def get_courses(
    skip: int = Query(0, ge=0, description="Số lượng bỏ qua (không âm)"),
    limit: int = Query(10, ge=1, le=100, description="Số lượng lấy (1-100)"),
    q: str = None
):
    base_query = "SELECT * FROM courses"
    params = {"skip": skip, "limit": limit}
    
    if q:
        base_query += " WHERE id ILIKE :q OR name ILIKE :q"
        params["q"] = f"%{q}%"
        
    full_query = base_query + " ORDER BY id LIMIT :limit OFFSET :skip;"
    
    with engine.connect() as conn:
        results = conn.execute(text(full_query), params).fetchall()
        return [dict(row._mapping) for row in results]

@app.get("/sections")
def list_sections(
    available_only: bool = False,
) -> list[dict[str, object]]:
    sql = """
        SELECT class_id, course_code, capacity, enrolled, remaining
        FROM v_section_summary
    """
    
    if available_only:
        sql += " WHERE remaining > 0"
        
    sql += " ORDER BY class_id"
    
    with engine.connect() as connection:
        rows = connection.execute(text(sql)).mappings().all()
        
    return [dict(row) for row in rows]

@app.get("/students/{student_id}/enrollments")
def list_student_enrollments(student_id: str) -> list[dict[str, object]]:
    student_sql = "SELECT id FROM students WHERE id = :student_id"
    
    enrollment_sql = """
        SELECT e.student_id,
               s.name AS student_name,
               cs.id AS class_section_id,
               c.code AS course_code,
               c.name AS course_name,
               e.registered_at
        FROM enrollments AS e
        JOIN students AS s ON s.id = e.student_id
        JOIN class_sections AS cs ON cs.id = e.class_section_id
        JOIN courses AS c ON c.code = cs.course_code
        WHERE e.student_id = :student_id
        ORDER BY cs.id
    """
    
    with engine.connect() as connection:
        student = connection.execute(
            text(student_sql),
            {"student_id": student_id},
        ).first()
        
        if student is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Khong tim thay sinh vien",
            )
            
        rows = connection.execute(
            text(enrollment_sql),
            {"student_id": student_id},
        ).mappings().all()
        
    return [dict(row) for row in rows]

@app.post(
    "/enrollments",
    status_code=status.HTTP_201_CREATED,
)
def create_enrollment(payload: EnrollmentCreate) -> dict[str, str]:
    student_sql = "SELECT id FROM students WHERE id = :student_id"
    
    section_sql = """
        SELECT cs.id,
               cs.capacity,
               COUNT(e.student_id) AS enrolled
        FROM class_sections AS cs
        LEFT JOIN enrollments AS e ON e.class_section_id = cs.id
        WHERE cs.id = :class_section_id
        GROUP BY cs.id, cs.capacity
    """
    
    duplicate_sql = """
        SELECT 1
        FROM enrollments
        WHERE student_id = :student_id
          AND class_section_id = :class_section_id
    """
    
    insert_sql = """
        INSERT INTO enrollments (student_id, class_section_id)
        VALUES (:student_id, :class_section_id)
    """
    
    parameters = {
        "student_id": payload.student_id,
        "class_section_id": payload.class_section_id,
    }
    
    with engine.begin() as connection:
        student = connection.execute(
            text(student_sql),
            {"student_id": payload.student_id},
        ).first()
        
        if student is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Khong tim thay sinh vien",
            )
            
        section = connection.execute(
            text(section_sql),
            {"class_section_id": payload.class_section_id},
        ).mappings().first()
        
        if section is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Khong tim thay lop hoc phan",
            )
            
        duplicated = connection.execute(
            text(duplicate_sql),
            parameters,
        ).first()
        
        if duplicated is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Sinh vien da dang ky lop nay",
            )
            
        if int(section["enrolled"]) >= int(section["capacity"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Lop hoc phan da het cho",
            )
            
        connection.execute(text(insert_sql), parameters)
        
    return {
        "message": "Dang ky thanh cong",
        "student_id": payload.student_id,
        "class_section_id": payload.class_section_id,
    }
    
@app.delete(
    "/enrollments/{student_id}/{class_section_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
    
def delete_enrollment(student_id: str, class_section_id: str) -> Response:
    sql = """
        DELETE FROM enrollments
        WHERE student_id = :student_id
          AND class_section_id = :class_section_id
    """
    
    with engine.begin() as connection:
        result = connection.execute(
            text(sql),
            {
                "student_id": student_id,
                "class_section_id": class_section_id,
            },
        )
        
        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Khong tim thay dang ky can huy",
            )
            
    return Response(status_code=status.HTTP_204_NO_CONTENT)


from typing import List
from fastapi import APIRouter

@app.get("/lecturers", response_model=List[schemas.LecturerResponse])
def get_lecturers(): 
    query = """
        SELECT id, name 
        FROM lecturers 
        ORDER BY id;
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query))
        lecturers = [{"id": row.id, "name": row.name} for row in result]
        return lecturers
    
@app.get("/sections/{section_id}")
def get_section_detail(section_id: str):
    query = """
        SELECT * 
        FROM v_section_summary 
        WHERE class_id = :section_id;
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query), {"section_id": section_id}).fetchone()
        if not result:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lớp học phần")
                
        return dict(result._mapping)

@app.patch("/sections/{section_id}/capacity")
def update_capacity(section_id: str, payload: schemas.CapacityUpdate):
    check_query = """
        SELECT enrolled 
        FROM v_section_summary 
        WHERE class_id = :section_id;
    """
    
    with engine.connect() as conn:
        section = conn.execute(text(check_query), {"section_id": section_id}).fetchone()
        
        if not section:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lớp học phần")
            
        if payload.capacity < section.enrolled:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Capacity không được nhỏ hơn số lượng đã đăng ký")
            
        update_query = """
            UPDATE class_sections 
            SET capacity = :capacity 
            WHERE id = :section_id;
        """
        conn.execute(text(update_query), {"capacity": payload.capacity, "section_id": section_id})
        conn.commit() 
        
        return {"message": "Cập nhật sức chứa thành công"}