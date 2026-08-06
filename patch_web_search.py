from pathlib import Path
import re

path = Path("app.py")
text = path.read_text(encoding="utf-8")

new_function = r'''def web_search(query):
    try:
        from bs4 import BeautifulSoup

        response = requests.post(
            "https://html.duckduckgo.com/html/",
            data={
                "q": query
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

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        results = []

        for result in soup.select(
            ".result"
        ):
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
'''

pattern = re.compile(
    r"def web_search\(query\):.*?(?=\ndef build_web_context\(results\):)",
    re.DOTALL
)

match = pattern.search(text)

if not match:
    raise SystemExit(
        "ERROR: Could not find the existing web_search() function."
    )

text = (
    text[:match.start()]
    + new_function
    + "\n"
    + text[match.end():]
)

path.write_text(
    text,
    encoding="utf-8"
)

print(
    "SUCCESS: web_search() replaced."
)
