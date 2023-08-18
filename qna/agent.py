from langchain.agents import Tool
from langchain.agents import AgentType

from langchain.agents import initialize_agent
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from qna.llm import pick_vectorstore

from langchain.tools.python.tool import PythonREPLTool
from langchain.tools import VectorStoreQAWithSourcesTool

def activate_agent(question, chat_history, vector_name):

    search = VectorStoreQAWithSourcesTool(vectorstore = pick_vectorstore(vector_name))
    python = PythonREPLTool
    tools = [
        search,
        python
    ]

    #memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    llm = ChatOpenAI(temperature=0)
    agent_chain = initialize_agent(tools, llm, agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION, verbose=True)

    result = agent_chain(input=question, chat_history=chat_history)

    return result