"""Web routes for Cloneazon."""

from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=db.APP_DIR / "static", check_dir=False), name="static")
app.mount("/images", StaticFiles(directory=db.DB_PATH.parent / "images", check_dir=False), name="images")
templates = Jinja2Templates(directory=db.APP_DIR / "templates")


def _render(request, template, user_id, **context):
    context["users"] = db.list_users()
    context["categories"] = db.list_categories()
    context["user_id"] = user_id
    return templates.TemplateResponse(request, template, context)


def _product_or_404(product_id):
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.get("/product/{product_id}")
def product_page(request: Request, product_id: int, user_id: int = Cookie(default=1)):
    product = _product_or_404(product_id)
    db.add_event(user_id, product_id, "view")
    return _render(
        request,
        "product.html",
        user_id,
        product=product,
        reviews=db.get_reviews(product_id),
        similar=db.get_similar(product_id, "hybrid"),
    )


@app.post("/product/{product_id}/review")
def submit_review(
    product_id: int,
    rating: int = Form(ge=1, le=5),
    text: str = Form(default=""),
    user_id: int = Cookie(default=1),
):
    _product_or_404(product_id)
    db.add_review(product_id, user_id, rating, text)
    return RedirectResponse(f"/product/{product_id}", status_code=303)


@app.get("/")
def home(request: Request, user_id: int = Cookie(default=1)):
    return _render(request, "home.html", user_id, products=db.list_products())


@app.get("/category/{name}")
def category_page(request: Request, name: str, user_id: int = Cookie(default=1)):
    products = db.list_products(category=name)
    if not products:
        raise HTTPException(status_code=404, detail="Category not found")
    return _render(request, "listing.html", user_id, category=name, products=products)


@app.post("/product/{product_id}/buy")
def buy(product_id: int, user_id: int = Cookie(default=1)):
    _product_or_404(product_id)
    db.add_event(user_id, product_id, "buy")
    return RedirectResponse("/bought", status_code=303)


@app.get("/bought")
def bought_page(request: Request, user_id: int = Cookie(default=1)):
    return _render(request, "bought.html", user_id, products=db.get_bought(user_id))


@app.post("/switch-user")
def switch_user(user_id: int = Form()):
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("user_id", str(user_id))
    return response
