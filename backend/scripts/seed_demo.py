"""
scripts/seed_demo.py
Creates a demo user and a pre-computed scan with findings for hackathon demos.
Run from backend/ directory:  python scripts/seed_demo.py
"""
from __future__ import annotations

import asyncio
import uuid
import sys
import os

# Make sure app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.models.scan import Scan, ScanStatus, SourceType
from app.models.finding import SecurityFinding, DependencyFinding
from app.models.report import Report
from app.services.auth_service import hash_password

DEMO_EMAIL = "demo@codeguardian.ai"
DEMO_PASSWORD = "demo1234"


async def seed() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        # Check if demo user already exists
        result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=DEMO_EMAIL,
                name="Demo User",
                password_hash=hash_password(DEMO_PASSWORD),
            )
            db.add(user)
            await db.flush()
            print(f"  Created user: {DEMO_EMAIL}")
        else:
            print(f"  Demo user already exists: {DEMO_EMAIL}")

        # Create a demo scan
        scan = Scan(
            user_id=user.id,
            name="Demo: Vulnerable Python App",
            status=ScanStatus.COMPLETE.value,
            source_type=SourceType.SNIPPET.value,
            language="python",
            source_meta={"code": "import pickle\ndef load(d): return pickle.loads(d)"},
        )
        db.add(scan)
        await db.flush()

        # Security findings
        db.add(SecurityFinding(
            scan_id=scan.id,
            tool="bandit",
            rule_id="B301",
            severity="HIGH",
            confidence="HIGH",
            file_path="snippet.py",
            line_number=2,
            code_snippet="return pickle.loads(d)",
            message="Pickle and modules that wrap it can be unsafe when used to deserialize untrusted data, possible security issue.",
            cwe_id="CWE-502",
            owasp_category="A8:2017-Insecure Deserialization",
        ))
        db.add(SecurityFinding(
            scan_id=scan.id,
            tool="bandit",
            rule_id="B403",
            severity="MEDIUM",
            confidence="HIGH",
            file_path="snippet.py",
            line_number=1,
            code_snippet="import pickle",
            message="Consider possible security implications associated with pickle module.",
            cwe_id="CWE-502",
        ))

        # Dependency finding
        db.add(DependencyFinding(
            scan_id=scan.id,
            package_name="requests",
            installed_version="2.25.0",
            fixed_version="2.28.0",
            severity="HIGH",
            cve_ids=["CVE-2023-32681"],
            description="Unintended leak of proxy-authorization credentials to destination servers.",
            ecosystem="pip",
        ))

        # Report
        db.add(Report(
            scan_id=scan.id,
            release_readiness_score=65,
            risk_level="MEDIUM",
            total_security_issues=2,
            critical_count=0,
            high_count=1,
            medium_count=1,
            low_count=0,
            total_dep_issues=1,
            ai_summary=(
                "The code deserialises untrusted input using pickle (CWE-502), which allows "
                "arbitrary code execution. The requests library has a known credential-leak "
                "vulnerability. Two security issues require remediation before production release."
            ),
            ai_fix_suggestions=[
                {
                    "index": 0,
                    "suggestion": "Replace pickle.loads() with json.loads() and validate the schema with pydantic or marshmallow.",
                },
                {
                    "index": 1,
                    "suggestion": "Upgrade requests to >= 2.28.0 to patch CVE-2023-32681.",
                },
            ],
            ai_review_narrative=(
                "The codebase has moderate risk. Address the deserialization vulnerability "
                "before this code handles any user-supplied input in production."
            ),
            model_used="seed-demo",
        ))

        await db.commit()
        print(f"  Created demo scan: {scan.id}")
        print(f"\n✓ Demo data seeded. Login with {DEMO_EMAIL} / {DEMO_PASSWORD}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
