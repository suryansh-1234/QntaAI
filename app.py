import os
import json
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
- CEO & Founder : Suryansh
- Co-founder : Govind trivedi
- UI Designer: Arnav Sharma
- Debugger: Govind Trivedi
- Advertiser: Shourya Sharma

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

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            mime_type TEXT,
            size INTEGER NOT NULL,
            content TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_attachments_conversation
        ON attachments(conversation_id, id);

        CREATE INDEX IF NOT EXISTS idx_conversations_user
        ON conversations(user_id, updated_at DESC);

        CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON messages(conversation_id, id);
        """
    )

    # --------------------------------------------------------
    # DATABASE MIGRATIONS
    # --------------------------------------------------------

    columns = [
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(conversations)"
        ).fetchall()
    ]

    if "client_id" not in columns:
        connection.execute(
            "ALTER TABLE conversations ADD COLUMN client_id TEXT"
        )
        print(
            "✅ Database migration: added client_id",
            flush=True
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

    print(
        "DEBUG USER ID:",
        session["user_id"],
        flush=True
    )

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
    client_id,
    title="New chat"
):
    conversation_id = uuid.uuid4().hex
    timestamp = now_iso()

    connection = get_db()

    connection.execute(
        """
        INSERT INTO conversations
        (id, user_id, title, created_at, updated_at, client_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            user_id,
            title,
            timestamp,
            timestamp,
            client_id
        )
    )

    connection.commit()
    connection.close()

    return conversation_id


def conversation_belongs_to_user(
    conversation_id,
    user_id,
    client_id=None
):
    connection = get_db()

    if client_id:
        row = connection.execute(
            """
            SELECT id
            FROM conversations
            WHERE id = ?
              AND (
                  user_id = ?
                  OR client_id = ?
              )
            """,
            (
                conversation_id,
                user_id,
                client_id
            )
        ).fetchone()
    else:
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
# ATTACHMENTS
# ============================================================

