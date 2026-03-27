from app.schemas.responses import APIResponse
from typing import Dict,Any
from fastapi.responses import JSONResponse

def success_response(status_code:int,message:str,data:Dict[str,Any] | None,meta:Dict[str,Any] | None = None):
  return JSONResponse(
    status_code=status_code,
    content=APIResponse(success=True,message=message,data=data,meta=meta).model_dump(exclude_none=True)
  )

def error_response(status_code:int,message:str,errors:None | Dict[str,Any] = None,meta:Dict[str,Any] | None = None):
  return JSONResponse(
    status_code=status_code,
    content=APIResponse(success=False,message=message,errors=errors,meta=meta).model_dump(exclude_none=True)
  )