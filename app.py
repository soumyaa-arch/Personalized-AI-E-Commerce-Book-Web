
import streamlit as st
import sqlite3
import math
import html
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.auth import authenticate_user, register_user
from utils.book_bot import answer_catalogue_query
from utils.orders import create_order_from_cart, get_checkout_items, get_order_confirmation, ensure_order_columns
from utils.order_history import get_user_orders, get_order_details
from utils.wishlist import get_user_wishlist, remove_from_wishlist
from utils.profile import get_profile, update_name
from utils.admin import (
    ALLOWED_STATUSES, require_admin, get_admin_metrics, get_order_status_counts,
    get_top_interacted_books, get_top_ordered_books, get_recent_orders,
    update_order_status, search_users,
)
from ml.recommender import (
    load_model,
    recommend_similar_from_model,
    get_personalized_recommendations,
)

st.set_page_config(
    page_title="E-Commerce Books",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Global CSS ----------
st.markdown("""
<style>
:root {
    --lavender: #8B6FC7;
    --lavender-light: #F4F0FC;
    --lavender-border: #DDD4F2;
    --text: #302B3A;
    --muted: #77717F;
    --white: #FFFFFF;
}

.stApp {
    background: #FBFAFD;
    color: var(--text);
}

.block-container {
    padding-top: 1.4rem;
    padding-bottom: 2rem;
    max-width: 1450px;
}

h1, h2, h3 {
    color: var(--text);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F4F0FC 0%, #FFFFFF 100%);
    border-right: 1px solid var(--lavender-border);
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #493B68;
}

.stButton > button {
    border-radius: 10px;
    border: 1px solid var(--lavender-border);
    background: white;
    color: #493B68;
    font-weight: 600;
    min-height: 42px;
}

.stButton > button:hover {
    border-color: var(--lavender);
    color: var(--lavender);
}

.primary-btn .stButton > button {
    background: var(--lavender);
    color: white;
    border-color: var(--lavender);
}

.metric-card {
    background: white;
    border: 1px solid var(--lavender-border);
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 3px 12px rgba(70, 50, 100, 0.06);
}

.hero {
    background: linear-gradient(135deg, #F4F0FC, #FFFFFF);
    border: 1px solid var(--lavender-border);
    border-radius: 20px;
    padding: 28px;
    margin-bottom: 22px;
}

.hero-title {
    font-size: 2.3rem;
    font-weight: 700;
    color: #493B68;
    margin-bottom: 6px;
}

.hero-subtitle {
    color: var(--muted);
    font-size: 1rem;
}

.login-card {
    max-width: 520px;
    margin: 40px auto;
    background: white;
    padding: 30px;
    border-radius: 20px;
    border: 1px solid var(--lavender-border);
    box-shadow: 0 8px 28px rgba(70, 50, 100, 0.08);
    color:black;
}

.small-muted {
    color: var(--muted);
    font-size: 0.9rem;
}

/* ---------- Login / Signup form visibility ---------- */

/* Keep authentication input boxes white and readable. */
.login-card div[data-baseweb="input"] {
    background-color: #FFFFFF !important;
    border: 1px solid var(--lavender-border) !important;
    border-radius: 10px !important;
}

/* Keep entered input text dark and clearly visible. */
.login-card div[data-baseweb="input"] input {
    background-color: #FFFFFF !important;
    color: #111111 !important;
    -webkit-text-fill-color: #111111 !important;
}

/* Make placeholders readable on the white input background. */
.login-card div[data-baseweb="input"] input::placeholder {
    color: #555555 !important;
    opacity: 1 !important;
    -webkit-text-fill-color: #555555 !important;
}

/* Make Login / Create Account tab text black and visible. */
.login-card button[data-baseweb="tab"] {
    color: #000000 !important;
    font-weight: 600 !important;
}

.login-card button[data-baseweb="tab"][aria-selected="true"] {
    color: #000000 !important;
    font-weight: 700 !important;
}

/* Make authentication action buttons black with white text. */
.login-card .stButton > button {
    background-color: #000000 !important;
    color: #FFFFFF !important;
    border-color: #000000 !important;
}

.login-card .stButton > button:hover {
    background-color: #222222 !important;
    color: #FFFFFF !important;
    border-color: #222222 !important;
}

/* Login / Create Account tabs */
button[data-baseweb="tab"] {
    color: #111111 !important;
    font-weight: 600 !important;
}

/* Active tab */
button[data-baseweb="tab"][aria-selected="true"] {
    color: #000000 !important;
    font-weight: 700 !important;
}

/* Tab text inside button */
button[data-baseweb="tab"] p {
    color: #111111 !important;
}

/* Active tab text */
button[data-baseweb="tab"][aria-selected="true"] p {
    color: #000000 !important;
}
</style>
""", unsafe_allow_html=True)


# ---------- Session state ----------
DEFAULTS = {
    "authenticated": False,
    "user": None,
    "page": "Home",
    "selected_book_id": None,
    "browse_page": 1,
    "orders_page": 1,
    "selected_order_id": None,
    "order_status_filter": "All",
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------- Authentication ----------
def login_form():
    # Center the complete welcome/login section
    left, center, right = st.columns([1, 2, 1])

    with center:
        with st.container(border=True):

            st.markdown("## 📚 Welcome to E-Commerce Books")

            st.markdown(
                '<p class="small-muted">'
                'Sign in to browse books, build your cart, and receive recommendations.'
                '</p>',
                unsafe_allow_html=True
            )

            login_tab, signup_tab = st.tabs(
                ["🔐 Login", "✨ Create Account"]
            )

            # ---------------- LOGIN ----------------
            with login_tab:

                email = st.text_input(
                    "Email",
                    placeholder="Enter your email address",
                    key="login_email"
                )

                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter your password",
                    key="login_password"
                )

                if st.button(
                    "Login",
                    type="primary",
                    use_container_width=True
                ):
                    user = authenticate_user(email, password)

                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.page = "Home"
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")

            # ---------------- SIGN UP ----------------
            with signup_tab:

                name = st.text_input(
                    "Full Name",
                    placeholder="Enter your full name",
                    key="signup_name"
                )

                email = st.text_input(
                    "Email",
                    placeholder="Enter your email address",
                    key="signup_email"
                )

                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter your password",
                    key="signup_password"
                )

                confirm = st.text_input(
                    "Confirm Password",
                    type="password",
                    placeholder="Confirm your password",
                    key="signup_confirm"
                )

                if st.button(
                    "Create Account",
                    use_container_width=True
                ):
                    if password != confirm:
                        st.error("Passwords do not match.")
                    else:
                        ok, message = register_user(
                            name,
                            email,
                            password
                        )

                        if ok:
                            st.success(
                                "Account created. Please log in."
                            )
                        else:
                            st.error(message)