def save_attachment(conversation_id, file):
    filename = clean_text(file.filename) or "unnamed"
    mime_type = file.mimetype or "application/octet-stream"
    raw_content = file.read()
    size = len(raw_content)

    text_content = None

    try:
        text_content = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        pass

    connection = get_db()

    connection.execute(
        """
        INSERT INTO attachments
        (conversation_id, filename, mime_type, size, content, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            filename,
            mime_type,
            size,
            text_content,
            now_iso()
        )
    )

    connection.commit()
    connection.close()

    return {
        "filename": filename,
        "mime_type": mime_type,
        "size": size,
        "content": text_content
    }


# ============================================================
# WEB SEARCH
# ============================================================

def should_search_web(prompt):
    """
    Decide whether the user's message actually requires
    current/external web information.
    """

    if not isinstance(prompt, str):
        return False

    text = prompt.strip().lower()

    if not text:
        return False

    search_phrases = (
        "today",
        "today's",
        "latest",
        "current",
        "currently",
        "recent",
        "recently",
        "news",
        "headlines",
        "breaking news",
        "this week",
        "this month",
        "right now",
        "at the moment",
        "what happened",
        "who is the current",
        "look up",
        "search the web",
        "search online",
        "fetch headlines",
    )

    return any(
        phrase in text
        for phrase in search_phrases
    )


def web_search(query):
    """
    Search DuckDuckGo and return relevant web results.

    For freshness-sensitive queries such as "today's news",
    "latest", or "current", add freshness hints to the search
    query so the search engine has a better chance of returning
    recent articles instead of old topic pages.
    """

    try:
        from bs4 import BeautifulSoup

        if not isinstance(query, str):
            return []

        query = query.strip()

        if not query:
            return []

        original_query = query
        lowered = query.lower()

        freshness_terms = (
            "today",
            "today's",
            "latest",
            "current",
            "currently",
            "recent",
            "recently",
            "breaking",
            "headlines",
            "this week",
        )

        freshness_requested = any(
            term in lowered
            for term in freshness_terms
        )

        search_query = query

        if freshness_requested:
            search_query = (
                query
                + " latest news"
                + " 2026"
            )

        print(
            "DEBUG actual search query:",
            repr(search_query),
            flush=True
        )

        response = requests.post(
            "https://html.duckduckgo.com/html/",
            data={
                "q": search_query
            },
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Linux; Android 15) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0 Mobile Safari/537.36"
                ),
                "Referer":
                    "https://html.duckduckgo.com/"
            },
            timeout=10
        )

        response.raise_for_status()

        print(
            "DEBUG DDG status:",
            response.status_code,
            flush=True
        )

        print(
            "DEBUG DDG bytes:",
            len(response.text),
            flush=True
        )

        debug_soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        print(
            "DEBUG DDG title:",
            (
                debug_soup.title.get_text(
                    " ",
                    strip=True
                )
                if debug_soup.title
                else "NO TITLE"
            ),
            flush=True
        )

        print(
            "DEBUG DDG result count:",
            len(debug_soup.select(".result")),
            flush=True
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        results = []

        for result in soup.select(".result"):

            link = result.select_one(
                ".result__a"
            )

            if not link:
                continue

            title = link.get_text(
                " ",
                strip=True
            )

            url = link.get(
                "href",
                ""
            )

            snippet_element = result.select_one(
                ".result__snippet"
            )

            snippet = (
                snippet_element.get_text(
                    " ",
                    strip=True
                )
                if snippet_element
                else ""
            )

            if not title or not url:
                continue

            results.append(
                {
                    "title": title,
                    "text": snippet,
                    "url": url
                }
            )

            if len(results) >= MAX_SEARCH_RESULTS:
                break

        print(
            "DEBUG web_search original query:",
            repr(original_query),
            flush=True
        )

        print(
            "DEBUG web_search results:",
            repr(results),
            flush=True
        )

        return results

    except requests.RequestException as error:
        print(
            "Web search request error:",
            repr(error),
            flush=True
        )
        return []

    except Exception as error:
        print(
            "Web search error:",
            repr(error),
            flush=True
        )
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
        user_id,
        client_id
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

    data = request.form.to_dict()

    try:
        data["messages"] = json.loads(
            data.get("messages", "[]")
        )
    except (TypeError, ValueError):
        data["messages"] = []

    # --------------------------------------------------------
    # Conversation ID
    # --------------------------------------------------------

    conversation_id = clean_text(
        data.get("conversation_id")
    )

    client_id = clean_text(
        data.get("client_id")
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
    # Search mode
    # --------------------------------------------------------

    search_mode = clean_text(
        data.get("mode") or "quick"
    ).lower()

    if search_mode not in (
        "quick",
        "search",
        "research"
    ):
        search_mode = "quick"

    # Quick keeps QntaAI's automatic search decision.
    #
    # Search and Research explicitly enable searching.
    web_enabled = search_mode in (
        "search",
        "research"
    )

    print(
        "DEBUG search mode:",
        repr(search_mode),
        "web_enabled:",
        repr(web_enabled),
        flush=True
    )


    # --------------------------------------------------------
    # Create conversation if needed
    # --------------------------------------------------------

    if not conversation_id:
        conversation_id = create_conversation(
            user_id,
            client_id
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

    uploaded_files = request.files.getlist("files")

    if not prompt and not uploaded_files:
        return jsonify(
            {
                "error":
                    "Please enter a message or attach a file."
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
    # Save uploaded attachments
    # --------------------------------------------------------

    uploaded_attachments = []

    for uploaded_file in request.files.getlist("files"):
        if not uploaded_file or not uploaded_file.filename:
            continue

        attachment = save_attachment(
            conversation_id,
            uploaded_file
        )

        uploaded_attachments.append(
            attachment
        )

    # --------------------------------------------------------
    # Optional web search
    # --------------------------------------------------------
    web_results = []

    if search_mode == "quick":

        # Existing automatic search behaviour.
        search_requested = should_search_web(
            prompt
        )

    elif search_mode == "search":

        # Explicit web search.
        search_requested = True

    else:

        # Research v1.
        # The deeper research engine comes later.
        search_requested = True

    print(
        "DEBUG search decision:",
        repr(prompt),
        "mode:",
        repr(search_mode),
        "=>",
        repr(search_requested),
        flush=True
    )

    if search_requested:
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

    if uploaded_attachments:
        attachment_context = []
        for attachment in uploaded_attachments:
            line = (
                f"Attached file: {attachment["filename"]} "
                f"({attachment["mime_type"]}, {attachment["size"]} bytes)"
            )
            if attachment.get("content"):
                line += "\\nFile content:\\n" + attachment["content"][:20000]
            attachment_context.append(line)

        ai_messages.append({
            "role": "system",
            "content": (
                "The user attached the following files. "
                "Use their metadata and text content when relevant.\\n\\n"
                + "\\n\\n".join(attachment_context)
            )
        })

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

    print(
        "DEBUG frontend sources:",
        repr(sources),
        flush=True
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
    