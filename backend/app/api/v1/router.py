"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1 import admin, auth, auth_firebase, dashboard, emails, feedback, lists, predictions

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(auth_firebase.router, prefix="/auth/firebase", tags=["Firebase Auth"])
api_router.include_router(emails.router, prefix="/emails", tags=["Emails"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["Predictions"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
api_router.include_router(lists.router, prefix="/lists", tags=["Whitelist & Blacklist"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])