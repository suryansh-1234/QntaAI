from pathlib import Path

path = Path("app.py")
text = path.read_text()

old = '''    if web_enabled:
        web_results = web_search(
            prompt
        )

    # --------------------------------------------------------
    # Build AI conversation
'''

new = '''    if web_enabled:
        web_results = web_search(
            prompt
        )

        print(
            "DEBUG web_results:",
            repr(web_results)
        )

    # --------------------------------------------------------
    # Build AI conversation
'''

if old not in text:
    raise SystemExit(
        "Target block not found. No changes made."
    )

path.write_text(
    text.replace(old, new, 1)
)

print("Patch applied successfully.")
