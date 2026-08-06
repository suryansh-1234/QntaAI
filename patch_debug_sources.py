from pathlib import Path

path = Path("app.py")
text = path.read_text()

old = '''    for result in web_results:
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
'''

new = '''    for result in web_results:
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
        repr(sources)
    )

    # --------------------------------------------------------
    # Return response to index.html
'''

if old not in text:
    raise SystemExit(
        "Target block not found. No changes made."
    )

path.write_text(
    text.replace(old, new, 1)
)

print("Patch applied successfully.")
