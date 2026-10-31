# AI-Based E-Commerce Book Store & Intelligent Recommendation System

A Python + Streamlit + SQLite + Scikit-learn academic project for an AI-powered online bookstore.

## Current status

Stages 1–19 are implemented. The final release was regression-tested with 26 automated tests.

Core features:
- User registration and secure login
- Role-based Admin/User access
- Home dashboard
- Browse/search/filter/sort/paginated book catalogue
- Book details
- Wishlist
- Shopping cart
- Demo checkout and order creation
- My Orders and order details
- Admin dashboard and order-status management
- Content-based ML recommendations using TF-IDF + nearest neighbours
- Personalized recommendations using the logged-in user's interactions
- Catalogue-grounded Book Bot
- SQLite persistence
- Automated regression tests

## Dataset

The supplied catalogue contains 149,942 books. The application uses the actual catalogue fields and does not invent genres, descriptions, stock levels, or user-rating history that are not present in the source data.

## Technology

- Python
- Streamlit
- SQLite
- Pandas
- NumPy
- Scikit-learn
- Joblib

## Project structure

```text
AI_BOOK_STORE/
├── app.py
├── bookstore.db
├── requirements.txt
├── README.md
├── components/
│   └── book_card.py
├── ml/
│   ├── recommender.py
│   ├── train_recommender.py
│   └── models/
│       └── content_recommender.joblib
├── utils/
│   ├── auth.py
│   ├── admin.py
│   ├── book_bot.py
│   ├── orders.py
│   ├── order_history.py
│   ├── profile.py
│   └── wishlist.py
└── tests/
    ├── test_auth.py
    ├── test_admin.py
    ├── test_book_bot.py
    ├── test_cart.py
    ├── test_orders.py
    ├── test_order_history.py
    ├── test_personalization.py
    ├── test_profile_wishlist.py
    └── test_recommender.py
```

## Installation

Create/activate a Python environment and run:

```bash
pip install -r requirements.txt
```

Then start the application:

```bash
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

GitHub stores the source code; Streamlit Community Cloud runs the Streamlit app.

1. Push this project to a GitHub repository. Keep `bookstore.db` and
   `ml/models/content_recommender.joblib` in the repository; the app needs both
   files to load the catalogue and recommendations.
2. In [Streamlit Community Cloud](https://share.streamlit.io/), create an app
   from that repository, select the branch, and set the main file to `app.py`.
3. Deploy. Streamlit installs the dependencies from `requirements.txt`.

The included database contains demo accounts and is intended only for a demo.
The documented development admin credentials are public, so do not use this
setup for real users or sensitive information. Streamlit Community Cloud's
local filesystem is not durable: account, wishlist, cart, and order changes
written to SQLite may be lost when the app restarts or redeploys. Use a managed
database and replace the demo admin setup before using the app with real data.
Do not commit `.streamlit/secrets.toml` or other credentials; configure secrets
in the app's Streamlit Cloud settings instead.

## Login

### Normal user

Use **Create Account** on the login page. New registrations are always created with the customer role.

### Development admin

```text
Email: admin@bookstore.local
Password: Admin@12345
```

This is a development credential only. Change it before deployment or final production use.

## Testing

From the project directory:

```bash
python -m pytest -q
```

The final regression suite contains 26 tests; the last run completed with 26 passed.

## Notes

- Checkout is a demo checkout; no real payment gateway is used.
- Book images are not required because the supplied dataset does not contain book images.
- Recommendations are content-based; collaborative filtering is not claimed because the supplied dataset has no multi-user rating/history matrix.
- Streamlit UI/browser testing should be performed in the target Python environment after installing the requirements.


## Final release checklist

1. Create and activate a virtual environment.
2. Install runtime dependencies with `pip install -r requirements.txt`.
3. Start with `streamlit run app.py` (or use `run_app.bat` / `run_app.sh`).
4. For development testing, install `requirements-dev.txt` and run `python -m pytest -q`.
5. For a final/demo deployment, replace the development admin password before use.

The included `bookstore.db` and `ml/models/content_recommender.joblib` are required for the supplied catalogue and trained recommendation experience; they are intentionally included in this release.
