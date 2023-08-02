import logging
import traceback
import time

from qna.llm import pick_llm
from qna.llm import pick_vectorstore
from qna.llm import pick_prompt

from httpcore import ReadTimeout
from openai.error import InvalidRequestError

#https://python.langchain.com/en/latest/modules/chains/index_examples/chat_vector_db.html
from langchain.chains import ConversationalRetrievalChain

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)
def qna(question: str, vector_name: str, chat_history=[], max_retries=1, initial_delay=5):

    logging.debug("Calling qna")

    llm, embeddings, llm_chat = pick_llm(vector_name)

    vectorstore = pick_vectorstore(vector_name, embeddings=embeddings)

    retriever = vectorstore.as_retriever(search_kwargs=dict(k=3))

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
