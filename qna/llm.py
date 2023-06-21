import os, json
import logging

from langchain.embeddings import OpenAIEmbeddings
from langchain.llms import OpenAI

from langchain.llms import VertexAI
from langchain.embeddings import VertexAIEmbeddings

def load_config(filename):
    logging.debug("Loading config for llm")
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.dirname(script_dir)

    # Join the script directory with the filename
    config_path = os.path.join(parent_dir, filename)

    logging.info(f"Config_path: {config_path}")

    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

def pick_llm(vector_name):
    logging.debug('Picking llm')
    # located in the parent directory e.g. config.json, qna/llm.py
    config = load_config("config.json")
    logging.info(f'Loaded config.json: {config} for {vector_name}')
    llm_config = config.get(vector_name, None)
    if llm_config is None:
        raise ValueError("No llm_config was found")
    logging.info(f'llm_config: {llm_config} for {vector_name}')
    llm_str = llm_config.get("llm", None)
    logging.info(f'llm_str is: {llm_str}')
    if llm_str is None:
        raise NotImplementedError(f"Need to provide llm_config for vector_name: {vector_name}")
    
    if llm_str == 'openai':
        llm = OpenAI(temperature=0)
        embeddings = OpenAIEmbeddings()
        logging.info("Chose OpenAI")
    elif llm_str == 'vertex':
        llm = VertexAI(temperature=0, max_output_tokens=1024)
        embeddings = VertexAIEmbeddings()
        logging.info("Chose VertexAI text-bison")
    elif llm_str == 'codey':
        llm = VertexAI(model_name = "code-bison", temperature=0.5, max_output_tokens=2048)
        embeddings = VertexAIEmbeddings()
        logging.info("Chose VertexAI code-bison")
    else:
        raise NotImplementedError(f'No llm implemented for {llm_str}')   
    
    logging.info(f'Using {llm_str}')

    return llm, embeddings