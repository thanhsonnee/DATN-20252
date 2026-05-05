"""Seed initial users for development."""
from __future__ import annotations

from app.db.models import Base, User, UserRole
from app.db.session import SessionLocal, engine
from app.core.security import hash_password


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return

        users = [
            User(
                email="admin@gmail.com",
                hashed_password=hash_password("admin123"),
                full_name="Admin",
                role=UserRole.admin,
            ),
            User(
                email="usera@gmail.com",
                hashed_password=hash_password("123456"),
                full_name="User A",
                role=UserRole.algo_tester,
            ),
            User(
                email="userb@gmail.com",
                hashed_password=hash_password("123456"),
                full_name="User B",
                role=UserRole.dataset_provider,
            ),
            User(
                email="userc@gmail.com",
                hashed_password=hash_password("123456"),
                full_name="User C", 
                role=UserRole.metric_provider,
            ),
        ]
        db.add_all(users)
        db.commit()
        print("Seeded 4 default users.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
