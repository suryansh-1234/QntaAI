import os
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, render_template, request, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-development-secret"
)

DATABASE = os.environ.get(
    "DATABASE_PATH",
    "qntaai.db"
)

OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    ""
).strip()

OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)

OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL",
    "openrouter/auto"
)

APP_URL = os.environ.get(
    "APP_URL",
    "http://localhost:5000"
)

APP_TITLE = "QntaAI"

MAX_MESSAGE_LENGTH = 8000
MAX_HISTORY_MESSAGES = 30
MAX_SEARCH_RESULTS = 5

SYSTEM_PROMPT = """
You are QntaAI, a helpful AI tutor and general assistant.

Rules:
- Do not repeatedly introduce yourself.
- Answer directly and clearly.
- Keep responses reasonably concise unless the user asks for detail.
- Explain difficult ideas in an easy-to-understand way.
- If web information is provided, use it as supporting context.
- Do not claim that you searched the web unless web information was actually provided.
- If the available information is insufficient, say so instead of inventing facts.
- Suryansh created you.

Math formatting:
- Do not use LaTeX for mathematical expressions.
- Write math using plain text instead.
- For example, write "x^2" instead of "$x^2$".
- Write "x^3 / 3 + C" instead of "\\frac{x^3}{3} + C".

Conversation context:
- Treat the recent conversation as important context.
- Always consider the immediately preceding user and assistant messages when answering a follow-up.
- Follow-up questions such as "does it", "is that", "why", "how", "what about it", and similar short questions usually refer to the most relevant concept, answer, or object from the immediately preceding messages.
- If the user uses a pronoun such as "it", "that", "this", "they", or "them", resolve it using the most recent relevant topic.
- If the user's intended meaning is reasonably clear, answer directly instead of asking for clarification.
- Do not ask the user to clarify an obvious reference from the conversation.
- Do not repeat information unnecessarily when the user is asking a follow-up question.
- For example, if the assistant just gave the integral of x^2 and the user asks "Does it come from the power rule?", interpret "it" as referring to the integral result and answer that question directly.When discussing mathematical rules, distinguish between the power rule for differentiation and the power rule for integration. Use the rule that matches the operation being discussed.If a follow-up pronoun such as "it" could reasonably refer to multiple concepts from the preceding message, do not arbitrarily choose one. Briefly address the relevant possibilities or explain the ambiguity.Full name of Suryansh is 'Suryansh Singh Bhadouriya'.He studies in St. Michael's School, Bhind.He studies in class 7th and Section E.When the user asks to practice a mathematical topic:
- Prefer giving one question at a time.
- Do not reveal the solution immediately unless asked.
- After the user answers, evaluate their work and explain mistakes.
- Gradually increase difficulty when they answer correctly.
- If the user asks for an explanation instead of practice, switch to teaching mode.
""".strip()
# ============================================================
# DATABASE
# ============================================================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_db()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_conversations_user
        ON conversations(user_id, updated_at DESC);

        CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON messages(conversation_id, id);
        """
    )

    connection.commit()
    connection.close()


init_db()
# ============================================================
# SESSION / USER
# ============================================================

def get_user_id():
    if "user_id" not in session:
        session["user_id"] = uuid.uuid4().hex

    return session["user_id"]


# ============================================================
# RATE LIMITING
# ============================================================

request_log = {}


def rate_limit_allowed(
    identifier,
    limit=20,
    window=60
):
    now = time.time()

    timestamps = request_log.get(
        identifier,
        []
    )

    timestamps = [
        timestamp
        for timestamp in timestamps
        if now - timestamp < window
    ]

    if len(timestamps) >= limit:
        request_log[identifier] = timestamps
        return False

    timestamps.append(now)

    request_log[identifier] = timestamps

    return True


# ============================================================
# HELPERS
# ============================================================

def now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


def clean_text(value):
    if not isinstance(value, str):
        return ""

    return value.strip()


def create_conversation(
    user_id,
    title="New chat"
):
    conversation_id = uuid.uuid4().hex
    timestamp = now_iso()

    connection = get_db()

    connection.execute(
        """
        INSERT INTO conversations
        (id, user_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            user_id,
            title,
            timestamp,
            timestamp
        )
    )

    connection.commit()
    connection.close()

    return conversation_id


def conversation_belongs_to_user(
    conversation_id,
    user_id
):
    connection = get_db()

    row = connection.execute(
        """
        SELECT id
        FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    ).fetchone()

    connection.close()

    return row is not None


def save_message(
    conversation_id,
    role,
    content
):
    timestamp = now_iso()

    connection = get_db()

    connection.execute(
        """
        INSERT INTO messages
        (conversation_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            conversation_id,
            role,
            content,
            timestamp
        )
    )

    connection.execute(
        """
        UPDATE conversations
        SET updated_at = ?
        WHERE id = ?
        """,
        (
            timestamp,
            conversation_id
        )
    )

    connection.commit()
    connection.close()


