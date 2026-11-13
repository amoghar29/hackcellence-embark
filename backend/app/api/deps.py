from typing import Annotated

from fastapi import Depends, Request

from app.core import db
from app.repositories.catalog_repo import Catalog
from app.repositories.package_repo import PackageRepository
from app.services.catalog_service import CatalogService
from app.services.change_service import ChangeService
from app.services.package_service import PackageService


def get_catalog(request: Request) -> Catalog:
    return request.app.state.catalog


def get_package_repository() -> PackageRepository:
    return PackageRepository(db.connect)


CatalogDep = Annotated[Catalog, Depends(get_catalog)]
PackageRepositoryDep = Annotated[PackageRepository, Depends(get_package_repository)]


def get_catalog_service(cat: CatalogDep) -> CatalogService:
    return CatalogService(cat)


def get_package_service(cat: CatalogDep, repo: PackageRepositoryDep) -> PackageService:
    return PackageService(cat, repo)


PackageServiceDep = Annotated[PackageService, Depends(get_package_service)]


def get_change_service(cat: CatalogDep, packages: PackageServiceDep, repo: PackageRepositoryDep) -> ChangeService:
    return ChangeService(cat, packages, repo)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
ChangeServiceDep = Annotated[ChangeService, Depends(get_change_service)]
