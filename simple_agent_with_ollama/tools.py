import os

def search_the_internet(search: str):
    """Search the Internet"""
    from tavily import TavilyClient

    tavily_client = TavilyClient(api_key="tavily_api_key")
    response = tavily_client.search(search)
    all_results = ""
    for result in response["results"]:
        all_results += "\n" + result["content"]


    return all_results

# print(search_the_internet("what is google ADK??"))



def create_directory(path: str) -> str:
    """
    Create a directory (and parents if needed).
    Returns the path.
    """
    os.makedirs(path, exist_ok=True)
    return path


def write_file(path: str, content: str) -> str:
    """
    Write string content to a file (overwrites if exists).
    """

    with open(path, "w") as f:
        f.write(content)
    return path


def read_file(path: str) -> str:
    """
    Read string content from a file.
    """
    with open(path, "r") as f:
        return f.read()


def update_file(path: str, content: str) -> str:
    """
    Append string content to a file.
    Creates the file if it does not exist.
    """


    with open(path, "a") as f:
        f.write(content)
    return path