def get_messages(
    conversation_id
):
    connection = get_db()

    rows = connection.execute(
        """
        SELECT role, content, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (conversation_id,)
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def get_ai_messages(
    conversation_id
):
    rows = get_messages(
        conversation_id
    )

    return [
        {
            "role": row["role"],
            "content": row["content"]
        }
        for row in rows[-MAX_HISTORY_MESSAGES:]
        if row["role"] in (
            "user",
            "assistant"
        )
    ]


def update_conversation_title(
    conversation_id,
    title
):
    title = clean_text(title)

    if not title:
        title = "New chat"

    title = title[:60]

    connection = get_db()

    connection.execute(
        """
        UPDATE conversations
        SET title = ?
        WHERE id = ?
        """,
        (
            title,
            conversation_id
        )
    )

    connection.commit()
    connection.close()
# ============================================================
# WEB SEARCH
# ============================================================

def web_search(query):
    try:
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            },
            headers={
                "User-Agent": "QntaAI/1.0"
            },
            timeout=8
        )

        response.raise_for_status()

        data = response.json()

        results = []

        abstract = data.get(
            "AbstractText"
        )

        if abstract:
            results.append(
                {
                    "title": data.get(
                        "Heading",
                        "Web result"
                    ),
                    "text": abstract,
                    "url": data.get(
                        "AbstractURL",
                        ""
                    )
                }
            )

        for item in data.get(
            "RelatedTopics",
            []
        ):
            if not isinstance(item, dict):
                continue

            if "Topics" in item:
                for nested in item["Topics"]:
                    if (
                        isinstance(nested, dict)
                        and nested.get("Text")
                    ):
                        results.append(
                            {
                                "title": nested.get(
                                    "Text",
                                    ""
                                )[:100],
                                "text": nested.get(
                                    "Text",
                                    ""
                                ),
                                "url": nested.get(
                                    "FirstURL",
                                    ""
                                )
                            }
                        )

            elif item.get("Text"):
                results.append(
                    {
                        "title": item.get(
                            "Text",
                            ""
                        )[:100],
                        "text": item.get(
                            "Text",
                            ""
                        ),
                        "url": item.get(
                            "FirstURL",
                            ""
                        )
                    }
                )

            if len(results) >= MAX_SEARCH_RESULTS:
                break

        return results[:MAX_SEARCH_RESULTS]

    except requests.RequestException:
        return []

    except ValueError:
        return []

    except Exception:
        return []


def build_web_context(results):
    if not results:
        return ""

    chunks = []

    for index, result in enumerate(
        results,
        start=1
    ):
        text = result.get(
            "text",
            ""
        )

        url = result.get(
            "url",
            ""
        )

        chunks.append(
            f"[Web result {index}]\n"
            f"Information: {text}\n"
            f"Source: {url}"
        )

    return "\n\n".join(chunks)
# ============================================================
# OPENROUTER
# ============================================================

def ask_openrouter(messages):
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured on the server."
        )

    headers = {
        "Authorization": (
            f"Bearer {OPENROUTER_API_KEY}"
        ),
        "Content-Type": "application/json",
        "HTTP-Referer": APP_URL,
        "X-Title": APP_TITLE
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": 5000
    }

    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=90
    )

    if response.status_code != 200:
        try:
            error_data = response.json()
        except ValueError:
            error_data = {}

        error_object = error_data.get(
            "error",
            {}
        )

        if not isinstance(
            error_object,
            dict
        ):
            error_object = {}

        message = error_object.get(
            "message"
        )

        raise RuntimeError(
            message
            or (
                "OpenRouter returned "
                f"HTTP {response.status_code}."
            )
        )

    data = response.json()

    choices = data.get(
        "choices",
        []
    )

    if not choices:
        raise RuntimeError(
            "OpenRouter returned no response choices."
        )

    content = (
        choices[0]
        .get("message", {})
        .get("content")
    )

    if not content:
        raise RuntimeError(
            "QntaAI received an empty response."
        )

    return content
# ============================================================
# FLASK ROUTES
# ============================================================

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/conversations")
def conversations():
    user_id = get_user_id()

    connection = get_db()

    rows = connection.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (user_id,)
    ).fetchall()

    connection.close()

    return jsonify(
        [
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
            for row in rows
        ]
    )


@app.post("/api/conversations")
def new_conversation():
    user_id = get_user_id()

    conversation_id = create_conversation(
        user_id
    )

    return jsonify(
        {
            "id": conversation_id,
            "title": "New chat"
        }
    )


@app.get(
    "/api/conversations/<conversation_id>"
)
def conversation(conversation_id):
    user_id = get_user_id()

    if not conversation_belongs_to_user(
        conversation_id,
        user_id
    ):
        return jsonify(
            {
                "error": "Conversation not found."
            }
        ), 404

    return jsonify(
        {
            "id": conversation_id,
            "messages": get_messages(
                conversation_id
            )
        }
    )


@app.delete(
    "/api/conversations/<conversation_id>"
)
def delete_conversation(conversation_id):
    user_id = get_user_id()

    if not conversation_belongs_to_user(
        conversation_id,
        user_id
    ):
        return jsonify(
            {
                "error": "Conversation not found."
            }
        ), 404

    connection = get_db()

    connection.execute(
        """
        DELETE FROM messages
        WHERE conversation_id = ?
        """,
        (conversation_id,)
    )

    connection.execute(
        """
        DELETE FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    )

    connection.commit()
    connection.close()

    return jsonify(
        {
            "success": True
        }
    )
