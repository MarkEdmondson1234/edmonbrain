from flask import Flask
import sys, os
import traceback
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

from dreamer.dream import dream

app = Flask(__name__)

@app.route('/dream/<vector_name>', methods=['GET'])
def create_dream(vector_name):
    dream(vector_name)
    return {
        "message": f"Dream for vector {vector_name} created and uploaded successfully."
    }

if __name__ == '__main__':
    app.run(debug=True)
