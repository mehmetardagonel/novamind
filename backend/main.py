from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import select
from db import init_db, get_session
from models import Email, EmailCreate, EmailUpdate
from sqlmodel import Session

app = FastAPI(title="Email API with DB")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/emails", response_model=list[Email])
def list_emails(session: Session = Depends(get_session)):
    return session.exec(select(Email)).all()

@app.get("/emails/{email_id}", response_model=Email)
def get_email(email_id: int, session: Session = Depends(get_session)):
    email = session.get(Email, email_id)
    if not email:
        raise HTTPException(404, "Email not found")
    return email

@app.post("/emails", response_model=Email, status_code=201)
def create_email(payload: EmailCreate, session: Session = Depends(get_session)):
    email = Email(**payload.dict())
    session.add(email)
    session.commit()
    session.refresh(email)
    return email

@app.put("/emails/{email_id}", response_model=Email)
def replace_email(email_id: int, payload: EmailCreate, session: Session = Depends(get_session)):
    email = session.get(Email, email_id)
    if not email:
        raise HTTPException(404, "Email not found")
    for k, v in payload.dict().items():
        setattr(email, k, v)
    session.add(email)
    session.commit()
    session.refresh(email)
    return email

@app.patch("/emails/{email_id}", response_model=Email)
def update_email(email_id: int, patch: EmailUpdate, session: Session = Depends(get_session)):
    email = session.get(Email, email_id)
    if not email:
        raise HTTPException(404, "Email not found")
    for k, v in patch.dict(exclude_none=True).items():
        setattr(email, k, v)
    session.add(email)
    session.commit()
    session.refresh(email)
    return email

@app.delete("/emails/{email_id}", status_code=204)
def delete_email(email_id: int, session: Session = Depends(get_session)):
    email = session.get(Email, email_id)
    if not email:
        raise HTTPException(404, "Email not found")
    session.delete(email)
    session.commit()
    return
