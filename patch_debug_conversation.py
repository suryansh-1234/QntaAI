from pathlib import Path

path = Path("app.py")
text = path.read_text()

old = '''    conversation_id = clean_text(
        data.get("conversation_id")
    )
'''

new = '''    conversation_id = clean_text(
        data.get("conversation_id")
    )

    print(
        "DEBUG conversation_id from frontend:",
        repr(conversation_id)
    )
'''

if old not in text:
    raise SystemExit(
        "❌ Could not find conversation_id block."
    )

text = text.replace(old, new, 1)

old2 = '''    if not conversation_id:
        conversation_id = create_conversation(
            user_id
        )
'''

new2 = '''    if not conversation_id:
        conversation_id = create_conversation(
            user_id
        )

        print(
            "DEBUG created conversation_id:",
            repr(conversation_id)
        )
    else:
        print(
            "DEBUG existing conversation_id:",
            repr(conversation_id)
        )
'''

if old2 not in text:
    raise SystemExit(
        "❌ Could not find conversation creation block."
    )

text = text.replace(old2, new2, 1)

old3 = '''    history = get_ai_messages(
        conversation_id
    )
'''

new3 = '''    history = get_ai_messages(
        conversation_id
    )

    print(
        "DEBUG history conversation_id:",
        repr(conversation_id)
    )

    print(
        "DEBUG history message count:",
        len(history)
    )
'''

if old3 not in text:
    raise SystemExit(
        "❌ Could not find history block."
    )

text = text.replace(old3, new3, 1)

old4 = '''    save_message(
        conversation_id,
        "assistant",
        reply
    )
'''

new4 = '''    save_message(
        conversation_id,
        "assistant",
        reply
    )

    print(
        "DEBUG saved conversation_id:",
        repr(conversation_id)
    )
'''

if old4 not in text:
    raise SystemExit(
        "❌ Could not find assistant save block."
    )

text = text.replace(old4, new4, 1)

path.write_text(text)

print("✅ Conversation debug patch applied.")