# ---------- Sidebar ----------
def render_sidebar():
    user = st.session_state.user

    with st.sidebar:
        st.markdown("## 📚 E-Commerce Books")
        st.caption("AI-powered online bookstore")

        st.divider()

        st.markdown(f"### 👤 {user['name']}")
        st.caption(user["email"])

        st.divider()

        nav_items = [
            "🏠 Home",
            "📚 Browse Books",
            "🤖 Recommendations",
            "💬 Book Bot",
            "🛒 Cart",
            "📦 My Orders",
            "❤️ Wishlist",
            "👤 Profile",
        ]

        if user["role"] == "admin":
            nav_items.append("👨‍💼 Admin Dashboard")

        current = st.session_state.page

        for label in nav_items:
            page_name = label.split(" ", 1)[1]
            if st.button(
                label,
                key=f"nav_{page_name}",
                use_container_width=True
            ):
                st.session_state.page = page_name
                if page_name == "My Orders":
                    st.session_state.selected_order_id = None
                st.rerun()

        st.divider()

        if st.button("🚪 Sign Out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.page = "Home"
            st.rerun()



# ---------- Database helpers ----------
def get_db_connection():
    conn = sqlite3.connect(ROOT / "bookstore.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@st.cache_resource(show_spinner=False)
def get_recommender_model():
    return load_model()


def get_book_choices(limit=30):
    conn = get_db_connection()
    try:
        return conn.execute(
            """SELECT book_id, title, author, avg_rating
                   FROM books
                   WHERE title IS NOT NULL AND TRIM(title) <> ''
                   ORDER BY CASE WHEN avg_rating IS NULL THEN 1 ELSE 0 END,
                            avg_rating DESC, title ASC
                   LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()


def get_home_stats():
    conn = get_db_connection()
    try:
        total_books = conn.execute(
            "SELECT COUNT(*) FROM books"
        ).fetchone()[0]

        top_rated = conn.execute(
            """
            SELECT book_id, title, author, avg_rating, price
            FROM books
            WHERE avg_rating IS NOT NULL
            ORDER BY avg_rating DESC, title ASC
            LIMIT 5
            """
        ).fetchall()

        author_counts = conn.execute(
            """
            SELECT author, COUNT(*) AS book_count
            FROM books
            WHERE author IS NOT NULL AND TRIM(author) <> ''
            GROUP BY author
            ORDER BY book_count DESC, author ASC
            LIMIT 5
            """
        ).fetchall()

        price_stats = conn.execute(
            """
            SELECT MIN(price), MAX(price), AVG(price)
            FROM books
            WHERE price IS NOT NULL
            """
        ).fetchone()

        return {
            "total_books": total_books,
            "top_rated": top_rated,
            "authors": author_counts,
            "min_price": price_stats[0] or 0,
            "max_price": price_stats[1] or 0,
            "avg_price": price_stats[2] or 0,
        }
    finally:
        conn.close()


def get_cart_summary(user_id):
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(ci.quantity), 0) AS item_count,
                COALESCE(SUM(ci.quantity * b.price), 0) AS total
            FROM carts c
            LEFT JOIN cart_items ci ON ci.cart_id = c.cart_id
            LEFT JOIN books b ON b.book_id = ci.book_id
            WHERE c.user_id = ?
            """,
            (user_id,)
        ).fetchone()
        return int(row["item_count"]), float(row["total"])
    finally:
        conn.close()


def get_user_order_summary(user_id):
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS order_count,
                COALESCE(SUM(total_amount), 0) AS total_spent
            FROM orders
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()
        return int(row["order_count"]), float(row["total_spent"])
    finally:
        conn.close()


# ---------- Browse Books ----------
@st.cache_data(ttl=3600)
def get_browse_ranges():
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT
                COALESCE(MIN(price), 0), COALESCE(MAX(price), 0),
                COALESCE(MIN(publication_year), 0), COALESCE(MAX(publication_year), 0)
            FROM books
            WHERE price IS NOT NULL
            """
        ).fetchone()
        return float(row[0]), float(row[1]), int(row[2]), int(row[3])
    finally:
        conn.close()


@st.cache_data(ttl=3600)
def get_publishers(limit=100):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT publisher, COUNT(*) AS book_count
            FROM books
            WHERE publisher IS NOT NULL AND TRIM(publisher) <> ''
            GROUP BY publisher
            ORDER BY book_count DESC, publisher ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [r["publisher"] for r in rows]
    finally:
        conn.close()


def search_books(search_text="", author="", publisher="", min_price=None,
                 max_price=None, min_rating=0.0, min_year=None, max_year=None,
                 sort_by="Relevance", page=1, page_size=12):
    conditions = []
    params = []

    if search_text.strip():
        term = f"%{search_text.strip()}%"
        conditions.append("(title LIKE ? OR author LIKE ? OR publisher LIKE ?)")
        params.extend([term, term, term])

    if author.strip():
        conditions.append("author LIKE ?")
        params.append(f"%{author.strip()}%")

    if publisher and publisher != "All Publishers":
        conditions.append("publisher = ?")
        params.append(publisher)

    if min_price is not None:
        conditions.append("price >= ?")
        params.append(float(min_price))

    if max_price is not None:
        conditions.append("price <= ?")
        params.append(float(max_price))

    if min_rating > 0:
        conditions.append("avg_rating >= ?")
        params.append(float(min_rating))

    if min_year and min_year > 0:
        conditions.append("publication_year >= ?")
        params.append(int(min_year))

    if max_year and max_year > 0:
        conditions.append("publication_year <= ?")
        params.append(int(max_year))

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    order_map = {
        "Relevance": "CASE WHEN avg_rating IS NULL THEN 1 ELSE 0 END, avg_rating DESC, title ASC",
        "Rating: High to Low": "avg_rating IS NULL, avg_rating DESC, title ASC",
        "Price: Low to High": "price ASC, title ASC",
        "Price: High to Low": "price DESC, title ASC",
        "Title: A to Z": "title COLLATE NOCASE ASC",
        "Newest First": "publication_year DESC, title ASC",
    }
    order_clause = order_map.get(sort_by, order_map["Relevance"])

    conn = get_db_connection()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM books {where}", params
        ).fetchone()[0]

        offset = max(page - 1, 0) * page_size
        rows = conn.execute(
            f"""
            SELECT book_id, isbn, title, author, publisher,
                   publication_year, avg_rating, price
            FROM books
            {where}
            ORDER BY {order_clause}
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        ).fetchall()
        return total, rows
    finally:
        conn.close()


def add_book_to_cart(user_id, book_id):
    conn = get_db_connection()
    try:
        conn.execute("BEGIN")
        cart = conn.execute(
            "SELECT cart_id FROM carts WHERE user_id = ? LIMIT 1", (user_id,)
        ).fetchone()
        if cart is None:
            cursor = conn.execute("INSERT INTO carts (user_id) VALUES (?)", (user_id,))
            cart_id = cursor.lastrowid
        else:
            cart_id = cart["cart_id"]

        existing = conn.execute(
            "SELECT cart_item_id, quantity FROM cart_items WHERE cart_id = ? AND book_id = ?",
            (cart_id, book_id),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE cart_items SET quantity = quantity + 1 WHERE cart_item_id = ?",
                (existing["cart_item_id"],),
            )
        else:
            conn.execute(
                "INSERT INTO cart_items (cart_id, book_id, quantity) VALUES (?, ?, 1)",
                (cart_id, book_id),
            )
        conn.execute("UPDATE carts SET updated_at = CURRENT_TIMESTAMP WHERE cart_id = ?", (cart_id,))
        # Feed real cart activity into the personalization engine.
        conn.execute(
            "INSERT INTO user_interactions (user_id, book_id, interaction_type) VALUES (?, ?, 'cart')",
            (int(user_id), int(book_id)),
        )
        conn.commit()
        return True, "Added to cart."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def render_book_grid(rows):
    if not rows:
        st.warning("No books match the selected filters. Try changing your search or filters.")
        return

    for start in range(0, len(rows), 3):
        cols = st.columns(3, gap="medium")
        for col, book in zip(cols, rows[start:start + 3]):
            with col:
                title = html.escape(str(book["title"] or "Untitled"))
                author = html.escape(str(book["author"] or "Unknown Author"))
                publisher = html.escape(str(book["publisher"] or "Unknown Publisher"))
                rating = book["avg_rating"]
                rating_text = f"⭐ {float(rating):.1f}" if rating is not None else "⭐ N/A"
                price = float(book["price"] or 0)
                year = book["publication_year"]
                year_text = str(year) if year else "Year N/A"

                st.markdown(
                    f"""
                    <div style="background:#fff;border:1px solid #DDD4F2;border-radius:16px;
                                padding:18px;min-height:245px;
                                box-shadow:0 3px 12px rgba(70,50,100,.06);">
                        <div style="font-size:2.5rem;text-align:center;margin-bottom:8px;">📖</div>
                        <div style="font-weight:700;color:#302B3A;min-height:48px;">{title}</div>
                        <div style="color:#77717F;min-height:24px;">{author}</div>
                        <div style="color:#77717F;font-size:.85rem;margin-top:5px;">{publisher}</div>
                        <div style="margin-top:10px;">{rating_text} &nbsp;|&nbsp; {year_text}</div>
                        <div style="font-size:1.15rem;font-weight:700;color:#493B68;margin-top:8px;">₹{price:,.0f}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                b1, b2 = st.columns(2)
                with b1:
                    if st.button("👁 Details", key=f"details_{book['book_id']}", use_container_width=True):
                        st.session_state.selected_book_id = int(book["book_id"])
                        st.session_state.page = "Book Details"
                        st.rerun()
                with b2:
                    if st.button("🛒 Add", key=f"add_{book['book_id']}", use_container_width=True):
                        ok, message = add_book_to_cart(
                            st.session_state.user["user_id"], int(book["book_id"])
                        )
                        if ok:
                            st.success("Added", icon="🛒")
                        else:
                            st.error(message)


def render_browse_books():
    st.markdown("## 📚 Browse Books")
    st.caption("Search the catalogue and use the filters to find a book that fits your needs.")

    min_db_price, max_db_price, min_db_year, max_db_year = get_browse_ranges()
    if max_db_price < min_db_price:
        max_db_price = min_db_price
    if max_db_year < min_db_year:
        max_db_year = min_db_year

    with st.container(border=True):
        st.markdown("### 🔎 Search & Filters")
        search_col, sort_col = st.columns([2.2, 1])
        with search_col:
            search_text = st.text_input(
                "Search",
                placeholder="Search by title, author or publisher...",
                key="browse_search",
            )
        with sort_col:
            sort_by = st.selectbox(
                "Sort by",
                [
                    "Relevance", "Rating: High to Low", "Price: Low to High",
                    "Price: High to Low", "Title: A to Z", "Newest First"
                ],
                key="browse_sort",
            )

        f1, f2, f3 = st.columns(3)
        with f1:
            author = st.text_input("Author", placeholder="e.g. Agatha Christie", key="browse_author")
        with f2:
            publishers = ["All Publishers"] + get_publishers()
            publisher = st.selectbox("Publisher", publishers, key="browse_publisher")
        with f3:
            min_rating = st.selectbox(
                "Minimum Rating", [0.0, 1.0, 2.0, 3.0, 4.0, 4.5],
                format_func=lambda x: "Any rating" if x == 0 else f"{x:.1f}+ ⭐",
                key="browse_rating",
            )

        f4, f5 = st.columns(2)
        with f4:
            price_range = st.slider(
                "Price Range (₹)", min_value=float(min_db_price), max_value=float(max_db_price),
                value=(float(min_db_price), float(max_db_price)), step=1.0,
                key="browse_price_range",
            )
        with f5:
            if min_db_year > 0 and max_db_year > 0:
                year_range = st.slider(
                    "Publication Year", min_value=min_db_year, max_value=max_db_year,
                    value=(min_db_year, max_db_year), step=1,
                    key="browse_year_range",
                )
            else:
                year_range = (0, 0)

    # The dataset has no genre/category column, so filters only use fields actually present in the data.
    st.caption("ℹ️ Category/genre is not shown because the supplied dataset does not contain a category field.")

    page_size = 12
    page_key = "browse_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    # Reset pagination when filter/search settings change.
    filter_signature = (
        search_text, author, publisher, tuple(price_range), min_rating,
        tuple(year_range), sort_by
    )
    if st.session_state.get("browse_filter_signature") != filter_signature:
        st.session_state["browse_filter_signature"] = filter_signature
        st.session_state[page_key] = 1

    total, rows = search_books(
        search_text=search_text,
        author=author,
        publisher=publisher,
        min_price=price_range[0],
        max_price=price_range[1],
        min_rating=min_rating,
        min_year=year_range[0],
        max_year=year_range[1],
        sort_by=sort_by,
        page=st.session_state[page_key],
        page_size=page_size,
    )

    total_pages = max(1, math.ceil(total / page_size))
    if st.session_state[page_key] > total_pages:
        st.session_state[page_key] = total_pages
        st.rerun()

    st.markdown(f"### 📖 Books <span class='small-muted'>({total:,} result(s))</span>", unsafe_allow_html=True)
    render_book_grid(rows)

    if total > 0:
        st.divider()
        prev_col, info_col, next_col = st.columns([1, 2, 1])
        with prev_col:
            if st.button("← Previous", disabled=st.session_state[page_key] <= 1, use_container_width=True):
                st.session_state[page_key] -= 1
                st.rerun()
        with info_col:
            st.markdown(
                f"<div style='text-align:center;padding-top:9px;color:#77717F;'>"
                f"Page <b>{st.session_state[page_key]}</b> of <b>{total_pages}</b>"
                f"</div>", unsafe_allow_html=True
            )
        with next_col:
            if st.button("Next →", disabled=st.session_state[page_key] >= total_pages, use_container_width=True):
                st.session_state[page_key] += 1
                st.rerun()


# ---------- Checkout & Orders ----------
def validate_checkout_form(customer_name, customer_email, shipping_address, city, state, pincode):
    """Client-side validation for the demo checkout form."""
    values = [customer_name, customer_email, shipping_address, city, state, pincode]
    if not all(str(v).strip() for v in values):
        return False, "Please complete all required checkout fields."
    email = str(customer_email).strip()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return False, "Please enter a valid email address."
    pin = str(pincode).strip()
    if not pin.isdigit() or len(pin) != 6:
        return False, "Please enter a valid 6-digit PIN code."
    return True, ""


def render_checkout():
    """Render a demo checkout and atomically create an order from the current cart."""
    user = st.session_state.user
    user_id = int(user["user_id"])
    items = get_checkout_items(user_id)

    st.markdown("## ⚡ Checkout")
    st.caption("Review your order and enter delivery details. This project uses demo payment only; no real payment is charged.")

    if not items:
        st.info("Your cart is empty. Add a book before checking out.")
        if st.button("📚 Browse Books", type="primary", use_container_width=True):
            st.session_state.page = "Browse Books"
            st.rerun()
        return

    item_count = sum(int(i["quantity"]) for i in items)
    subtotal = sum(float(i["line_total"]) for i in items)

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        st.markdown("### 📦 Delivery Details")
        with st.container(border=True):
            name = st.text_input("Full Name *", value=str(user.get("name") or ""), key="checkout_name")
            email = st.text_input("Email *", value=str(user.get("email") or ""), key="checkout_email")
            address = st.text_area("Delivery Address *", placeholder="House/flat, street, locality", key="checkout_address")
            c1, c2, c3 = st.columns(3)
            with c1:
                city = st.text_input("City *", key="checkout_city")
            with c2:
                state = st.text_input("State *", key="checkout_state")
            with c3:
                pincode = st.text_input("PIN Code *", max_chars=6, key="checkout_pincode")

        st.markdown("### 💳 Payment")
        st.radio(
            "Payment Method",
            ["Demo Payment (No real charge)"],
            key="checkout_payment_method",
            help="This academic project does not connect to a real payment gateway.",
        )

    with right:
        st.markdown("### 🧾 Order Summary")
        for item in items:
            st.markdown(
                f"**{html.escape(str(item['title']))}**  × {int(item['quantity'])}  "
                f"— ₹{float(item['line_total']):,.2f}"
            )
        st.divider()
        st.markdown(
            f"<div class='metric-card'>"
            f"<div style='display:flex;justify-content:space-between;'><span>Items</span><b>{item_count}</b></div>"
            f"<div style='display:flex;justify-content:space-between;margin-top:10px;'><span>Subtotal</span><b>₹{subtotal:,.2f}</b></div>"
            f"<div style='display:flex;justify-content:space-between;margin-top:10px;'><span>Delivery</span><b>₹0.00</b></div>"
            f"<hr><div style='display:flex;justify-content:space-between;font-size:1.2rem;'><b>Total</b><b style='color:#493B68;'>₹{subtotal:,.2f}</b></div>"
            f"</div>", unsafe_allow_html=True
        )

        st.write("")
        if st.button("✅ Place Order", type="primary", use_container_width=True):
            valid, message = validate_checkout_form(name, email, address, city, state, pincode)
            if not valid:
                st.error(message)
                return
            ok, result_message, order_id = create_order_from_cart(
                user_id=user_id,
                customer_name=name,
                customer_email=email,
                shipping_address=address,
                city=city,
                state=state,
                pincode=pincode,
                payment_method="Demo Payment",
            )
            if ok:
                st.session_state.last_order_id = int(order_id)
                st.session_state.page = "Order Confirmation"
                st.rerun()
            else:
                st.error(result_message)

        if st.button("← Back to Cart", use_container_width=True):
            st.session_state.page = "Cart"
            st.rerun()


def render_order_confirmation():
    user_id = int(st.session_state.user["user_id"])
    order_id = st.session_state.get("last_order_id")
    if not order_id:
        st.info("No recent order is available.")
        return

    order, items = get_order_confirmation(user_id, int(order_id))
    if order is None:
        st.error("Order not found.")
        return

    st.markdown("## 🎉 Order Confirmed")
    st.success(f"Your order #{order['order_id']} has been placed successfully.")
    st.markdown(
        f"<div class='hero'><div class='hero-title' style='font-size:1.8rem;'>Order #{order['order_id']}</div>"
        f"<div class='hero-subtitle'>Status: {html.escape(str(order['status']))} · {html.escape(str(order['order_date']))}</div></div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        st.markdown("### 📚 Purchased Books")
        for item in items:
            st.markdown(
                f"- **{html.escape(str(item['title']))}** — {html.escape(str(item['author']))} "
                f"× {int(item['quantity'])} · ₹{float(item['line_total']):,.2f}"
            )
        st.markdown("### 📦 Delivery Details")
        st.info(
            f"{html.escape(str(order['customer_name']))}\n\n"
            f"{html.escape(str(order['shipping_address']))}, {html.escape(str(order['city']))}, "
            f"{html.escape(str(order['state']))} - {html.escape(str(order['pincode']))}"
        )
    with right:
        st.markdown("### 💰 Payment Summary")
        st.markdown(
            f"<div class='metric-card'><div class='small-muted'>Demo payment</div>"
            f"<h2 style='color:#493B68;'>₹{float(order['total_amount']):,.2f}</h2>"
            f"<div>{html.escape(str(order['payment_method']))}</div></div>",
            unsafe_allow_html=True,
        )
        st.write("")
        st.info("No real payment was processed. This is a demonstration checkout for the academic project.")
        if st.button("📚 Continue Shopping", type="primary", use_container_width=True):
            st.session_state.page = "Browse Books"
            st.rerun()
        if st.button("🏠 Back to Home", use_container_width=True):
            st.session_state.page = "Home"
            st.rerun()



# ---------- Order History ----------
def render_order_details(order_id):
    user_id = int(st.session_state.user["user_id"])
    order, items = get_order_details(user_id, int(order_id))

    if order is None:
        st.error("Order not found.")
        if st.button("← Back to My Orders", use_container_width=True):
            st.session_state.selected_order_id = None
            st.session_state.page = "My Orders"
            st.rerun()
        return

    st.markdown("## 📦 Order Details")
    st.markdown(
        f"<div class='hero'><div class='hero-title' style='font-size:1.8rem;'>"
        f"Order #{int(order['order_id'])}</div>"
        f"<div class='hero-subtitle'>Status: {html.escape(str(order['status']))} · "
        f"{html.escape(str(order['order_date']))}</div></div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        st.markdown("### 📚 Books in This Order")
        for item in items:
            with st.container(border=True):
                c1, c2 = st.columns([3.2, 1])
                with c1:
                    st.markdown(f"**{html.escape(str(item['title']))}**")
                    st.caption(f"by {html.escape(str(item['author']))}")
                    st.write(f"Quantity: {int(item['quantity'])}")
                with c2:
                    st.markdown(f"**₹{float(item['line_total']):,.2f}**")
                    st.caption(f"₹{float(item['unit_price']):,.2f} each")

    with right:
        st.markdown("### 💰 Order Summary")
        st.markdown(
            f"<div class='metric-card'>"
            f"<div class='small-muted'>Order total</div>"
            f"<h2 style='color:#493B68;'>₹{float(order['total_amount']):,.2f}</h2>"
            f"<div>Status: <b>{html.escape(str(order['status']))}</b></div>"
            f"<div style='margin-top:8px;'>Payment: {html.escape(str(order['payment_method'] or 'Demo Payment'))}</div>"
            f"</div>", unsafe_allow_html=True,
        )

        st.markdown("### 📍 Delivery Details")
        st.info(
            f"**{html.escape(str(order['customer_name'] or ''))}**\n\n"
            f"{html.escape(str(order['shipping_address'] or ''))}, "
            f"{html.escape(str(order['city'] or ''))}, "
            f"{html.escape(str(order['state'] or ''))} - "
            f"{html.escape(str(order['pincode'] or ''))}\n\n"
            f"{html.escape(str(order['customer_email'] or ''))}"
        )

    st.write("")
    if st.button("← Back to My Orders", use_container_width=True):
        st.session_state.selected_order_id = None
        st.session_state.page = "My Orders"
        st.rerun()


def render_my_orders():
    """Render the authenticated user's paginated order history."""
    user_id = int(st.session_state.user["user_id"])

    selected_order_id = st.session_state.get("selected_order_id")
    if selected_order_id:
        render_order_details(int(selected_order_id))
        return

    st.markdown("## 📦 My Orders")
    st.caption("View your previous purchases, order status, totals, and delivery details.")

    filter_col, spacer = st.columns([1, 3])
    with filter_col:
        status = st.selectbox(
            "Order Status",
            ["All"] + list(ALLOWED_STATUSES),
            key="order_status_filter",
        )

    page_size = 8
    page_key = "orders_page"
    status_signature = status
    if st.session_state.get("orders_filter_signature") != status_signature:
        st.session_state["orders_filter_signature"] = status_signature
        st.session_state[page_key] = 1

    rows, total = get_user_orders(
        user_id,
        page=st.session_state.get(page_key, 1),
        page_size=page_size,
        status=status,
    )
    total_pages = max(1, math.ceil(total / page_size))
    if st.session_state.get(page_key, 1) > total_pages:
        st.session_state[page_key] = total_pages
        st.rerun()

    if not rows:
        st.info("You haven't placed any orders yet.")
        if st.button("📚 Browse Books", type="primary", use_container_width=True):
            st.session_state.page = "Browse Books"
            st.rerun()
        return

    st.markdown(
        f"<div class='small-muted'>Showing {len(rows)} of {total} order(s)</div>",
        unsafe_allow_html=True,
    )
    st.write("")

    for order in rows:
        with st.container(border=True):
            c1, c2, c3 = st.columns([2.1, 1.2, 1.1])
            with c1:
                st.markdown(f"### Order #{int(order['order_id'])}")
                st.caption(f"Placed: {order['order_date']}")
                st.write(f"{int(order['item_count'])} item(s)")
            with c2:
                st.markdown(f"**₹{float(order['total_amount']):,.2f}**")
                st.caption(str(order['payment_method'] or "Demo Payment"))
                st.success(str(order['status']))
            with c3:
                if st.button(
                    "View Details →",
                    key=f"view_order_{int(order['order_id'])}",
                    use_container_width=True,
                ):
                    st.session_state.selected_order_id = int(order["order_id"])
                    st.rerun()

    st.write("")
    prev_col, page_col, next_col = st.columns([1, 2, 1])
    with prev_col:
        if st.button(
            "← Previous",
            disabled=st.session_state[page_key] <= 1,
            use_container_width=True,
        ):
            st.session_state[page_key] -= 1
            st.rerun()
    with page_col:
        st.markdown(
            f"<div style='text-align:center;padding-top:8px;'>"
            f"Page <b>{st.session_state[page_key]}</b> of <b>{total_pages}</b></div>",
            unsafe_allow_html=True,
        )
    with next_col:
        if st.button(
            "Next →",
            disabled=st.session_state[page_key] >= total_pages,
            use_container_width=True,
        ):
            st.session_state[page_key] += 1
            st.rerun()


# ---------- Shopping Cart ----------
def get_cart_items(user_id):
    """Return the current user's cart items with live catalogue prices."""
    conn = get_db_connection()
    try:
        return conn.execute(
            """
            SELECT ci.cart_item_id, ci.book_id, ci.quantity,
                   b.isbn, b.title, b.author, b.publisher,
                   b.publication_year, b.avg_rating, b.price,
                   (ci.quantity * b.price) AS line_total
            FROM carts c
            JOIN cart_items ci ON ci.cart_id = c.cart_id
            JOIN books b ON b.book_id = ci.book_id
            WHERE c.user_id = ?
            ORDER BY ci.added_at DESC, ci.cart_item_id DESC
            """,
            (int(user_id),),
        ).fetchall()
    finally:
        conn.close()


def update_cart_item(user_id, cart_item_id, quantity):
    """Set an item's quantity, removing it when quantity is zero."""
    quantity = int(quantity)
    if quantity < 0:
        return False, "Quantity cannot be negative."

    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT ci.cart_item_id
            FROM carts c
            JOIN cart_items ci ON ci.cart_id = c.cart_id
            WHERE c.user_id = ? AND ci.cart_item_id = ?
            LIMIT 1
            """,
            (int(user_id), int(cart_item_id)),
        ).fetchone()
        if row is None:
            return False, "Cart item not found."

        if quantity == 0:
            conn.execute("DELETE FROM cart_items WHERE cart_item_id = ?", (int(cart_item_id),))
        else:
            conn.execute(
                "UPDATE cart_items SET quantity = ? WHERE cart_item_id = ?",
                (quantity, int(cart_item_id)),
            )

        conn.execute(
            """
            UPDATE carts SET updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (int(user_id),),
        )
        conn.commit()
        return True, "Cart updated."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def remove_cart_item(user_id, cart_item_id):
    return update_cart_item(user_id, cart_item_id, 0)


def clear_cart(user_id):
    """Remove every item from the current user's cart."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT cart_id FROM carts WHERE user_id = ? LIMIT 1",
            (int(user_id),),
        ).fetchone()
        if row is None:
            return True, "Cart is already empty."
        conn.execute("DELETE FROM cart_items WHERE cart_id = ?", (row["cart_id"],))
        conn.execute(
            "UPDATE carts SET updated_at = CURRENT_TIMESTAMP WHERE cart_id = ?",
            (row["cart_id"],),
        )
        conn.commit()
        return True, "Cart cleared."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def get_cart_totals(items):
    """Calculate subtotal and item count from queried cart rows."""
    item_count = sum(int(row["quantity"]) for row in items)
    subtotal = sum(float(row["line_total"]) for row in items)
    return item_count, subtotal


def render_cart():
    """Render the complete shopping cart and connect it to the future checkout stage."""
    user_id = st.session_state.user["user_id"]
    st.markdown("## 🛒 Shopping Cart")
    st.caption("Review your books, change quantities, or remove items before checkout.")

    items = get_cart_items(user_id)
    item_count, subtotal = get_cart_totals(items)

    if not items:
        st.markdown(
            """
            <div class="hero" style="text-align:center;">
                <div style="font-size:4rem;">🛒</div>
                <div class="hero-title" style="font-size:1.8rem;">Your cart is empty</div>
                <div class="hero-subtitle">Browse the catalogue and add books you would like to purchase.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("📚 Browse Books", type="primary", use_container_width=True):
            st.session_state.page = "Browse Books"
            st.rerun()
        return

    left, right = st.columns([1.65, 1], gap="large")

    with left:
        st.markdown(f"### 📚 Your Items ({item_count})")
        for item in items:
            with st.container(border=True):
                c1, c2, c3 = st.columns([4.1, 1.35, 1.35])
                with c1:
                    st.markdown(f"**{html.escape(str(item['title']))}**")
                    st.caption(f"{html.escape(str(item['author']))} · {html.escape(str(item['publisher'] or 'Publisher N/A'))}")
                    rating = item["avg_rating"]
                    rating_text = f"⭐ {float(rating):.1f}" if rating is not None else "⭐ N/A"
                    st.caption(f"{rating_text} · ₹{float(item['price']):,.2f} each")
                with c2:
                    new_qty = st.number_input(
                        "Qty",
                        min_value=1,
                        max_value=99,
                        value=int(item["quantity"]),
                        step=1,
                        key=f"cart_qty_{item['cart_item_id']}",
                    )
                    if int(new_qty) != int(item["quantity"]):
                        if st.button("Update", key=f"cart_update_{item['cart_item_id']}", use_container_width=True):
                            ok, message = update_cart_item(user_id, item["cart_item_id"], int(new_qty))
                            if ok:
                                st.rerun()
                            st.error(message)
                with c3:
                    st.markdown("**Line Total**")
                    st.markdown(f"### ₹{float(item['line_total']):,.2f}")
                    if st.button("🗑 Remove", key=f"cart_remove_{item['cart_item_id']}", use_container_width=True):
                        ok, message = remove_cart_item(user_id, item["cart_item_id"])
                        if ok:
                            st.rerun()
                        st.error(message)

        if st.button("🧹 Clear Cart", use_container_width=False):
            ok, message = clear_cart(user_id)
            if ok:
                st.rerun()
            st.error(message)

    with right:
        st.markdown("### 💳 Order Summary")
        st.markdown(
            f"""
            <div class="metric-card">
                <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
                    <span>Items</span><b>{item_count}</b>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
                    <span>Subtotal</span><b>₹{subtotal:,.2f}</b>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:10px;">
                    <span>Delivery</span><b>₹0.00</b>
                </div>
                <hr>
                <div style="display:flex;justify-content:space-between;font-size:1.2rem;">
                    <b>Total</b><b style="color:#493B68;">₹{subtotal:,.2f}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")
        st.info("Demo checkout")
        if st.button("⚡ Proceed to Checkout", type="primary", use_container_width=True):
            st.session_state.page = "Checkout"
            st.rerun()
        if st.button("📚 Continue Shopping", use_container_width=True):
            st.session_state.page = "Browse Books"
            st.rerun()


# ---------- Book Details ----------
def get_book_details(book_id):
    conn = get_db_connection()
    try:
        return conn.execute(
            """
            SELECT book_id, isbn, title, author, publisher, publication_year,
                   avg_rating, price
            FROM books
            WHERE book_id = ?
            LIMIT 1
            """,
            (int(book_id),),
        ).fetchone()
    finally:
        conn.close()


def get_similar_books(book):
    """Return ML content-based recommendations with a safe catalogue fallback."""
    try:
        payload = get_recommender_model()
        return recommend_similar_from_model(payload, int(book["book_id"]), n=6)
    except Exception:
        # Keep Book Details usable if a trained model is unavailable/corrupt.
        conn = get_db_connection()
        try:
            book_id = int(book["book_id"])
            author = str(book["author"] or "").strip()
            publisher = str(book["publisher"] or "").strip()
            year = book["publication_year"]
            rows = []
            if author:
                rows = conn.execute(
                    """SELECT book_id, title, author, publisher, publication_year, avg_rating, price
                       FROM books WHERE book_id <> ? AND author = ?
                       ORDER BY avg_rating IS NULL, avg_rating DESC, title ASC LIMIT 6""",
                    (book_id, author),
                ).fetchall()
            if len(rows) < 6 and publisher:
                excluded = [book_id] + [int(r["book_id"]) for r in rows]
                ph = ",".join("?" for _ in excluded)
                rows.extend(conn.execute(
                    f"""SELECT book_id, title, author, publisher, publication_year, avg_rating, price
                        FROM books WHERE publisher = ? AND book_id NOT IN ({ph})
                        ORDER BY avg_rating IS NULL, avg_rating DESC, title ASC LIMIT ?""",
                    [publisher] + excluded + [6 - len(rows)],
                ).fetchall())
            if len(rows) < 6 and year:
                excluded = [book_id] + [int(r["book_id"]) for r in rows]
                ph = ",".join("?" for _ in excluded)
                rows.extend(conn.execute(
                    f"""SELECT book_id, title, author, publisher, publication_year, avg_rating, price
                        FROM books WHERE publication_year BETWEEN ? AND ?
                        AND book_id NOT IN ({ph})
                        ORDER BY ABS(publication_year - ?) ASC, avg_rating IS NULL, avg_rating DESC
                        LIMIT ?""",
                    [int(year) - 3, int(year) + 3] + excluded + [int(year), 6 - len(rows)],
                ).fetchall())
            return rows[:6]
        finally:
            conn.close()


def is_in_wishlist(user_id, book_id):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM wishlist WHERE user_id = ? AND book_id = ? LIMIT 1",
            (user_id, book_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def toggle_wishlist(user_id, book_id):
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT wishlist_id FROM wishlist WHERE user_id = ? AND book_id = ? LIMIT 1",
            (user_id, book_id),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM wishlist WHERE wishlist_id = ?", (existing["wishlist_id"],))
            action = "removed"
        else:
            conn.execute(
                "INSERT INTO wishlist (user_id, book_id) VALUES (?, ?)",
                (user_id, book_id),
            )
            action = "added"
        conn.execute(
            "INSERT INTO user_interactions (user_id, book_id, interaction_type) VALUES (?, ?, 'wishlist')",
            (user_id, book_id),
        )
        conn.commit()
        return True, action
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def record_book_view(user_id, book_id):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO user_interactions (user_id, book_id, interaction_type) VALUES (?, ?, 'view')",
            (user_id, book_id),
        )
        conn.commit()
    finally:
        conn.close()


def render_book_details():
    book_id = st.session_state.get("selected_book_id")
    if not book_id:
        st.warning("No book has been selected.")
        if st.button("← Back to Browse Books"):
            st.session_state.page = "Browse Books"
            st.rerun()
        return

    book = get_book_details(book_id)
    if book is None:
        st.error("The selected book could not be found in the catalogue.")
        if st.button("← Back to Browse Books"):
            st.session_state.page = "Browse Books"
            st.rerun()
        return

    user_id = st.session_state.user["user_id"]
    view_key = f"view_logged_{user_id}_{book_id}"
    if not st.session_state.get(view_key, False):
        record_book_view(user_id, book_id)
        st.session_state[view_key] = True

    title = html.escape(str(book["title"] or "Untitled"))
    author = html.escape(str(book["author"] or "Unknown Author"))
    publisher = html.escape(str(book["publisher"] or "Unknown Publisher"))
    isbn = html.escape(str(book["isbn"] or "N/A"))
    rating = book["avg_rating"]
    rating_text = f"{float(rating):.1f} ⭐" if rating is not None else "Not rated"
    price = float(book["price"] or 0)
    year = book["publication_year"] or "Not available"
    wished = is_in_wishlist(user_id, book_id)

    if st.button("← Back to Browse Books", use_container_width=False):
        st.session_state.page = "Browse Books"
        st.rerun()

    st.markdown(
        f"""
        <div class="hero">
            <div style="font-size:3.5rem;margin-bottom:8px;">📖</div>
            <div class="hero-title" style="font-size:2rem;">{title}</div>
            <div class="hero-subtitle">by <b>{author}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.5, 1])
    with left:
        st.markdown("### 📚 Book Information")
        info_rows = [
            ("Author", author),
            ("Publisher", publisher),
            ("Publication Year", str(year)),
            ("ISBN", isbn),
            ("Rating", rating_text),
        ]
        for label, value in info_rows:
            c1, c2 = st.columns([1, 2.5])
            with c1:
                st.markdown(f"**{label}**")
            with c2:
                st.markdown(value)

        st.markdown("### 📝 About This Book")
        st.info(
            "A full book description is not available because the supplied dataset "
            "contains catalogue metadata only. The details above are taken directly "
            "from the bookstore catalogue."
        )

    with right:
        st.markdown(
            f"""<div class="metric-card" style="text-align:center;">
                <div class="small-muted">Listed Price</div>
                <div style="font-size:2.1rem;font-weight:700;color:#493B68;">₹{price:,.0f}</div>
                <div class="small-muted">{rating_text}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        st.write("")

        if st.button("🛒 Add to Cart", type="primary", use_container_width=True, key=f"detail_add_{book_id}"):
            ok, message = add_book_to_cart(user_id, book_id)
            if ok:
                st.success("Book added to your cart.", icon="🛒")
            else:
                st.error(message)

        if st.button("⚡ Buy Now", use_container_width=True, key=f"detail_buy_{book_id}"):
            ok, message = add_book_to_cart(user_id, book_id)
            if ok:
                st.session_state.page = "Cart"
                st.session_state.checkout_from_book = book_id
                st.rerun()
            else:
                st.error(message)

        wish_label = "💔 Remove from Wishlist" if wished else "❤️ Add to Wishlist"
        if st.button(wish_label, use_container_width=True, key=f"detail_wish_{book_id}"):
            ok, action = toggle_wishlist(user_id, book_id)
            if ok:
                st.success("Added to wishlist." if action == "added" else "Removed from wishlist.")
                st.rerun()
            else:
                st.error(action)

    st.divider()
    st.markdown("### ✨ You May Also Like")
    similar = get_similar_books(book)
    if similar:
        for start in range(0, len(similar), 3):
            cols = st.columns(3, gap="medium")
            for col, item in zip(cols, similar[start:start + 3]):
                with col:
                    item_title = html.escape(str(item["title"] or "Untitled"))
                    item_author = html.escape(str(item["author"] or "Unknown Author"))
                    item_rating = item["avg_rating"]
                    item_rating_text = f"⭐ {float(item_rating):.1f}" if item_rating is not None else "⭐ N/A"
                    item_price = float(item["price"] or 0)
                    st.markdown(
                        f"""<div style="background:#fff;border:1px solid #DDD4F2;border-radius:16px;padding:16px;min-height:190px;">
                            <div style="font-size:2.2rem;text-align:center;">📖</div>
                            <div style="font-weight:700;min-height:44px;">{item_title}</div>
                            <div class="small-muted">{item_author}</div>
                            <div style="margin-top:8px;">{item_rating_text} &nbsp;|&nbsp; ₹{item_price:,.0f}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    if st.button("View", key=f"similar_{item['book_id']}", use_container_width=True):
                        st.session_state.selected_book_id = int(item["book_id"])
                        st.rerun()
    else:
        st.info("No closely related books were found in the current catalogue.")


def render_recommendations():
    """Show personalized recommendations first, with content-based fallback."""
    st.markdown("## 🤖 AI Book Recommendations")
    st.caption("Recommendations learn from your own activity while keeping every result grounded in the real catalogue.")

    user_id = st.session_state.user["user_id"]
    try:
        personalized, meta = get_personalized_recommendations(user_id, n=8)
    except Exception as exc:
        personalized, meta = [], {"personalized": False, "interaction_count": 0, "seed_count": 0}
        st.warning(f"Personalized recommendations are temporarily unavailable: {exc}")

    if personalized:
        st.markdown("### ✨ Recommended For You")
        st.success(
            f"Personalized from {meta['interaction_count']} recent interaction(s) across "
            f"{meta['seed_count']} preference signal(s)."
        )
        render_recommendation_cards(personalized, key_prefix="personalized")
    else:
        st.markdown("### 🌟 Popular Picks For You")
        st.info(
            "You haven't built enough reading activity yet. Explore a few books, add a wishlist item, "
            "or put a book in your cart and this section will start adapting to your interests."
        )
        popular = get_popular_recommendations(8)
        render_recommendation_cards(popular, key_prefix="popular")

    st.divider()
    st.markdown("### 🔎 Explore Similar Books")
    st.caption("Choose any catalogue book to see content-based recommendations using title, author and publisher.")

    choices = get_book_choices(30)
    if not choices:
        st.warning("No books are available for recommendations.")
        return

    selected_id = st.session_state.get("selected_book_id")
    choice_ids = {int(r["book_id"]) for r in choices}
    default_index = next(
        (i for i, r in enumerate(choices) if int(r["book_id"]) == int(selected_id)),
        0,
    ) if selected_id in choice_ids else 0

    labels = [
        f"{r['title']} — {r['author']}"
        + (f" (⭐ {float(r['avg_rating']):.1f})" if r['avg_rating'] is not None else "")
        for r in choices
    ]
    selected_label = st.selectbox(
        "Choose a book to get similar recommendations",
        labels,
        index=default_index,
        key="similar_book_selector",
    )
    selected_book = choices[labels.index(selected_label)]

    try:
        payload = get_recommender_model()
        recommendations = recommend_similar_from_model(payload, int(selected_book["book_id"]), n=8)
    except Exception as exc:
        st.error(f"Recommendation model could not be loaded: {exc}")
        return

    if recommendations:
        render_recommendation_cards(recommendations, key_prefix="similar")
    else:
        st.warning("No similar books were found.")

    st.divider()
    st.markdown("### 🧠 How personalization works")
    a, b, c = st.columns(3)
    with a:
        st.markdown("**1. Your activity**")
        st.caption("Views, wishlist, cart and future purchases create preference signals.")
    with b:
        st.markdown("**2. Intent weighting**")
        st.caption("Stronger actions receive more weight, with recent activity contributing more.")
    with c:
        st.markdown("**3. Content similarity**")
        st.caption("TF-IDF similarity expands your preferred books into new catalogue suggestions.")


def get_popular_recommendations(limit=8):
    """Cold-start recommendations based only on catalogue quality signals."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT book_id, isbn, title, author, publisher, publication_year, avg_rating, price
               FROM books
               WHERE avg_rating IS NOT NULL
               ORDER BY avg_rating DESC, title ASC
               LIMIT ?""",
            (int(limit),),
        ).fetchall()
        return rows
    finally:
        conn.close()


