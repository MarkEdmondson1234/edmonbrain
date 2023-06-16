import os, json
import logging

from langchain.embeddings import OpenAIEmbeddings
from langchain.llms import OpenAI

from langchain.llms import VertexAI
from langchain.embeddings import VertexAIEmbeddings

def load_config(filename):
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.dirname(script_dir)

    # Join the script directory with the filename
    config_path = os.path.join(parent_dir, filename)

    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

def pick_llm(vector_name):
    # located in the parent directory e.g. config.json, qna/llm.py
    config = load_config("config.json")
    llm_config = config.get(vector_name, None)
    llm_str = llm_config.get("llm", None)
    if llm_str is None:
        raise NotImplementedError(f"Need to provide llm_config for vector_name: {vector_name}")
    
    if llm_str == 'openai':
        llm = OpenAI(temperature=0)
        embeddings = OpenAIEmbeddings()
    elif llm_str == 'vertex':
        llm = VertexAI(model_name = "chat-bison", temperature=0, max_output_tokens=1024)
        embeddings = VertexAIEmbeddings()
    elif llm_str == 'codey':
        llm = VertexAI(model_name = "codechat-bison", temperature=0.5, max_output_tokens=2048)
        embeddings = VertexAIEmbeddings()
    else:
        raise NotImplementedError(f'No llm implemented for {llm_str}')   
    
    logging.info(f'Using {llm_str}')

    return llm, embeddings