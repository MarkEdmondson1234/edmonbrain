import logging
import traceback

from qna.llm import pick_llm
from qna.llm import pick_vectorstore
from qna.llm import pick_prompt

from openai.error import InvalidRequestError

#https://python.langchain.com/en/latest/modules/chains/index_examples/chat_vector_db.html
from langchain.chains import ConversationalRetrievalChain

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)

def qna(question: str, vector_name: str, chat_history=[]):

    logging.debug("Calling qna")

    llm, embeddings, llm_chat = pick_llm(vector_name)

    vectorstore = pick_vectorstore(vector_name, embeddings=embeddings)

    retriever = vectorstore.as_retriever(search_kwargs=dict(k=3))

    prompt = pick_prompt(vector_name, chat_history)

    # 3072 in context + 3000 in response + 2000 in prompt
    qa = ConversationalRetrievalChain.from_llm(llm_chat,
                                               retriever=retriever, 
                                               chain_type="stuff",
                                               return_source_documents=True,
                                               verbose=True,
                                               output_key='answer',
                                               combine_docs_chain_kwargs={'prompt': prompt},
                                               condense_question_llm=llm)

    try:
        result = qa({"question": question, "chat_history": chat_history})
    except Exception as err:
        logging.error(traceback.format_exc())
        result = {"answer": f"An error occurred while asking: {question}: {str(err)}"}
    
    return result