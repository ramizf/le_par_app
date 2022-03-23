from flask import Flask, render_template, Response, request, redirect, url_for

app = Flask(__name__)

@app.route("/")
def index():
    import os
    from pathlib import Path
    from os.path import join, isdir, isfile, basename
    from google.cloud import storage
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'bucketkey.json'
    storage_client = storage.Client()
    bucket = storage_client.get_bucket('transcrib_bucket')
    prefix = 'Lease_docs'
    blobs = bucket.list_blobs(prefix=prefix)
    for blob in blobs:
        if blob.name.endswith("/"):
            continue
        file_split = blob.name.split("/")
        directory = "/".join(file_split[0:-1])
        Path(directory).mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(blob.name)
    return render_template('index.html')


@app.route("/forward/", methods=['POST'])
def move_forward():
    from pdf2image import convert_from_path
    import cv2
    import pytesseract
    import os
    import glob
    import spacy
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from os import listdir
    from os.path import isfile, join

    SERVICE_ACCOUNT_FILE = ('sheetskey.json')
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    #credentials = None
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    SAMPLE_SPREADSHEET_ID = '1gHxm5y-ej0z1f6yZQWAJFt9uocJ41BTAgA_0d81NT4A'
    service = build('sheets', 'v4', credentials=credentials)

    PDF_file = [f for f in listdir('Lease_docs/') if isfile(join('Lease_docs/', f))]
    PDF_file = ['Lease_docs/' + s for s in PDF_file]

    nlp = spacy.load("Lease_ner_model_55itr_drop3")


    if not os.path.exists("ex_img"):
        os.mkdir("ex_img")

    def ocr_core(img):
        text = pytesseract.image_to_string(img, config=custom_config)
        return text

    def get_gray(image):
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def remove_noise(image):
        return cv2.medianBlur(image, 5)

    def threshold(image):
        return cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    custom_config = r'--oem 3 --psm 12'

    for pdf in PDF_file:
        images = convert_from_path(pdf)
        for i in range(len(images)):
            images[i].save('ex_img/' + 'page' + str(i) + '.jpg', 'JPEG')
        x = []
        for fname in sorted(os.listdir('ex_img/')):
            img = cv2.imread(os.path.join('ex_img/',fname))
            img = get_gray(img)
            img = threshold(img)
            img = remove_noise(img)
            text = str(ocr_core(img))
            text = text.replace('\n', ' ')
            text = text.replace('/', '.')
            text = text.replace('~', '')
            text = text.replace('\\', '.')
            text = text.replace('. ', '.')
            text = text.replace(', ', ',')
            text = text.replace('  ', ' ')
            x.append(text)
        out = str(x)
        removing_files = glob.glob('file path/*.jpg')
        for i in removing_files:
            os.remove(i)
        e=[]
        doc = nlp(out)
        for ent in doc.ents:
            v=[ent.text,ent.label_]
            if v not in e:
                e.append(v)

    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                range="Sheet1!A:B").execute()


    sheet.values().append(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                          range="Sheet1!A:C", valueInputOption="USER_ENTERED",
                          insertDataOption="INSERT_ROWS", body={"values": e}).execute()

    return render_template('page1.html')


if __name__ == '__main__':
    app.run()
