from fastapi import APIRouter, UploadFile, File

router = APIRouter(
    prefix="/auditapp", tags=["auditapp"]
)


@router.post("/pricecheck")
async def upload_image(file: UploadFile = File(...)):
    # Читаем картинку
    image_data = await file.read()

    

    return