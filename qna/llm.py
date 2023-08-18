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

        logging.debug(f"Supabase URL: {supabase_url} vector_name: {vector_name}")
        
        supabase: Client = create_client(supabase_url, supabase_key)

        vectorstore = SupabaseVectorStore(supabase, 
                                          embeddings,
                                          table_name=vector_name,
                                          query_name=f'match_documents_{vector_name}')

        logging.debug("Chose Supabase")
    elif vs_str == 'cloudsql':
        from qna.database import setup_cloudsql
        # needs this merged in https://github.com/hwchase17/langchain/issues/2219
        from langchain.vectorstores.pgvector import PGVector

        logging.debug("Inititaing CloudSQL pgvector")
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
        
        logging.debug("Chose CloudSQL")

    else:
        raise NotImplementedError(f'No llm implemented for {vs_str}')   

    return vectorstore

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
If your memories don't help with your answer, just use them to set the tone and style of your response.
Indicate in your reply how sure you are about your answer, for example whether you are certain, taking your best guess, or its very speculative.

If you don't know, just say you don't know - don't make anything up. Avoid generic boilerplate answers.
Consider why the question was asked, and offer follow up questions linked to those reasons.
Match the level of detail in your answer to the question. A more detailed explanation is needed if the question is very specific.
Any questions about how you work should direct users to issue the `!help` command.
"""
    if prompt_str is not None:
        if "{context}" in prompt_str:
            raise ValueError("prompt must not contain a string '{context}'")
        if "{question}" in prompt_str:
            raise ValueError("prompt must not contain a string '{question}'")
        prompt_str_default = prompt_str_default + "\n" + prompt_str
    
    chat_summary = ""
    if len(chat_history) != 0:
        chat_summary = get_chat_history(chat_history, vector_name)
    
    follow_up = "\nIf you need more information to make your reply more certain, ask a follow up question"

    agent_buddy, agent_description = pick_chat_buddy(vector_name)
    if agent_buddy:
        follow_up += f""" to your friend explicitly including thier name: {agent_buddy}. 
{agent_buddy} is {agent_description} and any replies are in your chat history.  
"""
    else:
        follow_up += ".\n"

    memory_str = "\n## Your Memory\n{context}\n"
    current_conversation =f"## Current Conversation\n{chat_summary}\n"
    current_conversation = current_conversation.replace("{","{{").replace("}","}}") #escape {} characters
    my_q = "## My Question\n{question}\n## Your response:\n"
    if agent_buddy:
        buddy_question = """
(If necessary) Your Question to {agent_buddy}: (a detailed description of the question you need to have answered by using a python program)
My Friend's Response:\n"""

    prompt_template = prompt_str_default + follow_up + memory_str + current_conversation + my_q + buddy_question
    
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
    return None


def pick_agent(vector_name):
    agent_str = load_config_key("agent", vector_name)
    if agent_str == "yes":
        return True
    
    return False

def pick_shared_vectorstore(vector_name, embeddings):
    shared_vectorstore = load_config_key("shared_vectorstore", vector_name)
    vectorstore = pick_vectorstore(shared_vectorstore, embeddings)
    return vectorstore