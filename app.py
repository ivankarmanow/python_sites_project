from hashlib import sha256
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, Form, Cookie, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session

from models import User, Base, Book, SessionID

app = FastAPI()
html = Jinja2Templates(directory="html")

engine = create_engine("sqlite:///database.db")
Base.metadata.create_all(engine)


@app.get("/")
def index(
        request: Request,
        session_id: Annotated[str, Cookie()] = None
):
    with Session(engine) as session:
        user = None
        if session_id:
            session_id = session.get(SessionID, session_id)
            if session_id:
                user = session.get(User, session_id.user_id)
        books = session.scalars(select(Book)).all()
        return html.TemplateResponse(request, "index.html", {"books": books, "user": user})


@app.get("/login_form")
def login_form(request: Request):
    return html.TemplateResponse(request, "login.html")


@app.get("/reg_form")
def reg_form(request: Request):
    return html.TemplateResponse(request, "reg.html")


@app.get("/book/{id}")
def book_id(
        request: Request,
        id: int,
        session_id: Annotated[str, Cookie()] = None
):
    if not session_id:
        return "Войдите, чтобы посмотреть информацию о книге"
    with Session(engine) as session:
        session_id = session.get(SessionID, session_id)
        if not session_id:
            return "Войдите, чтобы посмотреть информацию о книге"
        user = session.get(User, session_id.user_id)
        book = session.get(Book, id)
        added_by = session.get(User, book.added_by)
        return html.TemplateResponse(request, "book.html", {"book": book, "added_by": added_by, "is_admin": user.is_admin})


@app.get("/add_form")
def add_form(
        request: Request,
        session_id: Annotated[str, Cookie()] = None
):
    if not session_id:
        return "Войдите, чтобы добавить книгу"
    with Session(engine) as session:
        if not session.get(SessionID, session_id):
            return "Войдите, чтобы добавить книгу"
    return html.TemplateResponse(request, "add.html")


@app.post("/add")
def add(
        title: Annotated[str, Form()],
        author: Annotated[str, Form()],
        year: Annotated[int, Form()],
        session_id: Annotated[str, Cookie()] = None
):
    if not session_id:
        return "Войдите, чтобы добавить книгу"
    with Session(engine) as session:
        session_id = session.get(SessionID, session_id)
        if not session_id:
            return "Войдите, чтобы добавить книгу"
        session.add(Book(
            title=title,
            author=author,
            year=year,
            added_by=session_id.user_id
        ))
        session.commit()
    return RedirectResponse("/", status_code=302)


@app.post("/login")
def login_(
        login: Annotated[str, Form()],
        password: Annotated[str, Form()]
):
    with Session(engine) as session:
        user = session.scalars(select(User).where(User.login == login)).one_or_none()
        if not user:
            return "Такого пользователя нет"
        password = sha256(password.encode("utf-8")).hexdigest()
        if user.password != password:
            return "Пароль неверный"
        session_id = str(uuid4())
        session.add(SessionID(id=session_id, user_id=user.id))
        session.commit()
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("session_id", session_id)
    return response


@app.post("/reg")
def reg(
        login: Annotated[str, Form()],
        password: Annotated[str, Form()],
        password2: Annotated[str, Form()]
):
    if password != password2:
        return "Пароли не совпадают"
    with Session(engine) as session:
        if session.scalars(select(User).where(User.login == login)).one_or_none():
            return "Пользователь с таким логином уже существует"
        password = sha256(password.encode("utf-8")).hexdigest()
        session.add(User(
            login=login,
            password=password
        ))
        session.commit()
    return login_(login, password)


@app.get("/delete")
def delete(
        id: int,
        session_id: Annotated[str, Cookie()] = None
):
    if session_id is None:
        return "Войдите, чтобы удалить книгу"
    with Session(engine) as session:
        session_id = session.get(SessionID, session_id)
        if not session_id:
            return "Войдите, чтобы удалить книгу"
        user = session.get(User, session_id.user_id)
        if not user.is_admin:
            return "Только админ может удалить книгу"
        session.delete(session.get(Book, id))
        session.commit()
    return RedirectResponse("/")


@app.get("/set_admin/{login}")
def set_admin(login: str):
    with Session(engine) as session:
        user = session.scalars(select(User).where(User.login == login)).one_or_none()
        user.is_admin = True
        session.add(user)
        session.commit()
    return RedirectResponse("/", status_code=302)
