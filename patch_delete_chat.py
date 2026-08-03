from pathlib import Path

path = Path("templates/index.html")
text = path.read_text(encoding="utf-8")

# =========================================================
# 1. Replace renderHistory()
# =========================================================

start_marker = "function renderHistory() {"
end_marker = "\n\n\n/* =========================================================\n   LOAD CHAT"

start = text.find(start_marker)
end = text.find(end_marker, start)

if start == -1 or end == -1:
    raise SystemExit(
        "ERROR: Could not locate renderHistory(). No changes made."
    )

new_render_history = r'''function renderHistory() {
    historyEl.innerHTML = "";

    if (chats.length === 0) {
        const empty = document.createElement("div");

        empty.style.padding = "12px 8px";
        empty.style.color = "var(--muted)";
        empty.style.fontSize = "12px";
        empty.textContent = "No conversations yet.";

        historyEl.appendChild(empty);
        return;
    }

    for (const chat of chats) {
        const item = document.createElement("div");

        item.className = "history-item";

        if (chat.id === currentChat.id) {
            item.classList.add("active");
        }

        const button = document.createElement("button");

        button.type = "button";
        button.className = "history-chat-button";

        button.innerHTML = `
            <span>💬</span>
            <span class="history-chat-title">
                ${escapeHtml(chat.title || "New chat")}
            </span>
        `;

        button.addEventListener("click", () => {
            loadChat(chat.id);
        });

        const deleteButton = document.createElement("button");

        deleteButton.type = "button";
        deleteButton.className = "history-delete-button";
        deleteButton.title = "Delete chat";
        deleteButton.setAttribute(
            "aria-label",
            `Delete ${chat.title || "chat"}`
        );
        deleteButton.textContent = "🗑️";

        deleteButton.addEventListener("click", event => {
            event.stopPropagation();
            deleteChat(chat.id);
        });

        item.appendChild(button);
        item.appendChild(deleteButton);

        historyEl.appendChild(item);
    }
}'''

text = text[:start] + new_render_history + text[end:]


# =========================================================
# 2. Add deleteChat()
# =========================================================

delete_marker = "function clearAllChats() {"

if delete_marker not in text:
    raise SystemExit(
        "ERROR: Could not locate clearAllChats(). No changes made."
    )

if "async function deleteChat(chatId)" not in text:
    delete_function = r'''async function deleteChat(chatId) {
    const chat = chats.find(
        item => item.id === chatId
    );

    if (!chat) {
        return;
    }

    const confirmed = window.confirm(
        `Delete "${chat.title || "New chat"}"?`
    );

    if (!confirmed) {
        return;
    }

    chats = chats.filter(
        item => item.id !== chatId
    );

    saveChats();

    if (currentChat.id === chatId) {
        currentChat = {
            id: createId(),
            title: "New chat",
            messages: []
        };

        chatTitle.textContent = "New chat";

        messagesEl.innerHTML = `
            <div
                class="welcome"
                id="welcome"
            >
                <div class="welcome-orb">
                    Q
                </div>

                <h1>
                    What are you curious about?
                </h1>

                <p>
                    I'm QntaAI — your AI tutor.
                    Ask me anything and let's
                    explore it together.
                </p>
            </div>
        `;
    }

    renderHistory();
}


'''

    text = text.replace(
        delete_marker,
        delete_function + delete_marker,
        1
    )


# =========================================================
# 3. Add CSS
# =========================================================

style_end = "</style>"

if style_end not in text:
    raise SystemExit(
        "ERROR: Could not locate </style>. No changes made."
    )

css = r'''
    /* =====================================================
       INDIVIDUAL CHAT DELETE BUTTON
       ===================================================== */

    .history-item {
        display: flex;
        align-items: center;
        gap: 4px;
        width: 100%;
    }

    .history-chat-button {
        flex: 1;
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 8px;
        border: 0;
        background: transparent;
        color: inherit;
        text-align: left;
        cursor: pointer;
        padding: 9px 8px;
        border-radius: 8px;
        font: inherit;
    }

    .history-chat-title {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .history-delete-button {
        flex: 0 0 auto;
        border: 0;
        background: transparent;
        color: var(--muted);
        cursor: pointer;
        padding: 7px;
        border-radius: 7px;
        opacity: 0;
        transition:
            opacity 0.15s ease,
            background 0.15s ease,
            color 0.15s ease;
    }

    .history-item:hover .history-delete-button,
    .history-delete-button:focus-visible {
        opacity: 1;
    }

    .history-delete-button:hover {
        background: rgba(255, 70, 70, 0.12);
        color: #ff6b6b;
    }

'''

if "INDIVIDUAL CHAT DELETE BUTTON" not in text:
    text = text.replace(
        style_end,
        css + style_end,
        1
    )


# =========================================================
# 4. Save
# =========================================================

path.write_text(text, encoding="utf-8")

print("SUCCESS: Individual chat deletion was added.")
print("Backup remains at:")
print("templates/index.html.backup")

