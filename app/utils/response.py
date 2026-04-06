from app.schemas.responses import APIResponse
from typing import Dict,Any
from fastapi.responses import JSONResponse
from sqlalchemy import select,func
from math import ceil
def success_response(status_code:int,message:str,data:Any | None=None,meta:Dict[str,Any] | None = None):
  content = APIResponse(success=True,message=message,data=data,meta=meta).model_dump(mode="json", exclude_none=True)
  return JSONResponse(
    status_code=status_code,
    content=content
  )

def error_response(status_code:int,message:str,errors:None | Dict[str,Any] = None,meta:Dict[str,Any] | None = None):
  content = APIResponse(success=False,message=message,errors=errors,meta=meta).model_dump(mode="json", exclude_none=True)
  return JSONResponse(
    status_code=status_code,
    content=content
  )

async def paginated_query(session, stmt, page: int, page_size: int):
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_items = (await session.execute(count_stmt)).scalar_one()

    total_pages = ceil(total_items / page_size) if total_items else 1

    paginated_stmt = (
        stmt
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = (await session.execute(paginated_stmt)).scalars().all()

    return {
        "items": items,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages
        }
    }