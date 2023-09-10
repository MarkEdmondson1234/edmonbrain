import logging
import traceback
import time

from qna.llm import pick_llm
from qna.llm import pick_retriever
from qna.llm import pick_prompt
from qna.llm import pick_agent

from httpcore import ReadTimeout
from httpx import ReadTimeout
from openai.error import InvalidRequestError

#https://python.langchain.com/en/latest/modules/chains/index_examples/chat_vector_db.html
from langchain.chains import ConversationalRetrievalChain

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)
def qna(question: str, 
        vector_name: str, 
        chat_history=[], 
        max_retries=1, 
        initial_delay=5, 
        stream_llm=None,
        message_author=None):

    logging.debug("Calling qna")

    llm, embeddings, llm_chat = pick_llm(vector_name)
    retriever = pick_retriever(vector_name, embeddings=embeddings)

    # override llm to one that supports streaming
    if stream_llm:
        llm_chat=stream_llm

    is_agent = pick_agent(vector_name)
    if is_agent:
        from qna.agent import activate_agent
        from qna.llm import pick_chat_buddy
        from qna.self_query import get_self_query_retriever
        from qna.llm import pick_vectorstore
        calendar = get_self_query_retriever(llm, vectorstore=pick_vectorstore(vector_name, embeddings=embeddings))
        result = activate_agent(question, llm_chat, chat_history, 
                                retriever=retriever, calendar_retriever=calendar)
        if result is not None:
            logging.info(f"agent result: {result}")
            chat_buddy, buddy_description = pick_chat_buddy(vector_name)
            if chat_buddy == message_author:
                result['answer'] = f"{chat_buddy} {result['answer']}"
            else:
                logging.info(f"No chat buddy found for {message_author} from {vector_name}")

            return result
        
        return {'answer':"Agent couldn't help", 'source_documents': []}

    prompt = pick_prompt(vector_name, chat_history)

    qa = ConversationalRetrievalChain.from_llm(llm_chat,
                                               retriever=retriever, 
                                               chain_type="stuff",
                                               return_source_documents=True,
                                               verbose=True,
                                               output_key='answer',
                                               combine_docs_chain_kwargs={'prompt': prompt},
                                               condense_question_llm=llm)
    
    for retry in range(max_retries):
        try:
            return qa({"question": question, "chat_history": chat_history})
        except ReadTimeout as err:
            delay = initial_delay * (retry + 1)
            logging.warning(f"Read timeout while asking: {question} - trying again after {delay} seconds. Error: {str(err)}")
            time.sleep(delay)
            try:
                result = qa({"question": question, "chat_history": chat_history})
                result["answer"] = result["answer"] + " (Sorry for delay, brain was a bit slow - should be quicker next time)"
                return result
            except ReadTimeout:
                if retry == max_retries - 1:
                    raise
        except Exception as err:
            delay = initial_delay * (retry + 1)
            logging.error(f"General error: {traceback.format_exc()}")
            time.sleep(delay)
            try:
                result = qa({"question": question, "chat_history": chat_history})
                result["answer"] = result["answer"] + " (Sorry for delay, had to warm up the brain - should be quicker next time)"
                return result
            except Exception:
                if retry == max_retries - 1:
                    raise

    raise Exception(f"Max retries exceeded for question: {question}")
