from langchain.agents import Tool
from langchain.agents import AgentType

from langchain.agents import initialize_agent
from langchain.memory import ConversationBufferMemory

from langchain.tools.python.tool import PythonREPLTool

from httpx import ReadTimeout

import logging
import traceback

def activate_agent(question, llm_chat, chat_history):

    logging.info(f"Activating agent {question}")

    if chat_history:
        last_human_message, last_ai_message = chat_history[-1]
        question = f"Last human message: {last_human_message}\nLast AI message: {last_ai_message}\nQuestion: {question}"

    tools = [
        Tool(
            name="python-repl",
            description="useful for when you need to calculate something using programing. Always end your programes with print() so we can see the answer.",
            func=PythonREPLTool().run
        )
    ]

    max_retries=1
    initial_delay = 5
    import time
    for retry in range(max_retries):
        try:
            agent_chain = initialize_agent(tools, llm=llm_chat, agent=AgentType.OPENAI_FUNCTIONS, verbose=True)
            result = agent_chain.run(input=question)
        except ReadTimeout as err:
            delay = initial_delay * (retry + 1)
            logging.warning(f"Read timeout while asking: {question} - trying again after {delay} seconds. Error: {str(err)}")
            time.sleep(delay)
            try:
                agent_chain = initialize_agent(tools, llm=llm_chat, agent=AgentType.OPENAI_FUNCTIONS, verbose=True)
                result = agent_chain.run(input=question)
            except ReadTimeout:
                if retry == max_retries - 1:
                    raise
        except Exception as err:
            delay = initial_delay * (retry + 1)
            logging.error(f"General error: {traceback.format_exc()}")
            time.sleep(delay)
            try:
                agent_chain = initialize_agent(tools, llm=llm_chat, agent=AgentType.OPENAI_FUNCTIONS, verbose=True)
                result = agent_chain.run(input=question)

            except Exception:
                if retry == max_retries - 1:
                    raise

    logging.info(f"Agent answer: {result}")

    return {"answer": result}