from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    organizations,
    studies,
    artifacts,
    approvals,
    comments,
    audit,
    validation,
    generation,
    graph,
    intelligence,
)

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
api_v1_router.include_router(
    organizations.router, prefix="/organizations", tags=["Organizations"]
)
api_v1_router.include_router(studies.router, prefix="/studies", tags=["Studies"])
api_v1_router.include_router(artifacts.router, prefix="/artifacts", tags=["Artifacts"])
api_v1_router.include_router(approvals.router, prefix="/approvals", tags=["Approvals"])
api_v1_router.include_router(comments.router, prefix="/comments", tags=["Comments"])
api_v1_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_v1_router.include_router(
    validation.router, prefix="/validation", tags=["Validation"]
)
api_v1_router.include_router(
    generation.router, prefix="/generation", tags=["AI Generation"]
)
api_v1_router.include_router(graph.router, prefix="/graph", tags=["Context Graph"])
api_v1_router.include_router(
    intelligence.router, prefix="/intelligence", tags=["Intelligence"]
)
