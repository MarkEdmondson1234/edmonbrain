from qna.loaders import read_gdrive_to_document

url = 'https://drive.google.com/drive/folders/1ikLHY_TlCmld2Dc5htBRvZUFVDO69ygf'

docs = read_gdrive_to_document(url)

if docs:
    for doc in docs:
        print(doc)
else:
    print('No docs found')