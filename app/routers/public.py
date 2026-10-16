"""Öffentliche Routen. Browser (Accept: text/html) bekommen HTML, alle anderen JSON.
Dieser Router MUSS zuletzt registriert werden (Catch-all /{category_slug})."""
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from app.core.exceptions import NotFoundError
from app.dependencies import (
    CategoryServiceDep,
    DocumentServiceDep,
    FileServiceDep,
    IdPath,
    ProductServiceDep,
    ensure_site_available,
)
from app.schemas.common import ERR_404, ErrorResponse
from app.schemas.product import PublicCategoryDetail, PublicCategoryList, PublicProductDetail
from app.services.file_service import InvalidStoragePathError
from app.templating import templates, wants_html

router = APIRouter(tags=["public"], dependencies=[Depends(ensure_site_available)])

MAINTENANCE_RESPONSE = {503: {"model": ErrorResponse, "description": "Wartungsmodus aktiv"}}
_IMAGE_NAME_RE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|webp)$")


def _download(document, path):
    return FileResponse(
        path,
        media_type=document.mime_type,
        filename=document.original_filename,
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, no-cache"},
    )


@router.get("/", response_model=PublicCategoryList, summary="Alle aktiven Kategorien", responses=MAINTENANCE_RESPONSE)
def index(request: Request, categories: CategoryServiceDep):
    items = categories.list_public()
    if wants_html(request):
        return templates.TemplateResponse(request, "index.html", {"categories": items})
    return {"categories": items}


@router.get("/media/images/{filename}", summary="Kategorie-/Produktbild", responses=ERR_404, response_class=FileResponse)
def media_image(filename: str, files: FileServiceDep):
    if not _IMAGE_NAME_RE.match(filename):
        raise NotFoundError()
    try:
        path = files.resolve(f"images/{filename}")
    except InvalidStoragePathError:
        raise NotFoundError()
    if not path.is_file():
        raise NotFoundError()
    return FileResponse(path, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/documents/{document_id}/download", summary="Dokument herunterladen", responses=ERR_404, response_class=FileResponse)
def download_document(document_id: IdPath, documents: DocumentServiceDep):
    document, path = documents.get_public_download(document_id)
    return _download(document, path)


@router.get(
    "/{category_slug}/{product_slug}/dokument/{document_id}/download",
    summary="Dokument über die Produkt-URL herunterladen",
    responses=ERR_404,
    response_class=FileResponse,
)
def download_document_nested(category_slug: str, product_slug: str, document_id: IdPath, documents: DocumentServiceDep):
    document, path = documents.get_public_download(document_id, category_slug, product_slug)
    return _download(document, path)


@router.get(
    "/{category_slug}",
    response_model=PublicCategoryDetail,
    summary="Kategorie mit aktiven Produkten",
    responses={**ERR_404, **MAINTENANCE_RESPONSE},
)
def category_detail(request: Request, category_slug: str, categories: CategoryServiceDep, products: ProductServiceDep):
    category = categories.get_public_by_slug(category_slug)
    children = categories.list_public_children(category)
    items = products.list_public(category)
    if wants_html(request):
        return templates.TemplateResponse(
            request,
            "category.html",
            {"category": category, "ancestors": categories.path(category)[:-1], "children": children, "products": items},
        )
    return {"category": category, "children": children, "products": items}


@router.get(
    "/{category_slug}/{product_slug}",
    response_model=PublicProductDetail,
    summary="Produkt mit aktiven Dokumenten",
    responses={**ERR_404, **MAINTENANCE_RESPONSE},
)
def product_detail(
    request: Request,
    category_slug: str,
    product_slug: str,
    categories: CategoryServiceDep,
    products: ProductServiceDep,
    documents: DocumentServiceDep,
):
    category, product = products.get_public(category_slug, product_slug)
    docs = documents.list_public(product.id)
    if wants_html(request):
        return templates.TemplateResponse(
            request,
            "product.html",
            {"category": category, "ancestors": categories.path(category)[:-1], "product": product, "documents": docs},
        )
    return {"category": category, "product": product, "documents": docs}
