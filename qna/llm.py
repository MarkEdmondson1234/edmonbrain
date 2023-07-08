import os, json
import logging


def load_config(filename):
    logging.debug("Loading config for llm")
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.dirname(script_dir)

    # Join the script directory with the filename
    config_path = os.path.join(parent_dir, filename)

    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

def pick_llm(vector_name):
    logging.debug('Picking llm')
    # located in the parent directory e.g. config.json, qna/llm.py
    config = load_config("config.json")
    llm_config = config.get(vector_name, None)
    if llm_config is None:
        raise ValueError("No llm_config was found")
    logging.info(f'llm_config: {llm_config} for {vector_name}')
    llm_str = llm_config.get("llm", None)
    if llm_str is None:
        raise NotImplementedError(f"Need to provide llm_config for vector_name: {vector_name}")
    
    if llm_str == 'openai':
        from langchain.embeddings import OpenAIEmbeddings
        from langchain.llms import OpenAI
        from langchain.chat_models import ChatOpenAI

        #llm = OpenAI(temperature=0)
        llm_chat = ChatOpenAI(model="gpt-4", temperature=0.2, max_tokens=5000)
        llm = OpenAI(model="gpt-3-turbo", temperature=0)
        embeddings = OpenAIEmbeddings()
        logging.info("Chose OpenAI")
    elif llm_str == 'vertex':
        from langchain.llms import VertexAI
        from langchain.embeddings import VertexAIEmbeddings
        from langchain.chat_models import ChatVertexAI
        llm = VertexAI(temperature=0, max_output_tokens=1024)
        llm_chat = ChatVertexAI(temperature=0, max_output_tokens=1024)
        embeddings = VertexAIEmbeddings()
        logging.info("Chose VertexAI text-bison")
    elif llm_str == 'codey':
        from langchain.llms import VertexAI
        from langchain.embeddings import VertexAIEmbeddings
        from langchain.chat_models import ChatVertexAI
        llm = VertexAI(model_name = "code-bison", temperature=0.5, max_output_tokens=2048)
        llm_chat = ChatVertexAI(model_name="codechat-bison", max_output_tokens=2048)
        embeddings = VertexAIEmbeddings()
        logging.info("Chose VertexAI code-bison")
    else:
        raise NotImplementedError(f'No llm implemented for {llm_str}')   

    return llm, embeddings, llm_chat


def pick_vectorstore(vector_name, embeddings):
    logging.debug('Picking vectorstore')
    # located in the parent directory e.g. config.json, qna/llm.py
    config = load_config("config.json")
    llm_config = config.get(vector_name, None)
    if llm_config is None:
        raise ValueError("No llm_config was found")
    logging.info(f'llm_config: {llm_config} for {vector_name}')
    vs_str = llm_config.get("vectorstore", None)
    if vs_str is None:
        raise NotImplementedError(f"Need to provide llm_config for vector_name: {vector_name}")
    
    if vs_str == 'supabase':
        from supabase import Client, create_client
        from langchain.vectorstores import SupabaseVectorStore
        from qna.database import setup_supabase

        logging.debug(f"Initiating Supabase store: {vector_name}")
        setup_supabase(vector_name)
        # init embedding and vector store
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')

        logging.info(f"Supabase URL: {supabase_url} vector_name: {vector_name}")
        
        supabase: Client = create_client(supabase_url, supabase_key)

        vectorstore = SupabaseVectorStore(supabase, 
                                          embeddings,
                                          table_name=vector_name,
                                          query_name=f'match_documents_{vector_name}')

        logging.info("Chose Supabase")
    elif vs_str == 'cloudsql':
        from qna.database import setup_cloudsql
        # needs this merged in https://github.com/hwchase17/langchain/issues/2219
        from langchain.vectorstores.pgvector import PGVector

        logging.info("Inititaing CloudSQL pgvector")
        setup_cloudsql(vector_name)

        # https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/pgvector
        CONNECTION_STRING = os.environ.get("PGVECTOR_CONNECTION_STRING")
        # postgresql://brainuser:password@10.24.0.3:5432/brain

        from qna.database import get_vector_size
        vector_size = get_vector_size(vector_name)

        os.environ["PGVECTOR_VECTOR_SIZE"] = str(vector_size)
        vectorstore = PGVector(connection_string=CONNECTION_STRING,
            embedding_function=embeddings,
            collection_name=vector_name,
            #pre_delete_collection=True # for testing purposes
            )
        
        logging.info("Chose CloudSQL")

    else:
        raise NotImplementedError(f'No llm implemented for {vs_str}')   

    return vectorstore