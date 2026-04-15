"""
階段 B～C：LangGraph 任務代理（B1～B4、C1～C2）。

- 圖與節點實作：`src/langgraph_learning/graphs/agent_graph.py`
- 工具：`src/langgraph_learning/tools/market.py`
"""

import path_setup

path_setup.add_src_to_path()

from langgraph_learning.graphs.agent_graph import main

if __name__ == "__main__":
    main()
