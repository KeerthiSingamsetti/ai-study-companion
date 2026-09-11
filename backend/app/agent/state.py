"""State contracts shared by StudyMate's LangGraph nodes."""

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """Request-scoped state for the StudyMate chat graph.

    ``add_messages`` provides LangGraph's standard message merge behaviour.
    It does not persist messages; persistence is introduced only when a
    checkpointer is explicitly configured.

    ``intent`` is written by the intent_router node and consumed by every
    downstream chat node to select the correct system prompt.  It holds one
    of the ``Intent`` enum values as a plain string so LangGraph can
    serialise it without importing the enum at checkpoint time.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    intent: str  # one of Intent enum values: general_chat | document_qa | quiz | flashcard | study_plan | progress | no_document
