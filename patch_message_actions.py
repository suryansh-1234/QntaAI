from pathlib import Path
import shutil

FILE = Path("templates/index.html")
BACKUP = Path("templates/index.html.before_message_actions")

if not FILE.exists():
    raise SystemExit("ERROR: templates/index.html not found.")

text = FILE.read_text(encoding="utf-8")

# ---------------------------------------------------------
# 1. Backup
# ---------------------------------------------------------

if not BACKUP.exists():
    shutil.copy2(FILE, BACKUP)
    print("Backup created:", BACKUP)

# ---------------------------------------------------------
# 2. Add CSS
# ---------------------------------------------------------

css_marker = """        .composer-main {
"""

css = r"""        /* =========================
           MESSAGE ACTIONS
        ========================= */

        .message-actions {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-top: 9px;
        }

        .message-action {
            border: 1px solid var(--border);
            background: transparent;
            color: var(--muted);
            border-radius: 8px;
            padding: 5px 9px;
            font-size: 12px;
            cursor: pointer;
            transition:
                background .15s,
                color .15s,
                transform .15s;
        }

        .message-action:hover {
            background: var(--surface);
            color: var(--text);
            transform: translateY(-1px);
        }

        .message-action.active {
            color: var(--text);
            background: var(--surface);
        }

"""

if ".message-actions {" not in text:
    if css_marker not in text:
        raise SystemExit("ERROR: CSS insertion marker not found.")

    text = text.replace(
        css_marker,
        css + css_marker,
        1
    )

    print("SUCCESS: message action CSS added.")
else:
    print("INFO: message action CSS already exists.")

# ---------------------------------------------------------
# 3. Add JavaScript helper
# ---------------------------------------------------------

js_marker = """/* =========================
   WEB SOURCES
========================= */
"""

js = r"""/* =========================
   MESSAGE ACTIONS
========================= */

function addMessageActions(
    parent,
    text
) {

    const actions =
        document.createElement("div");

    actions.className =
        "message-actions";


    /* COPY */

    const copyButton =
        document.createElement("button");

    copyButton.type =
        "button";

    copyButton.className =
        "message-action";

    copyButton.textContent =
        "📋 Copy";

    copyButton.title =
        "Copy response";


    copyButton.addEventListener(
        "click",
        async function () {

            try {

                if (
                    navigator.clipboard &&
                    window.isSecureContext
                ) {

                    await navigator.clipboard.writeText(
                        text
                    );

                } else {

                    const area =
                        document.createElement("textarea");

                    area.value =
                        text;

                    area.style.position =
                        "fixed";

                    area.style.opacity =
                        "0";

                    document.body.appendChild(
                        area
                    );

                    area.focus();
                    area.select();

                    document.execCommand(
                        "copy"
                    );

                    area.remove();
                }

                copyButton.textContent =
                    "✅ Copied";

                setTimeout(
                    function () {
                        copyButton.textContent =
                            "📋 Copy";
                    },
                    1400
                );

            } catch (error) {

                console.error(
                    "Copy failed:",
                    error
                );

                copyButton.textContent =
                    "⚠️ Failed";

                setTimeout(
                    function () {
                        copyButton.textContent =
                            "📋 Copy";
                    },
                    1400
                );
            }
        }
    );


    /* HELPFUL */

    const upButton =
        document.createElement("button");

    upButton.type =
        "button";

    upButton.className =
        "message-action";

    upButton.textContent =
        "👍";

    upButton.title =
        "Helpful";


    /* NOT HELPFUL */

    const downButton =
        document.createElement("button");

    downButton.type =
        "button";

    downButton.className =
        "message-action";

    downButton.textContent =
        "👎";

    downButton.title =
        "Not helpful";


    upButton.addEventListener(
        "click",
        function () {

            upButton.classList.add(
                "active"
            );

            downButton.classList.remove(
                "active"
            );
        }
    );


    downButton.addEventListener(
        "click",
        function () {

            downButton.classList.add(
                "active"
            );

            upButton.classList.remove(
                "active"
            );
        }
    );


    actions.appendChild(
        copyButton
    );

    actions.appendChild(
        upButton
    );

    actions.appendChild(
        downButton
    );

    parent.appendChild(
        actions
    );
}


"""

if "function addMessageActions(" not in text:
    if js_marker not in text:
        raise SystemExit("ERROR: JavaScript insertion marker not found.")

    text = text.replace(
        js_marker,
        js + js_marker,
        1
    )

    print("SUCCESS: message action JavaScript added.")
else:
    print("INFO: message action JavaScript already exists.")

# ---------------------------------------------------------
# 4. Add actions to AI messages only
# ---------------------------------------------------------

source_marker = """    if (
        Array.isArray(options.sources) &&
        options.sources.length > 0
    ) {

        addSources(
            body,
            options.sources
        );
    }


"""

replacement = """    if (
        Array.isArray(options.sources) &&
        options.sources.length > 0
    ) {

        addSources(
            body,
            options.sources
        );
    }


    /* =========================
       AI MESSAGE ACTIONS
    ========================= */

    if (role === "ai") {

        addMessageActions(
            body,
            text
        );
    }


"""

if "AI MESSAGE ACTIONS" not in text:
    if source_marker not in text:
        raise SystemExit(
            "ERROR: addMessage() insertion marker not found."
        )

    text = text.replace(
        source_marker,
        replacement,
        1
    )

    print("SUCCESS: actions connected to AI messages.")
else:
    print("INFO: AI message actions already connected.")

# ---------------------------------------------------------
# 5. Write
# ---------------------------------------------------------

FILE.write_text(
    text,
    encoding="utf-8"
)

print()
print("======================================")
print("SUCCESS: QntaAI message actions added.")
print("======================================")
print()
print("Added:")
print("  📋 Copy")
print("  👍 Helpful")
print("  👎 Not helpful")
print()
print("Backup:")
print(" ", BACKUP)
