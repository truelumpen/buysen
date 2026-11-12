"""Web routes for Cloneazon."""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Cookie, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db

LOGIN_DAYS = 30

# How many products each home page section shows per page.
PAGE_SIZES = {"for_you": 5, "popular": 10, "category": 5}

@asynccontextmanager
async def lifespan(app):
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=db.APP_DIR / "static", check_dir=False), name="static")
app.mount("/images", StaticFiles(directory=db.DB_PATH.parent / "images", check_dir=False), name="images")
templates = Jinja2Templates(directory=db.APP_DIR / "templates")
# Using the updated css file every time
templates.env.globals["version"] = lambda name: int((db.APP_DIR / "static" / name).stat().st_mtime)


def _current_user(user_id):
    """The logged-in user, or None if logged out (or the cookie points to no user)."""
    return db.get_user(user_id) if user_id is not None else None


def _render(request, template, user, **context):
    context["user"] = user
    context["categories"] = db.list_categories()
    return templates.TemplateResponse(request, template, context)


def _product_or_404(product_id):
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

def _section_items(kind, user, category="", page=1):
    """One page of a home page section, and whether a next page exists."""
    size = PAGE_SIZES[kind]
    offset = (page - 1) * size
    # Ask for one extra product: if it comes back, there is a next page.
    if kind == "for_you":
        items = db.recommend_for_user(user["id"], limit=size + 1, offset=offset) if user else []
    elif kind == "popular":
        items = db.list_products(limit=size + 1, offset=offset)
    else:
        items = db.list_products(category=category, limit=size + 1, offset=offset)
    return items[:size], len(items) > size

def _redirect(url):
    # 303 tells the browser to follow up with a GET, so refreshing never resubmits a form.
    return RedirectResponse(url, status_code=303)


@app.get("/")
def home(request: Request, user_id: int | None = Cookie(default=None)):
    user = _current_user(user_id)
    user_key = user["id"] if user else None
    for_you, for_you_more = _section_items("for_you", user)
    popular, popular_more = _section_items("popular", user)
    # Each shelf is (category, its first page of products, whether there are more).
    shelves = [(c, *_section_items("category", user, c)) for c in db.top_categories(user_key)]
    return _render(
        request,
        "home.html",
        user,
        for_you=for_you,
        for_you_more=for_you_more,
        popular=popular,
        popular_more=popular_more,
        shelves=shelves,
    )


@app.get("/section")
def section(
    request: Request,
    kind: Literal["for_you", "popular", "category"],
    page: int = Query(default=1, ge=1),
    category: str = "",
    user_id: int | None = Cookie(default=None),
):
    """Just the product cards of one page of a home section, for the ‹ › arrows."""
    user = _current_user(user_id)
    products, has_next = _section_items(kind, user, category, page)
    return templates.TemplateResponse(
        request,
        "cards.html",
        {"products": products},
        headers={"X-Has-Next": "1" if has_next else "0"},
    )


@app.get("/category/{name}")
def category_page(request: Request, name: str, user_id: int | None = Cookie(default=None)):
    products = db.list_products(category=name)
    if not products:
        raise HTTPException(status_code=404, detail="Category not found")
    user = _current_user(user_id)
    return _render(request, "listing.html", user, heading=name, products=products)

@app.get("/search")
def search(request: Request, q: str = "", user_id: int | None = Cookie(default=None)):
    query = q.strip()
    if not query:
        return _redirect("/")
    user = _current_user(user_id)
    return _render(
        request,
        "listing.html",
        user,
        heading=f"Results for “{query}”",
        query=query,
        products=db.search_products(query),
    )

@app.get("/product/{product_id}")
def product_page(request: Request, product_id: int, user_id: int | None = Cookie(default=None)):
    product = _product_or_404(product_id)
    user = _current_user(user_id)
    if user:
        db.add_event(user["id"], product_id, "view")
    return _render(
        request,
        "product.html",
        user,
        product=product,
        reviews=db.get_reviews(product_id),
        similar=db.get_similar(product_id, "hybrid"),
    )


@app.post("/product/{product_id}/review")
def submit_review(
    product_id: int,
    rating: int = Form(ge=1, le=5),
    text: str = Form(default=""),
    user_id: int | None = Cookie(default=None),
):
    _product_or_404(product_id)
    user = _current_user(user_id)
    if user:
        db.add_review(product_id, user["id"], rating, text)
    return _redirect(f"/product/{product_id}")


@app.post("/product/{product_id}/buy")
def buy(product_id: int, user_id: int | None = Cookie(default=None)):
    _product_or_404(product_id)
    user = _current_user(user_id)
    if not user:
        return _redirect(f"/product/{product_id}")
    db.add_event(user["id"], product_id, "buy")
    return _redirect("/bought")


@app.get("/bought")
def bought_page(request: Request, user_id: int | None = Cookie(default=None)):
    user = _current_user(user_id)
    if not user:
        return _redirect("/")
    return _render(request, "bought.html", user, products=db.get_bought(user["id"]))


@app.post("/login")
def login(username: str = Form(), next: str = Form(default="/")):
    # Only allow paths on this site, so a crafted form can't send people elsewhere.
    if not next.startswith("/") or next.startswith("//"):
        next = "/"
    username = username.strip()
    if not username:
        return _redirect(next)
    user = db.get_or_create_user(username)
    response = _redirect(next)
    response.set_cookie("user_id", str(user["id"]), max_age=LOGIN_DAYS * 24 * 3600, httponly=True)
    return response


@app.post("/logout")
def logout():
    response = _redirect("/")
    response.delete_cookie("user_id")
    return response