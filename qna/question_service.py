import os, logging

from langchain.vectorstores import SupabaseVectorStore
from qna.llm import pick_llm

#https://python.langchain.com/en/latest/modules/chains/index_examples/chat_vector_db.html
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts.prompt import PromptTemplate

from supabase import Client, create_client
from dotenv import load_dotenv

load_dotenv()

def qna(question: str, vector_name: str, chat_history=[]):

    logging.debug("Calling qna")

    llm, embeddings, llm_chat = pick_llm(vector_name)

    logging.info(f"Initiating Supabase store: {vector_name}")
    # init embedding and vector store
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')

    logging.info(f"Supabase URL: {supabase_url} vector_name: {vector_name}")
    
    supabase: Client = create_client(supabase_url, supabase_key)

    vectorstore = SupabaseVectorStore(supabase, 
                                      embeddings, 
                                      table_name=vector_name,
                                      query_name=f'match_documents_{vector_name}')

    logging.info(f"vectorstore.table_name {vectorstore.table_name}")

    retriever = vectorstore.as_retriever(search_kwargs=dict(k=3))

    prompt_template = """Use the following pieces of context to answer the question at the end. If you don't know the answer, reply stating you have no context sources to back up your reply, but taking a best guess.

    {context}

    Question: {question}
    Helpful Answer:"""

    QA_PROMPT = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )

    # how to add custom prompt?
    # llm_chat does not work with combine_docs_chain_kwargs: 
    # File "/usr/local/lib/python3.9/site-packages/langchain/chat_models/vertexai.py", line 136, in _generate
    #response = chat.send_message(question.content, **params)
    # TypeError: send_message() got an unexpected keyword argument 'context'"
    qa = ConversationalRetrievalChain.from_llm(llm,
                                               retriever=retriever, 
                                               return_source_documents=True,
                                               verbose=True,
                                               output_key='answer',
                                               combine_docs_chain_kwargs={'prompt': QA_PROMPT},
                                               condense_question_llm=llm,
                                               max_tokens_limit=3500)

    result = qa({"question": question, "chat_history": chat_history})
    
    return result