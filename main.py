from fastapi import FastAPI
from pydantic import BaseModel
import sqlite3
import gradio as gr
import pandas as pd
from collections import Counter
import re
from deep_translator import GoogleTranslator

# =========================
# APP
# =========================
app = FastAPI(title="Quotes API", version="2.0")
DB_FILE = "quotes.db"

translator = GoogleTranslator(source="en", target="ko")

# =========================
# DB
# =========================
def db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def all_data():
    conn = db()
    df = pd.read_sql_query("SELECT * FROM quotes", conn)
    conn.close()
    return df

# =========================
# MODEL
# =========================
class QuoteCreate(BaseModel):
    text: str
    author: str
    tags: str

# =========================
# CRUD API
# =========================

@app.post("/quotes/")
def create_quote(data: QuoteCreate):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO quotes (text, author, tags) VALUES (?, ?, ?)",
        (data.text, data.author, data.tags)
    )
    conn.commit()
    conn.close()
    return {"message": "created"}

@app.get("/quotes/")
def get_quotes(limit: int = 20):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM quotes LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(x) for x in rows]

@app.patch("/quotes/{quote_id}")
def update_quote(quote_id: int, data: QuoteCreate):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE quotes SET text=?, author=?, tags=? WHERE id=?",
        (data.text, data.author, data.tags, quote_id)
    )
    conn.commit()
    conn.close()
    return {"message": "updated"}

@app.delete("/quotes/{quote_id}")
def delete_quote(quote_id: int):
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM quotes WHERE id=?", (quote_id,))
    conn.commit()
    conn.close()
    return {"message": "deleted"}

# =========================
# STATISTICS
# =========================

def stats():
    df = all_data()
    if df.empty:
        return "No data"

    total = len(df)
    authors = df["author"].nunique()

    avg_len = df["text"].apply(lambda x: len(str(x).split())).mean()

    words = re.findall(r"\b[a-zA-Z]{3,}\b", " ".join(df["text"]).lower())
    top_words = Counter(words).most_common(5)

    tags = ",".join(df["tags"].dropna()).split(",")
    top_tags = Counter(tags).most_common(5)

    return f"""
📊 STATISTICS

Total Quotes: {total}
Unique Authors: {authors}
Average Words: {avg_len:.2f}

Top Words: {top_words}
Top Tags: {top_tags}
"""

# =========================
# GALLERY
# =========================

def gallery(lang):
    df = all_data()

    if df.empty:
        return "<h3>No data</h3>"

    html = "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:15px;'>"

    for _, q in df.iterrows():
        text = q["text"]

        if lang == "Korean":
            text = translator.translate(text)

        html += f"""
        <div style='background:#1e1e1e;color:white;padding:20px;border-radius:12px;'>
            <h4>{text}</h4>
            <p>{q['author']}</p>
            <small>{q['tags']}</small>
        </div>
        """

    html += "</div>"
    return html

# =========================
# GRADIO UI
# =========================

with gr.Blocks(theme=gr.themes.Soft()) as demo:

    gr.Markdown("# 📚 Quotes System")

    with gr.Tabs():

        # SEARCH
        with gr.Tab("Search"):
            lang = gr.Radio(["English", "Korean"], value="English")
            btn = gr.Button("Load Quotes")
            out = gr.HTML()

            btn.click(gallery, lang, out)

        # MANAGE
        with gr.Tab("Manage"):
            table = gr.Dataframe(value=all_data())

            t1 = gr.Textbox(label="Text")
            t2 = gr.Textbox(label="Author")
            t3 = gr.Textbox(label="Tags")

            def add(x, y, z):
                conn = db()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO quotes (text, author, tags) VALUES (?, ?, ?)",
                    (x, y, z)
                )
                conn.commit()
                conn.close()
                return all_data()

            gr.Button("Add").click(add, [t1, t2, t3], table)

            # UPDATE
            u_id = gr.Number(label="Quote ID")
            u1 = gr.Textbox(label="New Text")
            u2 = gr.Textbox(label="New Author")
            u3 = gr.Textbox(label="New Tags")

            def update_fn(i, x, y, z):
                conn = db()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE quotes SET text=?, author=?, tags=? WHERE id=?",
                    (x, y, z, int(i))
                )
                conn.commit()
                conn.close()
                return all_data()

            gr.Button("Update").click(update_fn, [u_id, u1, u2, u3], table)

            # DELETE
            d_id = gr.Number(label="Delete Quote ID")

            def delete_fn(i):
                conn = db()
                cur = conn.cursor()
                cur.execute("DELETE FROM quotes WHERE id=?", (int(i),))
                conn.commit()
                conn.close()
                return all_data()

            gr.Button("Delete").click(delete_fn, d_id, table)

        # STATISTICS
        with gr.Tab("Statistics"):
            btn2 = gr.Button("Generate Stats")
            out2 = gr.Textbox(lines=10)

            btn2.click(stats, None, out2)

        # API INFO
        with gr.Tab("API"):
            gr.Markdown("http://127.0.0.1:8000/docs")

# =========================
# RUN
# =========================
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    demo.launch(share=True)
