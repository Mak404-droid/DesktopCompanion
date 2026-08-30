import os
from dotenv import load_dotenv
from tavily import TavilyClient


load_dotenv()

API_KEY = os.getenv("TAVILY_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "TAVILY_API_KEY was not found in .env"
    )

client = TavilyClient(
    api_key=API_KEY
)


def search_web(query, max_results=5):

    try:

        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True
        )

        return response

    except Exception as e:

        print(
            "Web search error:",
            e
        )

        return None


def format_results(response):

    if not response:
        return "No web results found."

    output = []

    answer = response.get(
        "answer"
    )

    if answer:

        output.append(
            "SEARCH SUMMARY:\n"
            + answer
        )

    results = response.get(
        "results",
        []
    )

    for i, result in enumerate(
        results,
        start=1
    ):

        title = result.get(
            "title",
            "Unknown"
        )

        url = result.get(
            "url",
            ""
        )

        content = result.get(
            "content",
            ""
        )

        output.append(
            f"{i}. {title}\n"
            f"{url}\n"
            f"{content}"
        )

    return "\n\n".join(
        output
    )


if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "Desktop Companion Web Search"
    )

    print(
        "================================"
    )

    query = input(
        "Search: "
    ).strip()

    if query:

        response = search_web(
            query
        )

        print(
            "\n"
            + format_results(
                response
            )
        )

    else:

        print(
            "No search query entered."
        )