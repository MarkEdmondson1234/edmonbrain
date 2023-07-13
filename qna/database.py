import psycopg2
from psycopg2.extensions import adapt
import logging
import os
import time
import math

logging.basicConfig(level=logging.INFO)

def setup_supabase(vector_name:str, verbose:bool=False):
    hello = f"Setting up supabase database: {vector_name}"
    logging.debug(hello)
    if verbose:
        print(hello)
    setup_database(vector_name, verbose)

def setup_cloudsql(vector_name:str, verbose:bool=False):
    hello = f"Setting up cloudsql database: {vector_name}"
    logging.debug(hello)
    if verbose:
        print(hello)
    setup_database(vector_name, verbose)

def lookup_connection_env(vector_name:str):
    from qna.llm import load_config
    config = load_config("config.json")
    llm_config = config.get(vector_name, None)
    if llm_config is None:
        raise ValueError("No llm_config was found")
    logging.debug(f'llm_config: {llm_config} for {vector_name}')
    vs_str = llm_config.get("vectorstore", None)
    if vs_str == "supabase":
        return "DB_CONNECTION_STRING"
    elif vs_str == "cloudsql":
        return "PGVECTOR_CONNECTION_STRING"
    
    raise ValueError("Could not find vectorstore for {vs_str}")


def get_vector_size(vector_name: str):
    from qna.llm import load_config
    config = load_config("config.json")
    llm_config = config.get(vector_name, None)
    if llm_config is None:
        raise ValueError("No llm_config was found")
    logging.debug(f'llm_config: {llm_config} for {vector_name}')
    llm_str = llm_config.get("llm", None)

    vector_size = 768
    if llm_str == 'openai':
        vector_size = 1536 # openai

    logging.debug(f'vector size: {vector_size}')
    return vector_size

def setup_database(vector_name:str, verbose:bool=False):

    connection_env = lookup_connection_env(vector_name)
    
    params = {'vector_name': vector_name, 'vector_size': get_vector_size(vector_name)}

    execute_sql_from_file("sql/sb/setup.sql", params, verbose=verbose, connection_env=connection_env)
    execute_sql_from_file("sql/sb/create_table.sql", params, verbose=verbose, connection_env=connection_env)
    execute_sql_from_file("sql/sb/create_function.sql", params, verbose=verbose, connection_env=connection_env)

    if verbose: print("Ran all setup SQL statements")
    
    return True

def return_sources_last24(vector_name:str):
    params = {'vector_name': vector_name, 'time_period':'1 day'}
    return execute_sql_from_file("sql/sb/return_sources.sql", params, return_rows=True, 
                                 connection_env=lookup_connection_env(vector_name))

def delete_row_from_source(source: str, vector_name:str):
    # adapt the user input and decode from bytes to string to protect against sql injection
    source = adapt(source).getquoted().decode()
    sql_params = {'source_delete': source}
    sql = f"""
        DELETE FROM {vector_name}
        WHERE metadata->>'source' = %(source_delete)s
    """

    do_sql(sql, sql_params=sql_params, connection_env=lookup_connection_env(vector_name))



def do_sql(sql, sql_params=None, return_rows=False, verbose=False, connection_env='DB_CONNECTION_STRING', max_retries=5):

    if connection_env is None:
        raise ValueError("Need to specify connection_env to connect to DB")

    rows = []
    connection_string = os.getenv(connection_env, None)
    if connection_string is None:
        raise ValueError("No connection string")

    for attempt in range(max_retries):
        try:
            connection = psycopg2.connect(connection_string)
            cursor = connection.cursor()

            if verbose:
                logging.info(f"SQL: {sql}")
            else:
                pass
            # execute the SQL - raise the error if already found
            cursor.execute(sql, sql_params)

            # commit the transaction to save changes to the database
            connection.commit()

            if return_rows:
                rows = cursor.fetchall()

            break  # If all operations were successful, break the loop

        except (psycopg2.errors.DuplicateObject, 
                psycopg2.errors.DuplicateTable, 
                psycopg2.errors.DuplicateFunction) as e:
            logging.debug(str(e))
            if verbose:
                print(str(e))

        except psycopg2.errors.InternalError as error:
            logging.error(f"InternalError, retrying... Attempt {attempt+1} out of {max_retries}")
            time.sleep(math.pow(2, attempt))  # Exponential backoff
            continue  # Go to the next iteration of the loop to retry the operation

        except (Exception, psycopg2.Error) as error:
            logging.error(f"Error while connecting to PostgreSQL: {str(error)}", exc_info=True)

        finally:
            if connection:
                cursor.close()
                connection.close()
                logging.debug("PostgreSQL connection is closed")
    
        # If we've exhausted all retries and still haven't succeeded, raise an error
        if attempt + 1 == max_retries:
            raise Exception("Maximum number of retries exceeded")

    if rows:
        return rows
    
    return None


def execute_sql_from_file(filepath, params, return_rows=False, verbose=False, connection_env=None):

     # Get the directory of this Python script
    dir_path = os.path.dirname(os.path.realpath(__file__))
    # Build the full filepath by joining the directory with the filename
    filepath = os.path.join(dir_path, filepath)

    # read the SQL file
    with open(filepath, 'r') as file:
        sql = file.read()

    # substitute placeholders in the SQL
    sql = sql.format(**params)
    rows = do_sql(sql, return_rows=return_rows, verbose=verbose, connection_env=connection_env)
    
    if return_rows:
        if rows is None: return None
        return rows
    
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Setup a database",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("vectorname", help="The namespace for vectorstore")
    parser.add_argument("connection_env", help="The connection environment string", default="DB_CONNECTION_STRING")

    args = parser.parse_args()
    config = vars(args)

    vector_name = config.get('vectorname', None)
    if vector_name is None:
        raise ValueError("Must provide a vectorname")
    
    setup_database(vector_name, verbose=True, connection_env=config.get("connection_env"))

