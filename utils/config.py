import logging, os, json

def load_config(filename):
    
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.dirname(script_dir)

    # Join the script directory with the filename
    config_path = os.path.join(parent_dir, filename)
    logging.info(f"Loading config file: {config_path}")

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