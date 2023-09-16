import os, json
import logging
import datetime
from langchain.prompts.prompt import PromptTemplate

logging.basicConfig(level=logging.INFO)

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

def load_config_key(key, vector_name):
    config = load_config("config.json")
    llm_config = config.get(vector_name, None)
    if llm_config is None:
        raise ValueError("No llm_config was found")
    logging.debug(f'llm_config: {llm_config} for {vector_name}')
    key_str = llm_config.get(key, None)
    
    return key_str

def pick_llm(vector_name):
    logging.debug('Picking llm')
    
    llm_str = load_config_key("llm", vector_name)
    
    if llm_str == 'openai':
        from langchain.embeddings import OpenAIEmbeddings
        #from langchain.llms import OpenAI
        from langchain.chat_models import ChatOpenAI

        #llm = OpenAI(temperature=0)
        llm_chat = ChatOpenAI(model="gpt-4", temperature=0.3, max_tokens=3000)
        llm = ChatOpenAI(model="gpt-3.5-turbo-16k", temperature=0, max_tokens=11000)
        embeddings = OpenAIEmbeddings()
        logging.debug("Chose OpenAI")
    elif llm_str == 'vertex':
        from langchain.llms import VertexAI
        from langchain.embeddings import VertexAIEmbeddings
        from langchain.chat_models import ChatVertexAI
        llm = ChatVertexAI(temperature=0, max_output_tokens=1024)
        llm_chat = ChatVertexAI(temperature=0, max_output_tokens=1024)
        embeddings = VertexAIEmbeddings()
        logging.debug("Chose VertexAI text-bison")
    elif llm_str == 'codey':
        from langchain.llms import VertexAI
        from langchain.embeddings import VertexAIEmbeddings
        from langchain.chat_models import ChatVertexAI
        llm = VertexAI(model_name = "code-bison", temperature=0.5, max_output_tokens=2048)
        llm_chat = ChatVertexAI(model_name="codechat-bison", max_output_tokens=2048)
        embeddings = VertexAIEmbeddings()
        logging.debug("Chose VertexAI code-bison")
    else:
        raise NotImplementedError(f'No llm implemented for {llm_str}')   

    return llm, embeddings, llm_chat

def pick_streaming(vector_name):
    
    llm_str = load_config_key("llm", vector_name)
    
    if llm_str == 'openai':
        return True
    
    return False
    
def pick_vectorstore(vector_name, embeddings):
    logging.debug('Picking vectorstore')

    vs_str = load_config_key("vectorstore", vector_name)

    shared_vs = False
    if vs_str is None:
        # look for shared vector store
        shared_vn = load_config_key("shared_vectorstore", vector_name)
        if shared_vn is None:
            raise NotImplementedError(f"No vectorstore or shared_vectorstore found in llm_config for vector_name: {vector_name}")
        logging.info(f"Loading shared vectorstore {shared_vn}")
        vs_str = load_config_key("vectorstore", shared_vn)
        shared_vs = True
        vector_name = shared_vn
    
    if vs_str == 'supabase':
        from supabase import Client, create_client
        from langchain.vectorstores import SupabaseVectorStore
        from qna.database import setup_supabase

        if not shared_vs:
            logging.debug(f"Initiating Supabase store: {vector_name}")
            setup_supabase(vector_name)
        # init embedding and vector store
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')

        logging.debug(f"Supabase URL: {supabase_url} vector_name: {vector_name}")

        supabase: Client = create_client(supabase_url, supabase_key)

        vectorstore = SupabaseVectorStore(supabase, 
                                        embeddings,
                                        table_name=vector_name,
                                        query_name=f'match_documents_{vector_name}')

        logging.debug("Chose Supabase")
    elif vs_str == 'cloudsql':
        from langchain.vectorstores.pgvector import PGVector

        logging.debug("Inititaing CloudSQL pgvector")
        #setup_cloudsql(vector_name) 

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

        logging.debug("Chose CloudSQL")
    elif vs_str == 'alloydb':  # exact same as CloudSQL for now
        from langchain.vectorstores.pgvector import PGVector

        logging.info("Inititaing AlloyDB pgvector")
        #setup_cloudsql(vector_name) 

        # https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/pgvector
        CONNECTION_STRING = os.environ.get("ALLOYDB_CONNECTION_STRING",None)
        if CONNECTION_STRING is None:
            logging.info("Did not find ALLOYDB_CONNECTION_STRING fallback to PGVECTOR_CONNECTION_STRING")
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

        logging.info("Chose AlloyDB")

    else:
        raise NotImplementedError(f'No llm implemented for {vs_str}')   

    return vectorstore

