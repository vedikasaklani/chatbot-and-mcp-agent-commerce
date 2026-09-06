"""API to get reviews for a profuct based on product_id"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.database import get_db
from database.database_models import Review

reviews_router = APIRouter(prefix="/reviews", tags=["reviews"])

@reviews_router.get("/products/{product_id}")
def get_product_rating(
    product_id: int,
    db: Session = Depends(get_db)
):
    """Return the average rating and review count for a product."""
    result = (
        db.query(
            func.avg(Review.rating).label("average_rating"),
            func.count(Review.id).label("review_count")
        )
        .filter(Review.product_id == product_id)
        .first()
    )

    if result.review_count == 0:
        return {
            "product_id": product_id,
            "message": "No reviews available"
        }

    return {
        "product_id": product_id,
        "average_rating": round(float(result.average_rating), 2),
        "review_count": result.review_count
    }