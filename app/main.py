"""Web routes for Cloneazon."""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Cookie, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db
from recsys import personalize, semantic

LOGIN_DAYS = 30

# How many products each home page section shows per page.
PAGE_SIZES = {"for_you": 5, "popular": 10, "category": 5, "related": 5, "listing": 24, "search": 24, "bought_with": 5}
@asynccontextmanager
async def lifespan(app):
    db.init_db()
    semantic.load() # Load the CLIP once at startup
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

def _section_items(kind, user, category="", page=1, product=None, query=""):
    size = PAGE_SIZES[kind]
    offset = (page - 1) * size
    user_key = user["id"] if user else None  # recommendations skip what this user bought
    # Ask for one extra product: if it comes back, there is a next page.
    if kind == "for_you":
        items = personalize.recommend(user["id"], limit=size + 1, offset=offset) if user else []
    elif kind == "popular":
        items = db.popular_products(limit=size + 1, offset=offset, exclude_bought_by=user_key)
    elif kind == "related":
        # Related lists are short, so fetch everything up to this page and slice.
        items = _related_items(product, user_key, limit=offset + size + 1)[offset:]
    elif kind == "listing":
        items = db.list_products(category=category, limit=size + 1, offset=offset)
    elif kind == "search":
        items = semantic.hybrid_search(query, limit=size + 1, offset=offset)
    elif kind == "bought_with":
        items = _bought_with_items(product, user_key)[offset : offset + size + 1]
    else:
        items = personalize.recommend(user_key, limit=size + 1, offset=offset, category=category)
    return items[:size], len(items) > size

def _related_items(product, user_key=None, limit=10):
    """Related items from recsys.content; same-category bestsellers until it has run."""
    related = db.get_similar(product["id"], "content", limit=limit, exclude_bought_by=user_key)
    if related:
        return related
    same_category = db.list_products(category=product["category"], limit=limit + 1)
    return [p for p in same_category if p["id"] != product["id"]][:limit]

def _bought_with_items(product, user_key):
    """People buy with: the complements of `product` (bought on the same trip by other
    shoppers) first, then the related items of each complement to fill the row.
    Never the product itself or anything the user already bought."""
    complements = db.bought_with(product["id"], exclude_bought_by=user_key)
    items = list(complements)
    for complement in complements:
        items += db.get_similar(complement["id"], "content", limit=10, exclude_bought_by=user_key)
    seen = {product["id"]}
    unique = []
    for item in items:
        if item["id"] not in seen:  # the same product can be related to several complements
            seen.add(item["id"])
            unique.append(item)
    return unique

def _redirect(url):
    # 303 tells the browser to follow up with a GET, so refreshing never resubmits a form.
    return RedirectResponse(url, status_code=303)


@app.get("/")
def home(request: Request, user_id: int | None = Cookie(default=None)):
    user = _current_user(user_id)
    user_key = user["id"] if user else None
    for_you, for_you_more = _section_items("for_you", user)
    # The user's most recent purchase (get_bought lists newest first), if any.
    purchases = db.get_bought(user["id"]) if user else []
    last_bought = purchases[0] if purchases else None
    bought_with, bought_with_more = (
        _section_items("bought_with", user, product=last_bought) if last_bought else ([], False)
    )
    popular, popular_more = _section_items("popular", user)
    # Each shelf is (category, its first page of products, whether there are more).
    shelves = [(c, *_section_items("category", user, c)) for c in personalize.top_categories(user_key)]
    return _render(
        request,
        "home.html",
        user,
        for_you=for_you,
        for_you_more=for_you_more,
        last_bought=last_bought,
        bought_with=bought_with,
        bought_with_more=bought_with_more,
        popular=popular,
        popular_more=popular_more,
        shelves=shelves,
    )

# Handle types validation
# The signature of the page
@app.get("/section")
def section(
    request: Request,
    kind: Literal["for_you", "popular", "category", "related", "listing", "search", "bought_with"], # Kind must be one of three strings
    page: int = Query(default=1, ge=1), # Page must be a number greater or equal 1, default 1
    category: str = "", # Has to be a string, default ""
    product: int | None = None,  # the product whose related items are paged
    query: str = "",  # the search text, for search result pages
    user_id: int | None = Cookie(default=None),
):
    """Just the product cards of one page of a home section, for the ‹ › arrows."""
    user = _current_user(user_id)
    related_to = _product_or_404(product) if kind in ("related", "bought_with") else None
    products, has_next =  _section_items(kind, user, category, page, related_to, query)
    return templates.TemplateResponse(
        request,
        "cards.html",
        {"products": products},
        headers={"X-Has-Next": "1" if has_next else "0"},
    )


@app.get("/category/{name}")
def category_page(request: Request, name: str, user_id: int | None = Cookie(default=None)):
    user = _current_user(user_id)
    products, has_more = _section_items("listing", user, category=name)
    if not products:
        raise HTTPException(status_code=404, detail="Category not found")
    return _render(
        request,
        "listing.html",
        user,
        heading=name,
        kind="listing",
        category=name,
        products=products,
        has_more=has_more,
    )

@app.get("/search")
def search(request: Request, q: str = "", user_id: int | None = Cookie(default=None)):
    query = q.strip()
    if not query:
        return _redirect("/")
    user = _current_user(user_id)
    products, has_more = _section_items("search", user, query=query)
    return _render(
        request,
        "listing.html",
        user,
        heading=f"Results for “{query}”",
        kind="search",
        query=query,
        products=products,
        has_more=has_more,
    )

@app.get("/product/{product_id}")
def product_page(request: Request, product_id: int, user_id: int | None = Cookie(default=None)):
    product = _product_or_404(product_id)
    user = _current_user(user_id)
    if user:
        db.add_event(user["id"], product_id, "view")
    related, related_more = _section_items("related", user, product=product)
    return _render(
        request,
        "product.html",
        user,
        product=product,
        reviews=db.get_reviews(product_id),
        related=related,
        related_more=related_more,
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
    # httponly=True means JavaScript on the page can't read the cookie
    # It's a defence against cross-site scripting (XSS)
    # if an attacker ever got script onto your page, they couldn't steal the login cookie
    response.set_cookie("user_id", str(user["id"]), max_age=LOGIN_DAYS * 24 * 3600, httponly=True)
    return response


@app.post("/logout")
def logout():
    response = _redirect("/")
    response.delete_cookie("user_id")
    return response