def pick_retriever(vector_name, embeddings):
    vectorstore = pick_vectorstore(vector_name, embeddings=embeddings)

    vs_str = load_config_key("vectorstore", vector_name)
    
    if vs_str == 'supabase' and load_config_key("self_query", vector_name):
        from qna.self_query import get_self_query_retriever
        llm, _, _ = pick_llm(vector_name)

        sq_retriver = get_self_query_retriever(llm, vectorstore)
    else:
        logging.info(f"No self_querying retriever available for {vs_str}")
        sq_retriver = None

    vs_retriever = vectorstore.as_retriever(search_kwargs=dict(k=3))
    
    rt_list = load_config_key("retrievers", vector_name)

    # early return if only one retriever is available
    if (not rt_list or len(rt_list) == 0) and sq_retriver is None:
        logging.info(f"Only one retriever available - vector store {vs_str}")
        return vs_retriever
    
    if sq_retriver is not None:
        all_retrievers = [vs_retriever, sq_retriver]
    else:
        all_retrievers = [vs_retriever]

    from langchain.retrievers import MergerRetriever
    from langchain.retrievers import GoogleCloudEnterpriseSearchRetriever
    _, filter_embeddings, _ = pick_llm(vector_name)

    for key, value in rt_list.items():
        from utils.gcp import get_gcp_project
        if value.get("provider") == "GoogleCloudEnterpriseSearchRetriever":
            gcp_retriever = GoogleCloudEnterpriseSearchRetriever(
                project_id=get_gcp_project(),
                search_engine_id=key,
                location_id=value.get("location", "global"),
                engine_data_type=1 if value.get("type","unstructured") == "structured" else 0,
                query_expansion_condition=2
            )
        else:
            raise NotImplementedError(f"Retriver not supported: {value}")
        
        all_retrievers.append(gcp_retriever)
    lotr = MergerRetriever(retrievers=all_retrievers)

    # https://python.langchain.com/docs/integrations/retrievers/merger_retriever
    from langchain.document_transformers import (
        EmbeddingsRedundantFilter,
        EmbeddingsClusteringFilter,
    )
    from langchain.retrievers.document_compressors import DocumentCompressorPipeline
    from langchain.retrievers import ContextualCompressionRetriever

    filter = EmbeddingsRedundantFilter(embeddings=filter_embeddings)
    pipeline = DocumentCompressorPipeline(transformers=[filter])
    retriever = ContextualCompressionRetriever(
        base_compressor=pipeline, base_retriever=lotr, 
        k=3)

    return retriever


def get_chat_history(inputs, vector_name, last_chars=1000, summary_chars=1500) -> str:
    from langchain.schema import Document
    from qna.summarise import summarise_docs

    # Prepare the full chat history
    res = []
    for human, ai in inputs:
        res.append(f"Human:{human}\nAI:{ai}")
    full_history = "\n".join(res)
    
    # Get the last `last_chars` characters of the full chat history
    last_bits = []
    for human, ai in reversed(inputs):
        add_me = f"Human:{human}\nAI:{ai}"
        last_bits.append(add_me)

    recent_history = "\n".join(reversed(last_bits))
    recent_history = recent_history[-last_chars:]
    logging.info(f"Recent chat history: {recent_history}")
    
    # Summarize chat history too
    remaining_history = full_history
    logging.info(f"Remaining chat history: {remaining_history}")
    doc_history = Document(page_content=remaining_history)
    chat_summary = summarise_docs([doc_history], vector_name=vector_name, skip_if_less=last_chars)
    text_sum = ""
    for summ in chat_summary:
        text_sum += summ.page_content + "\n"
    
    logging.info(f"Conversation Summary: {text_sum}")
    
    # Make sure the summary is not longer than `summary_chars` characters
    summary = text_sum[:summary_chars]
    
    # Concatenate the summary and the last `last_chars` characters of the chat history
    return summary + "\n### Recent Chat History\n..." + recent_history



