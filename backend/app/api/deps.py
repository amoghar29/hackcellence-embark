from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends

from app.core import db
from app.repositories.catalog_repo import CatalogRepository
from app.repositories.package_repo import PackageRepository
from app.services.catalog_service import CatalogService
from app.services.change_service import ChangeService
from app.services.package_service import PackageService


def get_catalog() -> Iterator[CatalogRepository]:
    """One catalog connection per request."""
    with db.connect() as conn:
        yield CatalogRepository(conn)


def get_package_repository() -> PackageRepository:
    return PackageRepository(db.connect)


CatalogDep = Annotated[CatalogRepository, Depends(get_catalog)]
PackageRepositoryDep = Annotated[PackageRepository, Depends(get_package_repository)]


def get_catalog_service(cat: CatalogDep) -> CatalogService:
    return CatalogService(cat)


def get_package_service(cat: CatalogDep, repo: PackageRepositoryDep) -> PackageService:
    return PackageService(cat, repo)


PackageServiceDep = Annotated[PackageService, Depends(get_package_service)]


def get_change_service(cat: CatalogDep, packages: PackageServiceDep) -> ChangeService:
    return ChangeService(cat, packages)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
ChangeServiceDep = Annotated[ChangeService, Depends(get_change_service)]
