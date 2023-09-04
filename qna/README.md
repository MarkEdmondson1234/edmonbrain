# QNA

Needs secret manager:

UNSTRCUTURED_KEY: https://www.unstructured.io/api-key/

if you are calling API, or deploy your own Unstrucutred instance from [this folder](../unstructured)

The config.json file should be uploaded to the root of the GCP bucket you are using.

It also includes a list of file extensions the GitLoader will load when indexing an entire repository.  This is limited to exclude things like HTML that should go through the Unstructured loader instead. Currently ignores those files TODO: send them to Unstrcutured instead

Example:

```json
{
    "code_extensions": [".py", ".js", ".java", ".c", ".cpp", ".cs", ".rb", ".php", ".txt", ".md", ".json", ".yaml", ".sql", ".r"],
	"edmonbrain_vertex":{
        "llm":"vertex",
        "vectorstore": "supabase",
        "prompt": "You are a British chatty AI who always works step by step logically through why you are answering any particular question."
    },
    "codey":{
        "llm":"codey",
        "vectorstore": "supabase",
        "prompt": "You are an expert code assistant AI who always describes step by step logically through why you are answering any particular question, with illustrative code examples."
    },
	"fnd":{
        "llm":"openai",
        "vectorstore": "supabase"
    },
	"sanne":{
        "llm":"openai",
        "vectorstore": "supabase",
        "prompt": "You are a feminine Danish AI who works for a Danish female freelance games designer who makes educational games. You always answer by describing step by step logically through why you are answering any particular question.  Answer in Danish unless otherwise requested."

    },
    "edmonbrain":{
        "llm":"openai",
        "vectorstore": "supabase",
        "prompt": "You are a chatty AI who always works step by step logically through why you are answering any particular question."
    },
    "jesper":{
        "llm":"openai",
        "vectorstore": "supabase",
        "prompt": "You are a Danish AI who works with a Science Educational Professor. Answer in Danish unless otherwise requested"

    }
}
```

Discovery Search neeeds 
* Discovery Engine viewer role added