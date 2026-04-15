import operator
from typing import Annotated, TypedDict
from langgraph.graph import END, START, StateGraph


class AllState(TypedDict):
    messages: Annotated[list[str], operator.add]


def hello_node(state: AllState) -> dict[str, list[str]]:
    """最小節點：往 messages 追加一筆（Annotated + operator.add 會合併列表）。"""
    return {"messages": ["hello from graph"]}


graph = StateGraph(AllState)
graph.add_node("hello", hello_node)
graph.add_edge(START, "hello")
graph.add_edge("hello", END)

app = graph.compile()

if __name__ == "__main__":
    result = app.invoke({"messages": []})
    print(result)
