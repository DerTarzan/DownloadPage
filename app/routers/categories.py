import logging

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.dependencies import AdminDep, CategoryServiceDep, IdPath, require_admin
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.schemas.common import ADMIN_ERRORS, ERR_404, ERR_409, ERR_413, ERR_415, ReorderRequest

audit = logging.getLogger("app.audit")

router = APIRouter(
    prefix="/api/admin/categories",
    tags=["admin: categories"],
    dependencies=[Depends(require_admin)],
    responses=ADMIN_ERRORS,
)


@router.get("", response_model=list[CategoryOut], summary="Alle Kategorien (auch inaktive)")
def list_categories(svc: CategoryServiceDep):
    return svc.list_admin()


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED, responses=ERR_409)
def create_category(data: CategoryCreate, svc: CategoryServiceDep, admin: AdminDep):
    category = svc.create(data)
    audit.info("Kategorie angelegt id=%s slug=%s von=%s", category.id, category.slug, admin.username)
    return category


# /reorder VOR /{id}, damit "reorder" nicht als ID interpretiert wird
@router.put("/reorder", response_model=list[CategoryOut], summary="Reihenfolge festlegen", responses={422: {"description": "ids unvollständig"}})
def reorder_categories(data: ReorderRequest, svc: CategoryServiceDep, admin: AdminDep):
    result = svc.reorder(data.ids)
    audit.info("Kategorien neu sortiert von=%s", admin.username)
    return result


@router.get("/{category_id}", response_model=CategoryOut, responses=ERR_404)
def get_category(category_id: IdPath, svc: CategoryServiceDep):
    return svc.get(category_id)


@router.put("/{category_id}", response_model=CategoryOut, responses={**ERR_404, **ERR_409})
def update_category(category_id: IdPath, data: CategoryUpdate, svc: CategoryServiceDep, admin: AdminDep):
    category = svc.update(category_id, data)
    audit.info("Kategorie geändert id=%s von=%s", category_id, admin.username)
    return category


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Kategorie löschen",
    description="Mit Produkten: 409, außer `cascade=true` (löscht Produkte, Dokumente und Dateien mit).",
    responses={**ERR_404, **ERR_409},
)
def delete_category(
    category_id: IdPath, svc: CategoryServiceDep, admin: AdminDep, cascade: bool = Query(default=False)
):
    svc.delete(category_id, cascade=cascade)
    audit.info("Kategorie gelöscht id=%s cascade=%s von=%s", category_id, cascade, admin.username)


@router.post("/{category_id}/image", response_model=CategoryOut, responses={**ERR_404, **ERR_413, **ERR_415})
def upload_category_image(category_id: IdPath, svc: CategoryServiceDep, admin: AdminDep, file: UploadFile = File(...)):
    category = svc.set_image(category_id, file)
    audit.info("Kategorie-Bild hochgeladen id=%s von=%s", category_id, admin.username)
    return category


@router.delete("/{category_id}/image", status_code=status.HTTP_204_NO_CONTENT, responses=ERR_404)
def delete_category_image(category_id: IdPath, svc: CategoryServiceDep, admin: AdminDep):
    svc.remove_image(category_id)
    audit.info("Kategorie-Bild gelöscht id=%s von=%s", category_id, admin.username)
