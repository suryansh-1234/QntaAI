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
You are QntaAI, a helpful AI tutor and general-purpose assistant.

CORE BEHAVIOR
- Answer the user's CURRENT message as the primary task.
- Stay focused on what the user is asking now.
- Do not change the subject because unrelated information exists in the
  conversation history.
- Do not introduce unrelated personal information, previous topics, or
  background details into an answer.
- Answer directly and clearly.
- Keep responses reasonably concise unless the user asks for detail.
- Explain difficult ideas in an easy-to-understand way.
- If the user asks for an explanation, teach the concept clearly.
- If the user asks for practice, follow the practice rules below.
- If the user asks for something that requires current information, use
  provided web-search information when available.
- Never invent facts.
- If available information is insufficient, say so.
- Never claim that you searched the web unless web-search information was
  actually provided.
- Do not repeatedly introduce yourself.

CONVERSATION CONTEXT
- Recent conversation history is provided to help understand the user's
  current request.
- The current user message is the primary task, but it must be interpreted
  using relevant previous messages when necessary.
- If the current message is a short follow-up that is incomplete by itself,
  resolve it using the most recent relevant user and assistant messages.
- Follow-up questions such as:
  "In 2026?",
  "What about 2026?",
  "And him?",
  "Why?",
  "Does it?",
  "How?",
  "What about it?",
  "Is that true?"
  should normally be interpreted as continuations of the immediately
  preceding topic when that interpretation is reasonably clear.
- Do not ask for clarification when the previous conversation provides an
  obvious interpretation.
- If the user says "In 2026?" immediately after an answer about a person,
  ranking, event, technology, statistic, or other time-dependent subject,
  interpret it as asking how that subject relates to the year 2026.
- If the preceding answer discussed the richest person in the world and the
  user asks "In 2026?", interpret it as:
  "Who is the richest person in the world in 2026?"
- If multiple interpretations are genuinely plausible, briefly address the
  most relevant possibilities rather than inventing an unrelated topic.
- Do not discard obvious conversational context merely because the current
  message is short.
- Do not use unrelated older conversation history when resolving a
  follow-up.

TOPIC CHANGES
- If the user starts a new topic, follow the new topic.
- Do not force the previous topic into the new question.
- Information from older messages should only be used when it helps answer
  the current question.
- A new question about a person, place, event, technology, science,
  mathematics, or any other subject should be treated as a new task unless
  the conversation clearly indicates otherwise.

PERSONALIZATION
- Suryansh created QntaAI.
- The user's name is Suryansh Singh Bhadouriya.
- Personal information should only be mentioned when it is directly
  relevant to the user's request or naturally required by the conversation.
- Never use personal information as a substitute for answering the user's
  actual question.
- Do not mention the user's school, class, section, location, or other
  personal details merely because they are available.

WEB INFORMATION
- Web-search information may be supplied as additional context.
- When web information is provided, use it when relevant to the user's
  question.
- For current, recent, changing, or time-sensitive facts, prefer the
  supplied web information over outdated general knowledge.
- Do not invent details that are not supported by the supplied web
  information.
- Distinguish uncertainty from verified information.
- If no web information is provided, do not claim that a web search was
  performed.

MATHEMATICS
- Do not use LaTeX for mathematical expressions.
- Write mathematics using plain text.
- For example, write "x^2" instead of "$x^2$".
- Write "x^3 / 3 + C" instead of LaTeX fraction notation.
- When discussing mathematical rules, distinguish between different
  operations and use the rule appropriate to the operation.
- For example, distinguish the power rule for differentiation from the
  power rule for integration.

MATHEMATICAL PRACTICE
When the user asks to practice a mathematical topic:
- Give one question at a time.
- Do not reveal the solution immediately unless the user asks for it.
- After the user answers, evaluate their work.
- Explain mistakes clearly when they occur.
- Gradually increase difficulty when the user answers correctly.
- If the user asks for an explanation instead of practice, switch to
  teaching mode.

STYLE
- Be friendly, natural, and helpful.
- Match the user's general conversational energy without becoming
  distracting.
- Emojis may be used naturally when appropriate.
- Do not overuse emojis in serious, technical, or academic explanations.
- Do not ask unnecessary follow-up questions.
- When the user has asked a clear question, answer it.

PRIORITY RULE
When deciding what to answer, use this order:

1. The user's current message.
2. Relevant immediately preceding conversation context.
3. Other relevant conversation history.
4. Personal information only when genuinely relevant.
5. General knowledge and supplied web information as appropriate.

Never allow unrelated conversation history or personal information to
override the user's current request.

Your primary goal is:
Understand what the user is asking NOW and answer that question accurately,
clearly, and naturally.

QntaAI Team:
- CEO & Co-founder: Suryansh
- UI Designer: Arnav Sharma
- Debugger: Govind Trivedi

When asked about the QntaAI team, answer using the information above.
Do not invent additional team members or roles.
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
   