def render_recommendation_cards(rows, key_prefix="recommendation"):
    if not rows:
        st.info("No recommendations are available yet.")
        return

    for start in range(0, len(rows), 4):
        cols = st.columns(4, gap="medium")
        for col, book in zip(cols, rows[start:start + 4]):
            with col:
                title = html.escape(str(book["title"] or "Untitled"))
                author = html.escape(str(book["author"] or "Unknown Author"))
                rating = book["avg_rating"]
                rating_text = f"⭐ {float(rating):.1f}" if rating is not None else "⭐ N/A"
                price = float(book["price"] or 0)
                reason = book.get("reason_interaction") if isinstance(book, dict) else None
                reason_text = {
                    "view": "Based on a book you viewed",
                    "wishlist": "Based on your wishlist",
                    "cart": "Based on a book in your cart",
                    "purchase": "Based on a previous purchase",
                }.get(reason, "AI content match")

                st.markdown(
                    f"""<div style="background:#fff;border:1px solid #DDD4F2;border-radius:16px;
                                padding:16px;min-height:215px;box-shadow:0 3px 12px rgba(70,50,100,.06);">
                        <div style="font-size:2.2rem;text-align:center;">📖</div>
                        <div style="font-weight:700;min-height:44px;">{title}</div>
                        <div class="small-muted">{author}</div>
                        <div style="margin-top:8px;">{rating_text} &nbsp;|&nbsp; ₹{price:,.0f}</div>
                        <div class="small-muted" style="margin-top:8px;">{html.escape(reason_text)}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                if st.button(
                    "View Details",
                    key=f"{key_prefix}_{int(book['book_id'])}",
                    use_container_width=True,
                ):
                    st.session_state.selected_book_id = int(book["book_id"])
                    st.session_state.page = "Book Details"
                    st.rerun()


def record_bot_search(user_id, books):
    if not books:
        return
    conn = get_db_connection()
    try:
        conn.executemany(
            "INSERT INTO user_interactions (user_id, book_id, interaction_type) VALUES (?, ?, 'search')",
            [(int(user_id), int(book["book_id"])) for book in books[:6]],
        )
        conn.commit()
    finally:
        conn.close()


def render_book_bot():
    """Grounded chatbot UI: every catalogue result comes from SQLite/ML."""
    st.markdown("## 💬 Book Bot")
    st.caption("Ask about books, authors, prices, ratings, publication years, or recommendations. Results are grounded in the bookstore catalogue.")

    examples = [
        "📚 Recommend some books",
        "✍️ Books by Agatha Christie",
        "💰 Books under ₹500",
        "⭐ Top rated books",
        "📅 Books published in 2000",
        "📖 Tell me about a book",
    ]
    st.markdown("### Try asking")
    example_cols = st.columns(3)
    for i, example in enumerate(examples):
        with example_cols[i % 3]:
            if st.button(example, key=f"bot_example_{i}", use_container_width=True):
                st.session_state["book_bot_input"] = example.split(" ", 1)[1]
                st.rerun()

    message = st.text_input(
        "Your question",
        key="book_bot_input",
        placeholder="e.g. Find books by Agatha Christie",
    )

    if st.button("Ask Book Bot", type="primary", use_container_width=True):
        personalized_for_bot = []
        try:
            personalized_for_bot, _ = get_personalized_recommendations(st.session_state.user["user_id"], n=6)
        except Exception:
            personalized_for_bot = []
        result = answer_catalogue_query(message, personalized_recommendations=personalized_for_bot)
        st.session_state["book_bot_last_result"] = result
        if result.get("books"):
            record_bot_search(st.session_state.user["user_id"], result["books"])

    result = st.session_state.get("book_bot_last_result")
    if not result:
        st.info("The Book Bot searches the real catalogue and does not invent books or catalogue details.")
        return

    st.markdown(f"### 🤖 {html.escape(result['text'])}")
    books = result.get("books", [])
    if not books:
        st.warning("No matching catalogue records were found.")
        return

    for start in range(0, len(books), 3):
        cols = st.columns(3, gap="medium")
        for col, book in zip(cols, books[start:start + 3]):
            with col:
                title = html.escape(book["title"])
                author = html.escape(book["author"])
                rating = book["avg_rating"]
                rating_text = f"⭐ {rating:.1f}" if rating is not None else "⭐ N/A"
                st.markdown(
                    f"""<div style="background:#fff;border:1px solid #DDD4F2;border-radius:16px;padding:16px;min-height:190px;">
                        <div style="font-size:2.2rem;text-align:center;">📖</div>
                        <div style="font-weight:700;min-height:44px;">{title}</div>
                        <div class="small-muted">{author}</div>
                        <div style="margin-top:8px;">{rating_text} &nbsp;|&nbsp; ₹{book['price']:,.0f}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                if st.button("View Details", key=f"bot_book_{result['intent']}_{book['book_id']}", use_container_width=True):
                    st.session_state.selected_book_id = int(book["book_id"])
                    st.session_state.page = "Book Details"
                    st.rerun()



# ---------- Wishlist ----------
def render_wishlist():
    user_id = int(st.session_state.user["user_id"])
    st.markdown("## ❤️ Wishlist")
    st.caption("Books you saved for later.")

    rows = get_user_wishlist(user_id)
    if not rows:
        st.info("Your wishlist is empty. Open a book and choose 'Add to Wishlist'.")
        if st.button("📚 Browse Books", type="primary", use_container_width=True):
            st.session_state.page = "Browse Books"
            st.rerun()
        return

    st.markdown(f"### Saved Books ({len(rows)})")
    for start in range(0, len(rows), 3):
        cols = st.columns(3, gap="medium")
        for col, book in zip(cols, rows[start:start + 3]):
            with col:
                title = html.escape(str(book["title"] or "Untitled"))
                author = html.escape(str(book["author"] or "Unknown Author"))
                rating = book["avg_rating"]
                rating_text = f"⭐ {float(rating):.1f}" if rating is not None else "⭐ N/A"
                price = float(book["price"] or 0)
                st.markdown(
                    f"""<div style="background:#fff;border:1px solid #DDD4F2;border-radius:16px;
                    padding:16px;min-height:210px;box-shadow:0 3px 12px rgba(70,50,100,.06);">
                    <div style="font-size:2.2rem;text-align:center;">📖</div>
                    <div style="font-weight:700;min-height:44px;">{title}</div>
                    <div class="small-muted">{author}</div>
                    <div style="margin-top:8px;">{rating_text} &nbsp;|&nbsp; ₹{price:,.0f}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("View", key=f"wish_view_{book['book_id']}", use_container_width=True):
                        st.session_state.selected_book_id = int(book["book_id"])
                        st.session_state.page = "Book Details"
                        st.rerun()
                with c2:
                    if st.button("🛒 Add", key=f"wish_cart_{book['book_id']}", use_container_width=True):
                        ok, message = add_book_to_cart(user_id, int(book["book_id"]))
                        if ok:
                            st.success("Added", icon="🛒")
                        else:
                            st.error(message)
                with c3:
                    if st.button("Remove", key=f"wish_remove_{book['book_id']}", use_container_width=True):
                        ok, message = remove_from_wishlist(user_id, int(book["book_id"]))
                        if ok:
                            st.rerun()
                        else:
                            st.error(message)


# ---------- Profile ----------
def render_profile():
    user_id = int(st.session_state.user["user_id"])
    profile = get_profile(user_id)
    if profile is None:
        st.error("Your profile could not be found.")
        return

    st.markdown("## 👤 Profile")
    st.caption("Manage your bookstore account information.")

    with st.container(border=True):
        st.markdown("### Account Information")
        name = st.text_input("Full Name", value=profile["name"], key="profile_name")
        st.text_input("Email", value=profile["email"], disabled=True, key="profile_email")
        st.text_input("Role", value=str(profile["role"]).title(), disabled=True, key="profile_role")
        st.text_input("Member Since", value=str(profile["created_at"]), disabled=True, key="profile_created")

        if st.button("Save Name", type="primary", use_container_width=True):
            ok, message = update_name(user_id, name)
            if ok:
                refreshed = get_profile(user_id)
                st.session_state.user["name"] = refreshed["name"]
                st.success(message, icon="✅")
                st.rerun()
            else:
                st.error(message)

# ---------- Home Dashboard ----------
def render_home():
    user = st.session_state.user
    stats = get_home_stats()
    cart_items, cart_total = get_cart_summary(user["user_id"])
    order_count, total_spent = get_user_order_summary(user["user_id"])

    st.markdown("""
    <div class="hero">
        <div class="hero-title">📚 E-Commerce Books</div>
        <div class="hero-subtitle">
            To buy a book is to willingly choose a companion.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"### Welcome back, {user['name']} 👋")
    st.caption("Discover books, explore authors, and find your next read.")

    # Summary cards
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""<div class="metric-card">
                <div class="small-muted">📚 Total Books</div>
                <div style="font-size:1.8rem;font-weight:700;color:#493B68;">
                    {stats["total_books"]:,}
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""<div class="metric-card">
                <div class="small-muted">🛒 Cart Items</div>
                <div style="font-size:1.8rem;font-weight:700;color:#493B68;">
                    {cart_items}
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""<div class="metric-card">
                <div class="small-muted">📦 Your Orders</div>
                <div style="font-size:1.8rem;font-weight:700;color:#493B68;">
                    {order_count}
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""<div class="metric-card">
                <div class="small-muted">💰 Total Spent</div>
                <div style="font-size:1.8rem;font-weight:700;color:#493B68;">
                    ₹{total_spent:,.0f}
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.write("")

    # Main dashboard sections
    left, right = st.columns([1.45, 1])

    with left:
        st.markdown("### ⭐ Top Rated Books")

        for book in stats["top_rated"]:
            with st.container(border=True):
                b1, b2, b3 = st.columns([3.2, 1, 1])

                with b1:
                    st.markdown(f"**{book['title']}**")
                    st.caption(book["author"])

                with b2:
                    rating = book["avg_rating"]
                    st.markdown(f"⭐ **{rating:.1f}**")

                with b3:
                    st.markdown(f"**₹{book['price']:,.0f}**")

        st.markdown("### ✍️ Books by Popular Authors")

        for author in stats["authors"]:
            a1, a2 = st.columns([4, 1])
            with a1:
                st.markdown(f"**{author['author']}**")
            with a2:
                st.caption(f"{author['book_count']} books")

    with right:
        st.markdown("### 🛒 Purchase Details")

        st.markdown(
            f"""<div class="metric-card">
                <b>Current Cart</b>
                <h2 style="color:#493B68;">₹{cart_total:,.0f}</h2>
                <p class="small-muted">{cart_items} item(s) in your cart</p>
            </div>""",
            unsafe_allow_html=True,
        )

        st.write("")

        if st.button("🛒 Open Cart", use_container_width=True):
            st.session_state.page = "Cart"
            st.rerun()

        if st.button("📚 Browse Books", type="primary", use_container_width=True):
            st.session_state.page = "Browse Books"
            st.rerun()

        if st.button("📦 View My Orders", use_container_width=True):
            st.session_state.page = "My Orders"
            st.rerun()

        st.markdown("### 💬 Book Bot")

        st.info(
            "Ask the Book Bot to find books, authors, recommendations, "
            "or help you navigate the bookstore."
        )

        if st.button("🤖 Open Book Bot", use_container_width=True):
            st.session_state.page = "Book Bot"
            st.rerun()

    st.divider()

    # Store overview
    st.markdown("### 📊 Store Overview")

    o1, o2, o3 = st.columns(3)

    with o1:
        st.markdown(
            f"""<div class="metric-card">
                <b>Lowest Listed Price</b>
                <h3>₹{stats["min_price"]:,.0f}</h3>
            </div>""",
            unsafe_allow_html=True,
        )

    with o2:
        st.markdown(
            f"""<div class="metric-card">
                <b>Average Book Price</b>
                <h3>₹{stats["avg_price"]:,.0f}</h3>
            </div>""",
            unsafe_allow_html=True,
        )

    with o3:
        st.markdown(
            f"""<div class="metric-card">
                <b>Highest Listed Price</b>
                <h3>₹{stats["max_price"]:,.0f}</h3>
            </div>""",
            unsafe_allow_html=True,
        )



# ---------- Admin Dashboard ----------
def render_admin_dashboard():
    """Render admin-only catalogue, user, order and interaction analytics."""
    user = st.session_state.get("user")
    if not require_admin(user):
        st.error("Admin access is required to view this page.")
        st.session_state.page = "Home"
        return

    st.markdown("## 👨‍💼 Admin Dashboard")
    st.caption("Monitor the bookstore catalogue, users, orders and customer activity.")

    metrics = get_admin_metrics()
    m1, m2, m3, m4 = st.columns(4)
    metric_data = [
        (m1, "📚 Total Books", f"{metrics['total_books']:,}"),
        (m2, "👥 Users", f"{metrics['total_users']:,}"),
        (m3, "📦 Orders", f"{metrics['total_orders']:,}"),
        (m4, "💰 Revenue", f"₹{float(metrics['total_revenue']):,.2f}"),
    ]
    for col, label, value in metric_data:
        with col:
            st.markdown(
                f"<div class='metric-card'><div class='small-muted'>{label}</div>"
                f"<div style='font-size:1.65rem;font-weight:700;color:#493B68;'>{value}</div></div>",
                unsafe_allow_html=True,
            )

    st.write("")
    a, b, c = st.columns(3)
    for col, label, value in [
        (a, "🛒 Active Carts", metrics["active_carts"]),
        (b, "❤️ Wishlist Items", metrics["wishlist_items"]),
        (c, "🧠 Interactions", metrics["interactions"]),
    ]:
        with col:
            st.markdown(
                f"<div class='metric-card'><div class='small-muted'>{label}</div>"
                f"<div style='font-size:1.45rem;font-weight:700;color:#493B68;'>{int(value):,}</div></div>",
                unsafe_allow_html=True,
            )

    st.divider()
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("### 📊 Order Status")
        status_rows = get_order_status_counts()
        if status_rows:
            import pandas as pd
            status_df = pd.DataFrame([dict(r) for r in status_rows])
            status_df = status_df.set_index("status")
            st.bar_chart(status_df["order_count"])
        else:
            st.info("No orders have been placed yet.")

    with right:
        st.markdown("### 🔥 Most Interacted Books")
        interaction_rows = get_top_interacted_books(8)
        if interaction_rows:
            for row in interaction_rows:
                st.markdown(
                    f"**{html.escape(str(row['title']))}** — {html.escape(str(row['author'] or 'Unknown'))} "
                    f"· {int(row['interactions'])} interaction(s)"
                )
        else:
            st.info("Customer interaction data will appear here as users browse the store.")

    st.divider()
    st.markdown("### 🏆 Top Ordered Books")
    ordered_rows = get_top_ordered_books(8)
    if ordered_rows:
        import pandas as pd
        ordered_df = pd.DataFrame([
            {
                "Book": row["title"],
                "Author": row["author"] or "Unknown",
                "Units Sold": int(row["units_sold"]),
                "Sales": round(float(row["sales"]), 2),
            }
            for row in ordered_rows
        ])
        st.dataframe(ordered_df, use_container_width=True, hide_index=True)
    else:
        st.info("No completed orders are available yet.")

    st.divider()
    st.markdown("### 📦 Order Management")
    status_filter = st.selectbox(
        "Filter orders",
        ["All"] + list(ALLOWED_STATUSES),
        key="admin_order_filter",
    )
    recent_orders = get_recent_orders(25, status_filter)
    if recent_orders:
        for order in recent_orders:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2.2, 1.2, 1.5])
                with c1:
                    st.markdown(f"**Order #{int(order['order_id'])}**")
                    st.caption(
                        f"{order['order_date']} · {order['customer_name'] or order['account_email']} · "
                        f"{int(order['item_count'])} item(s)"
                    )
                with c2:
                    st.markdown(f"**₹{float(order['total_amount']):,.2f}**")
                    st.caption(str(order['customer_email'] or order['account_email']))
                with c3:
                    current_status = str(order["status"])
                    choices = list(ALLOWED_STATUSES)
                    try:
                        idx = choices.index(current_status)
                    except ValueError:
                        idx = 0
                    new_status = st.selectbox(
                        "Status",
                        choices,
                        index=idx,
                        key=f"admin_status_{int(order['order_id'])}",
                    )
                    if new_status != current_status:
                        if st.button("Update", key=f"admin_update_{int(order['order_id'])}", use_container_width=True):
                            ok, message = update_order_status(int(order["order_id"]), new_status)
                            if ok:
                                st.success("Updated.", icon="✅")
                                st.rerun()
                            else:
                                st.error(message)
    else:
        st.info("No orders match the selected status.")

    st.divider()
    st.markdown("### 👥 Users")
    user_search = st.text_input(
        "Search users by name or email",
        placeholder="e.g. admin@bookstore.local",
        key="admin_user_search",
    )
    user_rows = search_users(user_search, limit=30)
    if user_rows:
        import pandas as pd
        users_df = pd.DataFrame([
            {
                "ID": int(row["user_id"]),
                "Name": row["name"],
                "Email": row["email"],
                "Role": row["role"],
                "Created": row["created_at"],
            }
            for row in user_rows
        ])
        st.dataframe(users_df, use_container_width=True, hide_index=True)
    else:
        st.info("No users match the search.")

    st.caption(
        "Catalogue data is treated as the supplied source dataset. The admin dashboard does not invent "
        "stock levels or genres that are not present in the database."
    )

# ---------- Page router ----------
def render_page():
    page = st.session_state.page

    if page == "Home":
        render_home()
    elif page == "Browse Books":
        render_browse_books()
    elif page == "Book Details":
        render_book_details()
    elif page == "Recommendations":
        render_recommendations()
    elif page == "Book Bot":
        render_book_bot()
    elif page == "Cart":
        render_cart()
    elif page == "Checkout":
        render_checkout()
    elif page == "Order Confirmation":
        render_order_confirmation()
    elif page == "My Orders":
        render_my_orders()
    elif page == "Wishlist":
        render_wishlist()
    elif page == "Profile":
        render_profile()
    elif page == "Admin Dashboard":
        render_admin_dashboard()
    else:
        st.markdown(f"## {page}")
        st.info(
            f"The **{page}** module is reserved for its planned development stage. "
            "The application shell and navigation are already connected."
        )

# ---------- App ----------
def main():
    # Keep existing databases compatible when the checkout snapshot fields are introduced.
    ensure_order_columns()
    if not st.session_state.authenticated:
        login_form()
    else:
        render_sidebar()
        render_page()


if __name__ == "__main__":
    main()
