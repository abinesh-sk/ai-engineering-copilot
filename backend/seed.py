from app.core.database import engine
from app.core.models import Base, Organization, Application
from sqlalchemy.orm import Session

Base.metadata.create_all(bind=engine)  # harmless if tables already exist

with Session(engine) as session:
    org = Organization(name="Personal Org")
    session.add(org)
    session.flush()  # generates org.id without committing yet

    application = Application(org_id=org.id, name="rag_test_app")
    session.add(application)
    session.commit()

    print(f"org_id: {org.id}")
    print(f"application_id: {application.id}")