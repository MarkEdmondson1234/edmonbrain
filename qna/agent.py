from langchain.agents import Tool
from langchain.agents import AgentType

from langchain.agents import initialize_agent

from langchain.tools.python.tool import PythonREPLTool
from langchain import LLMMathChain
from langchain.chains import RetrievalQA

from httpx import ReadTimeout

import logging
import traceback

def activate_agent(question, llm_chat, chat_history, retriever, calendar_retriever=None):

    logging.info(f"Activating agent {question}")

    if chat_history:
        last_human_message, last_ai_message = chat_history[-1]
        question = f"Last human message: {last_human_message}\nLast AI message: {last_ai_message}\nQuestion: {question}"
    
    # create calculator tool
    calculator = LLMMathChain.from_llm(llm=llm_chat, verbose=True)

    from langchain.prompts import PromptTemplate
    # memory tool
    template_memory = """You are a memory assistant bot.
Below are memories that have been recalled to try and answer the question below.
If the memories do not help you to answer, apologise and say you don't remember anything relevant to help.
If the memories do help with your answer, use them to answer and also summarise what memories you are using to help answer the question.
## Memories
{context}
## Question
{question}
## Your Answer
"""
    memory = RetrievalQA.from_chain_type(
        llm=llm_chat,
        chain_type="stuff",
        chain_type_kwargs={
            "prompt": PromptTemplate(
                template=template_memory,
                input_variables=["context", "question"],
            ),
        },
        retriever=retriever,
    )

    template_calendar="""You are a calendar assistant bot.  
Below are events that have been returned for the dates or time period requested in the question.
Reply echoing the memories and trust they did occur on dates as specified in the question.
## Memories within dates as specified in the question
{context}
## Question
{question}
## Your Answer
"""
    calendar = RetrievalQA.from_chain_type(
        llm=llm_chat,
        chain_type="stuff",
        chain_type_kwargs={
            "prompt": PromptTemplate(
                template=template_calendar,
                input_variables=["context", "question"],
            ),
        },
        retriever=calendar_retriever
    )

    tools = [
        Tool(
            name="python-repl",
            description="useful for when you need to calculate something using programing. Always end your programes with print() so we can see the answer.",
            func=PythonREPLTool().run
        ),
        Tool(
            name = "calculator",
            func=calculator.run,
            description = f"""
            Useful when you need to do mathematical operations or arithmetic.
            """
        ),
        Tool(name = "calendar-helper",
             func=calendar.run,
             description = """
             Useful when you have specific dates to look up within your memory
             """),
        Tool(
            name = "long-term-memory",
            func=memory.run,
            description="""
            Use when you don't have specific dates to look up in your memory, but are searching for general subjects that happened in the past.
            """
        )
    ]

    agent_kwargs = {'prefix': f'You are an assistant to another AI. You have access to the following tools:'}

    max_retries=1
    initial_delay = 5
    import time
    for retry in range(max_retries):
        try:
            agent_chain = initialize_agent(tools, 
                                           llm=llm_chat, 
                                           agent=AgentType.OPENAI_FUNCTIONS, 
                                           agent_kwargs=agent_kwargs, 
                                           verbose=True)
            result = agent_chain.run(input=question)
        except ReadTimeout as err:
            delay = initial_delay * (retry + 1)
            logging.warning(f"Read timeout while asking: {question} - trying again after {delay} seconds. Error: {str(err)}")
            time.sleep(delay)
            try:
                agent_chain = initialize_agent(tools, 
                                               llm=llm_chat, 
                                               agent=AgentType.OPENAI_FUNCTIONS,
                                               agent_kwargs=agent_kwargs, 
                                               verbose=True)
                result = agent_chain.run(input=question)
            except ReadTimeout:
                if retry == max_retries - 1:
                    raise
        except Exception as err:
            delay = initial_delay * (retry + 1)
            logging.error(f"General error: {traceback.format_exc()}")
            time.sleep(delay)
            try:
                agent_chain = initialize_agent(tools, 
                                               llm=llm_chat, 
                                               agent=AgentType.OPENAI_FUNCTIONS, 
                                               agent_kwargs=agent_kwargs,
                                               verbose=True)
                result = agent_chain.run(input=question)

            except Exception:
                if retry == max_retries - 1:
                    raise

    logging.info(f"Agent answer: {result}")

    return {"answer": result}