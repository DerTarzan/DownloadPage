import logging

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.dependencies import AdminDep, IdPath, ProductServiceDep, require_admin
from app.schemas.common import ADMIN_ERRORS, ERR_404, ERR_409, ERR_413, ERR_415
from app.schemas.product import ProductCreate, ProductOut, ProductReorderRequest, ProductUpdate

audit = logging.getLogger("app.audit")

router = APIRouter(
    prefix="/api/admin/products",
    tags=["admin: products"],
    dependencies=[Depends(require_admin)],
    responses=ADMIN_ERRORS,
)


@router.get("", response_model=list[ProductOut], summary="Alle Produkte (optional gefiltert)")
def list_products(svc: ProductServiceDep, category_id: int | None = Query(default=None, ge=1), active: bool | None = None):
    return svc.list_admin(category_id=category_id, active=active)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED, responses={**ERR_409, 422: {"description": "Kategorie existiert nicht"}})
def create_product(data: ProductCreate, svc: ProductServiceDep, admin: AdminDep):
    product = svc.create(data)
    audit.info("Produkt angelegt id=%s slug=%s von=%s", product.id, product.slug, admin.username)
    return product


@router.put("/reorder", response_model=list[ProductOut], summary="Reihenfolge innerhalb einer Kategorie festlegen")
def reorder_products(data: ProductReorderRequest, svc: ProductServiceDep, admin: AdminDep):
    result = svc.reorder(data.category_id, data.ids)
    audit.info("Produkte neu sortiert category_id=%s von=%s", data.category_id, admin.username)
    return result


@router.get("/{product_id}", response_model=ProductOut, responses=ERR_404)
def get_product(product_id: IdPath, svc: ProductServiceDep):
    return svc.get(product_id)


@router.put("/{product_id}", response_model=ProductOut, responses={**ERR_404, **ERR_409})
def update_product(product_id: IdPath, data: ProductUpdate, svc: ProductServiceDep, admin: AdminDep):
    product = svc.update(product_id, data)
    audit.info("Produkt geändert id=%s von=%s", product_id, admin.username)
    return product


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Mit Dokumenten: 409, außer `cascade=true` (löscht Dokumente und Dateien mit).",
    responses={**ERR_404, **ERR_409},
)
def delete_product(product_id: IdPath, svc: ProductServiceDep, admin: AdminDep, cascade: bool = Query(default=False)):
    svc.delete(product_id, cascade=cascade)
    audit.info("Produkt gelöscht id=%s cascade=%s von=%s", product_id, cascade, admin.username)


@router.post("/{product_id}/image", response_model=ProductOut, responses={**ERR_404, **ERR_413, **ERR_415})
def upload_product_image(product_id: IdPath, svc: ProductServiceDep, admin: AdminDep, file: UploadFile = File(...)):
    product = svc.set_image(product_id, file)
    audit.info("Produkt-Bild hochgeladen id=%s von=%s", product_id, admin.username)
    return product


@router.delete("/{product_id}/image", status_code=status.HTTP_204_NO_CONTENT, responses=ERR_404)
def delete_product_image(product_id: IdPath, svc: ProductServiceDep, admin: AdminDep):
    svc.remove_image(product_id)
    audit.info("Produkt-Bild gelöscht id=%s von=%s", product_id, admin.username)
