from pathlib import Path

path = Path("templates/index.html")
text = path.read_text()

original = text


def replace_once(old, new, description):
    global text

    count = text.count(old)

    if count != 1:
        raise RuntimeError(
            f"{description}: expected 1 match, found {count}"
        )

    text = text.replace(old, new, 1)
    print(f"✅ {description}")


# ============================================================
# 1. Initial currentChat
# ============================================================

replace_once(
'''let currentChat = {
    id: createId(),
    title: "New chat",
    messages: []
};''',
'''let currentChat = {
    id: createId(),
    title: "New chat",
    messages: [],
    conversation_id: null
};''',
"Added conversation_id to initial currentChat"
)


# ============================================================
# 2. New chat
# ============================================================

replace_once(
'''    currentChat = {
        id: createId(),
        title: "New chat",
        messages: []
    };''',
'''    currentChat = {
        id: createId(),
        title: "New chat",
        messages: [],
        conversation_id: null
    };''',
"Added conversation_id reset to startNewChat()"
)


# ============================================================
# 3. Current chat reset after deletion
# ============================================================

replace_once(
'''        currentChat = {
            id: createId(),
            title: "New chat",
            messages: []
        };''',
'''        currentChat = {
            id: createId(),
            title: "New chat",
            messages: [],
            conversation_id: null
        };''',
"Added conversation_id reset after chat deletion"
)


# ============================================================
# 4. Send conversation_id to Flask
# ============================================================

replace_once(
'''                    body: JSON.stringify({
                        messages:
                            currentChat.messages,

                        web_search:
                            webSearchEl.checked,

                        model:
                            modelSelect.value
                    })''',
'''                    body: JSON.stringify({
                        conversation_id:
                            currentChat.conversation_id,

                        messages:
                            currentChat.messages,

                        web_search:
                            webSearchEl.checked,

                        model:
                            modelSelect.value
                    })''',
"Added conversation_id to /api/chat request"
)


# ============================================================
# 5. Store conversation_id returned by Flask
# ============================================================

replace_once(
'''        try {

            data =
                await response.json();

        } catch (jsonError) {''',
'''        try {

            data =
                await response.json();

            if (
                data &&
                data.conversation_id
            ) {
                currentChat.conversation_id =
                    data.conversation_id;
            }

        } catch (jsonError) {''',
"Added conversation_id response handling"
)


# ============================================================
# Write only after ALL checks succeeded
# ============================================================

if text == original:
    raise RuntimeError(
        "No changes were made."
    )

path.write_text(text)

print()
print("🎉 Conversation context patch applied successfully.")
print("🧠 QntaAI can now preserve backend conversation IDs.")
print()
