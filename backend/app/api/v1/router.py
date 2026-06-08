from fastapi import APIRouter

from app.api.v1.endpoints import (
    adam,
    csr,
    statistical_qc,
    tlf,
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
    notifications,
    intake,
    uploads,
    raw_data,
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
api_v1_router.include_router(
    notifications.router, prefix="/notifications", tags=["Notifications"]
)
api_v1_router.include_router(intake.router, prefix="/intake", tags=["Intake"])
api_v1_router.include_router(uploads.router, prefix="/studies", tags=["Uploads"])
api_v1_router.include_router(raw_data.router, prefix="/raw-data", tags=["Raw Data"])
api_v1_router.include_router(adam.router, prefix="/adam", tags=["ADaM"])
api_v1_router.include_router(tlf.router, prefix="/tlf", tags=["TLF"])
api_v1_router.include_router(csr.router, prefix="/csr", tags=["CSR"])
api_v1_router.include_router(
    statistical_qc.router, prefix="/statistical-qc", tags=["Statistical QC"]
)
