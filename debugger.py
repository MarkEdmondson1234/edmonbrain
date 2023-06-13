from qna.loaders import read_gdrive_to_document

url = 'https://drive.google.com/drive/folders/1qW3BNTsSXk6l2XnpioMvBIbcvRE1eIUp'

docs = read_gdrive_to_document(url)

if docs:
    for doc in docs:
        print(doc)
else:
    print('No docs found')