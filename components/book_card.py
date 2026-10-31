
import streamlit as st

def book_card(title, author, rating, price, book_id=None):
    st.markdown(
        f"""
        <div style="
            background:#FFFFFF;
            border:1px solid #DDD4F2;
            border-radius:16px;
            padding:18px;
            min-height:180px;
            box-shadow:0 3px 12px rgba(70,50,100,.06);
        ">
            <div style="font-size:2rem;text-align:center;">📖</div>
            <div style="font-weight:700;color:#302B3A;">{title}</div>
            <div style="color:#77717F;">{author}</div>
            <div style="margin-top:8px;">⭐ {rating:.1f} &nbsp; | &nbsp; ₹{price:,.0f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