def pick_prompt(vector_name, chat_history=[]):
    """Pick a custom prompt"""
    logging.debug('Picking prompt')

    prompt_str = load_config_key("prompt", vector_name)

    the_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')
    prompt_str_default = f"""You are Edmonbrain the chat bot created by Mark Edmondson. It is now {the_date}.
Use your memory to answer the question at the end.
Indicate in your reply how sure you are about your answer, for example whether you are certain, taking your best guess, or its very speculative.

If you don't know, just say you don't know - don't make anything up. Avoid generic boilerplate answers.
Consider why the question was asked, and offer follow up questions linked to those reasons.
Any questions about how you work should direct users to issue the `!help` command.
"""
    if prompt_str is not None:
        if "{context}" in prompt_str:
            raise ValueError("prompt must not contain a string '{context}'")
        if "{question}" in prompt_str:
            raise ValueError("prompt must not contain a string '{question}'")
        prompt_str_default = prompt_str_default + "\n" + prompt_str
    
    chat_summary = ""
    original_question = ""
    if len(chat_history) != 0:
        original_question = chat_history[0][0]
        chat_summary = get_chat_history(chat_history, vector_name)
    
    follow_up = "\nIf you can't answer the human's question without more information, ask a follow up question"

    agent_buddy, agent_description = pick_chat_buddy(vector_name)
    if agent_buddy:
        follow_up += f""" either to the human, or to your friend bot.
You bot friend will reply back to you within your chat history.
Ask {agent_buddy} for help with topics: {agent_description}
Ask clarification questions to the human and wait for response if your friend bot can't help.
Don't repeat the question if you can see the answer in the chat history (from any source)  
This means there are three people in this conversation - you, the human and your assistant bot.
Asking questions to your friend bot are only allowed with this format:
€€Question€€ 
(your question here, including all required information needed to answer the question fully)
Can you help, {agent_buddy} , with the above question?
€€End Question€€
"""
    else:
        follow_up += ".\n"

    memory_str = "\n## Your Memory (ignore if not relevant to question)\n{context}\n"

    current_conversation = ""
    if chat_summary != "":
        current_conversation =f"## Current Conversation\n{chat_summary}\n"
        current_conversation = current_conversation.replace("{","{{").replace("}","}}") #escape {} characters
   
    buddy_question = ""
    my_q = "## Current Question\n{question}\n"
    if agent_buddy:
        buddy_question = f"""(Including, if needed, your question to {agent_buddy})"""
        my_q = f"## Original Question that started conversation\n{original_question}\n" + my_q

    prompt_template = prompt_str_default + follow_up + memory_str + current_conversation + my_q + buddy_question + "\n## Your response:\n"
    
    logging.debug(f"--Prompt_template: {prompt_template}") 
    QA_PROMPT = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )

    return QA_PROMPT

def pick_chat_buddy(vector_name):
    chat_buddy = load_config_key("chat_buddy", vector_name)
    if chat_buddy is not None:
        logging.info(f"Got chat buddy {chat_buddy} for {vector_name}")
        buddy_description = load_config_key("chat_buddy_description", vector_name)
        return chat_buddy, buddy_description
    return None, None


def pick_agent(vector_name):
    agent_str = load_config_key("agent", vector_name)
    if agent_str == "yes":
        return True
    
    return False

def pick_shared_vectorstore(vector_name, embeddings):
    shared_vectorstore = load_config_key("shared_vectorstore", vector_name)
    vectorstore = pick_vectorstore(shared_vectorstore, embeddings)
    return vectorstore