import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.dependencies import AdminDep, DocumentServiceDep, IdPath, require_admin
from app.schemas.common import ADMIN_ERRORS, ERR_404, ERR_413, ERR_415
from app.schemas.document import DocumentOut, DocumentUpdate

audit = logging.getLogger("app.audit")

router = APIRouter(
    prefix="/api/admin",
    tags=["admin: documents"],
    dependencies=[Depends(require_admin)],
    responses=ADMIN_ERRORS,
)


@router.post(
    "/products/{product_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="PDF zu einem Produkt hochladen (multipart/form-data)",
    responses={**ERR_404, **ERR_413, **ERR_415},
)
def upload_document(
    product_id: IdPath,
    svc: DocumentServiceDep,
    admin: AdminDep,
    file: Annotated[UploadFile, File(description="PDF-Datei")],
    title: Annotated[str | None, Form(max_length=200)] = None,
    description: Annotated[str | None, Form()] = None,
    version: Annotated[str, Form(min_length=1, max_length=32)] = "1.0",
    active: Annotated[bool, Form()] = True,
):
    document = svc.create(
        product_id, file, title=title, description=description, version=version, active=active, uploaded_by=admin.id
    )
    audit.info(
        "Dokument hochgeladen id=%s product_id=%s größe=%s von=%s", document.id, product_id, document.file_size, admin.username
    )
    return document


@router.get("/documents", response_model=list[DocumentOut], summary="Alle Dokumente (optional gefiltert)")
def list_documents(svc: DocumentServiceDep, product_id: int | None = None, active: bool | None = None):
    return svc.list_admin(product_id=product_id, active=active)


@router.get("/documents/{document_id}", response_model=DocumentOut, responses=ERR_404)
def get_document(document_id: IdPath, svc: DocumentServiceDep):
    return svc.get(document_id)


@router.put("/documents/{document_id}", response_model=DocumentOut, summary="Metadaten ändern / (de)aktivieren", responses=ERR_404)
def update_document(document_id: IdPath, data: DocumentUpdate, svc: DocumentServiceDep, admin: AdminDep):
    document = svc.update(document_id, data)
    audit.info("Dokument geändert id=%s von=%s", document_id, admin.username)
    return document


@router.put(
    "/documents/{document_id}/file",
    response_model=DocumentOut,
    summary="PDF ersetzen",
    responses={**ERR_404, **ERR_413, **ERR_415},
)
def replace_document_file(
    document_id: IdPath,
    svc: DocumentServiceDep,
    admin: AdminDep,
    file: Annotated[UploadFile, File(description="Neue PDF-Datei")],
    version: Annotated[str | None, Form(max_length=32)] = None,
):
    document = svc.replace_file(document_id, file, version)
    audit.info("Dokument-Datei ersetzt id=%s von=%s", document_id, admin.username)
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERR_404)
def delete_document(document_id: IdPath, svc: DocumentServiceDep, admin: AdminDep):
    svc.delete(document_id)
    audit.info("Dokument gelöscht id=%s von=%s", document_id, admin.username)
