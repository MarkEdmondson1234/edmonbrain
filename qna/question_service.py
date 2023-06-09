import os, logging

from langchain.vectorstores import SupabaseVectorStore
from qna.llm import pick_llm

#https://python.langchain.com/en/latest/modules/chains/index_examples/chat_vector_db.html
from langchain.chains import ConversationalRetrievalChain

from supabase import Client, create_client
from dotenv import load_dotenv

load_dotenv()

def qna(question: str, vector_name: str, chat_history=None):

    llm, embeddings = pick_llm(vector_name)

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

    retriever = vectorstore.as_retriever(search_kwargs=dict(k=4))

    qa = ConversationalRetrievalChain.from_llm(llm, 
                                               retriever=retriever, 
                                               return_source_documents=True,
                                               verbose=True,
                                               output_key='answer',
                                               max_tokens_limit=3500)

    result = qa({"question": question, "chat_history": chat_history})
    
    return result