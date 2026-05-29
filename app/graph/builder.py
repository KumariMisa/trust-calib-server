from typing import Dict, Any, Callable, AsyncGenerator
from app.graph.state import AgentState
from app.graph.nodes import (
    load_conversation_node,
    context_builder_node,
    llm_generation_node,
    persistence_node
)

class StateGraph:
    """
    A lightweight emulator of LangGraph's StateGraph.
    Provides identical developer interfaces (add_node, compile, astream).
    """
    def __init__(self, state_schema):
        self.state_schema = state_schema
        self.nodes = {}
        self.entry_point = None
        self.edges = []

    def add_node(self, name: str, action: Callable):
        self.nodes[name] = action
        return self

    def set_entry_point(self, name: str):
        self.entry_point = name
        return self

    def add_edge(self, start_key: str, end_key: str):
        self.edges.append((start_key, end_key))
        return self

    def compile(self):
        return CompiledGraph(self)

class CompiledGraph:
    def __init__(self, graph: StateGraph):
        self.graph = graph

    async def astream(self, input_data: Dict[str, Any], db) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the graph nodes in sequence, yielding events and tokens.
        Matches the streaming signature of LangGraph.
        """
        # Initialize state
        state = self.graph.state_schema(**input_data)
        
        # Step 1: Load History (LoadConversationNode)
        if "load_history" in self.graph.nodes:
            state = await self.graph.nodes["load_history"](state, db)
            yield {"event": "node_start", "node": "LoadConversationNode"}
            yield {"event": "node_end", "node": "LoadConversationNode"}

        # Step 2: Context Builder (ContextBuilderNode)
        if "context_builder" in self.graph.nodes:
            state = await self.graph.nodes["context_builder"](state)
            yield {"event": "node_start", "node": "ContextBuilderNode"}
            yield {"event": "node_end", "node": "ContextBuilderNode"}

        # Step 3: LLM Generation (LLMGenerationNode) - Streams output
        if "llm_generation" in self.graph.nodes:
            yield {"event": "node_start", "node": "LLMGenerationNode"}
            async for token in self.graph.nodes["llm_generation"](state):
                yield {"event": "token", "text": token}
            yield {"event": "node_end", "node": "LLMGenerationNode"}

        # Step 4: Save & Commit (PersistenceNode)
        if "persistence" in self.graph.nodes:
            state = await self.graph.nodes["persistence"](state, db)
            yield {"event": "node_start", "node": "PersistenceNode"}
            yield {"event": "node_end", "node": "PersistenceNode"}


# Define and build the compiled chat workflow graph
workflow = StateGraph(state_schema=AgentState)

# Add our custom nodes
workflow.add_node("load_history", load_conversation_node)
workflow.add_node("context_builder", context_builder_node)
workflow.add_node("llm_generation", llm_generation_node)
workflow.add_node("persistence", persistence_node)

# Set entry point
workflow.set_entry_point("load_history")

# Add edges to represent flow
workflow.add_edge("load_history", "context_builder")
workflow.add_edge("context_builder", "llm_generation")
workflow.add_edge("llm_generation", "persistence")

# Compile graph
chat_graph = workflow.compile()
