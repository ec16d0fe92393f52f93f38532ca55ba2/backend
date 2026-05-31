from fastapi import APIRouter, UploadFile, File

from auditapp.src.sdk.minio_client import S3BucketService

router = APIRouter(
    prefix="/auditapp", tags=["auditapp"]
)


@router.post("/pricecheck")
async def upload_image(file: UploadFile = File(...)):
    # Читаем картинку
    image_data = await file.read()
    S3BucketService().upload_file_object('2', '3.png', image_data)
    

    return