# ============================================================
# CHAT API
# ============================================================

@app.post("/api/chat")
def chat():
    user_id = get_user_id()

    client_identifier = (
        request.remote_addr or "unknown"
    )

    if not rate_limit_allowed(
        client_identifier
    ):
        return jsonify(
            {
                "error":
                    "Too many requests. Please wait a moment."
            }
        ), 429

    data = request.get_json(
        silent=True
    ) or {}

    # --------------------------------------------------------
    # Conversation ID
    # --------------------------------------------------------

    conversation_id = clean_text(
        data.get("conversation_id")
    )

    # --------------------------------------------------------
    # Get message from the old frontend format
    # --------------------------------------------------------

    prompt = clean_text(
        data.get("message")
    )

    # --------------------------------------------------------
    # Get message from our new frontend format
    #
    # The new index.html sends:
    #
    # {
    #     "messages": [
    #         {
    #             "role": "user",
    #             "content": "hello"
    #         }
    #     ],
    #     "web_search": false
    # }
    # --------------------------------------------------------

    frontend_messages = data.get(
        "messages"
    )

    if (
        not prompt
        and isinstance(
            frontend_messages,
            list
        )
    ):
        for message in reversed(
            frontend_messages
        ):
            if not isinstance(
                message,
                dict
            ):
                continue

            role = message.get(
                "role"
            )

            content = clean_text(
                message.get(
                    "content"
                )
            )

            if (
                role == "user"
                and content
            ):
                prompt = content
                break

    # --------------------------------------------------------
    # Web search
    # --------------------------------------------------------

    web_enabled = bool(
        data.get("web_search")
    )

    # --------------------------------------------------------
    # Create conversation if needed
    # --------------------------------------------------------

    if not conversation_id:
        conversation_id = create_conversation(
            user_id
        )

    if not conversation_belongs_to_user(
        conversation_id,
        user_id
    ):
        return jsonify(
            {
                "error":
                    "Conversation not found."
            }
        ), 404

    # --------------------------------------------------------
    # Validate message
    # --------------------------------------------------------

    if not prompt:
        return jsonify(
            {
                "error":
                    "Please enter a message."
            }
        ), 400

    if len(prompt) > MAX_MESSAGE_LENGTH:
        return jsonify(
            {
                "error":
                    (
                        "Message is too long. "
                        f"Maximum is "
                        f"{MAX_MESSAGE_LENGTH} "
                        "characters."
                    )
            }
        ), 400

    # --------------------------------------------------------
    # Set conversation title
    # --------------------------------------------------------

    existing_messages = get_messages(
        conversation_id
    )

    if not existing_messages:
        title = re.sub(
            r"\s+",
            " ",
            prompt
        ).strip()

        update_conversation_title(
            conversation_id,
            title
        )

    # --------------------------------------------------------
    # Save user's message
    # --------------------------------------------------------

    save_message(
        conversation_id,
        "user",
        prompt
    )

    # --------------------------------------------------------
    # Optional web search
    # --------------------------------------------------------

    web_results = []

    if web_enabled:
        web_results = web_search(
            prompt
        )

    # --------------------------------------------------------
    # Build AI conversation
    # --------------------------------------------------------

    ai_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    history = get_ai_messages(
        conversation_id
    )

    # --------------------------------------------------------
    # Add web information to AI context
    # --------------------------------------------------------

    if web_results:
        web_context = build_web_context(
            web_results
        )

        ai_messages.append(
            {
                "role": "system",
                "content": (
                    "The following information "
                    "was retrieved from a web "
                    "search. Use it when relevant. "
                    "Do not invent details that "
                    "are not supported by the "
                    "information.\n\n"
                    f"{web_context}"
                )
            }
        )

    ai_messages.extend(
        history
    )

    # --------------------------------------------------------
    # Ask OpenRouter
    # --------------------------------------------------------

    try:
        reply = ask_openrouter(
            ai_messages
        )

    except Exception as error:
        print(
            "OpenRouter error:",
            repr(error)
        )

        return jsonify(
            {
                "error": str(error)
            }
        ), 502

    # --------------------------------------------------------
    # Save AI response
    # --------------------------------------------------------

    save_message(
        conversation_id,
        "assistant",
        reply
    )

    # --------------------------------------------------------
    # Convert web results to frontend sources
    # --------------------------------------------------------

    sources = []

    for result in web_results:
        sources.append(
            {
                "title": result.get(
                    "title",
                    "Web source"
                ),
                "url": result.get(
                    "url",
                    ""
                )
            }
        )

    # --------------------------------------------------------
    # Return response to index.html
    # --------------------------------------------------------

    return jsonify(
        {
            "conversation_id":
                conversation_id,

            "reply":
                reply,

            "sources":
                sources
        }
    )
# ============================================================
# DEVELOPMENT ENTRY POINT
# ============================================================

if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
   