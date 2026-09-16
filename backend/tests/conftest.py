import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_spre.db"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import Policy

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_spre.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded_policy():
    async with TestSessionLocal() as db:
        policy = Policy(
            policy_name="Test Auto Policy",
            policy_type="AUTO",
            description="A policy used only in tests.",
            base_premium=1000,
            min_age=21,
            max_age=65,
            min_income=10000,
            coverage_amount=500000,
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)
        return policy


def pytest_sessionfinish(session, exitstatus):
    if os.path.exists("test_spre.db"):
        try:
            os.remove("test_spre.db")
        except PermissionError:
            pass
