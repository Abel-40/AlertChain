from fastapi import APIRouter


router = APIRouter()

@router.get("/kdjaf/")
async def kdg():
  return {"message":"check"}