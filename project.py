from flask import Flask, render_template, request, send_from_directory, redirect, url_for
import xml.etree.ElementTree as ET
import pandas as pd
import os
import csv

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FILE_PATH = os.path.join(UPLOAD_FOLDER, 'processed_data.csv')
ALLOWED_EXTENSIONS = {'xml', 'txt'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Load existing processed data if available
if os.path.exists(PROCESSED_FILE_PATH):
    processed_data = pd.read_csv(PROCESSED_FILE_PATH)
else:
    processed_data = None

def parse_xml(file_data):
    root = ET.fromstring(file_data)
    start_parsing = False
    elements = []
    for element in root.iter():
        if start_parsing:
            id_value = element.get('id')
            if id_value is not None:
                element_dict = {
                    'id': id_value,
                    'source': element.get('source', ''),
                    'target': element.get('target', ''),
                    'value': element.get('value', 'Выполняет')
                }
                elements.append(element_dict)
        elif element.get('id') == '1':
            start_parsing = True
    return elements

def process_data(file_data):
    elements = parse_xml(file_data)
    df = pd.DataFrame(elements)
    df.replace({'value': {'include': 'Включает'}}, inplace=True)
    if 'description' not in df.columns:
        df['description'] = ''
    return df

def create_links():
    global processed_data
    links = {}
    if processed_data is not None and not processed_data.empty:
        id_to_name = processed_data.set_index('id')['value'].to_dict()
        for index, row in processed_data.iterrows():
            source_id = row['source']
            target_id = row['target']
            value = row['value']
            source_name = id_to_name.get(source_id, '')
            target_name = id_to_name.get(target_id, '')
            # Swap if the object is a target and modify the connection type
            if target_name and source_name:
                if target_name == id_to_name.get(row['id']):
                    source_name, target_name = target_name, source_name
                links[index] = {
                    'source': source_name,
                    'value': value,
                    'target': target_name
                }
    return links

@app.route('/', methods=['GET', 'POST'])
def index():
    global processed_data
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', error="No file part", files=os.listdir(UPLOAD_FOLDER))
        file = request.files['file']
        if file.filename == '':
            return render_template('index.html', error="Файл отсутствует!", files=os.listdir(UPLOAD_FOLDER))
        uploaded_file_data = file.read()
        processed_data = process_data(uploaded_file_data)
        processed_data.to_csv(PROCESSED_FILE_PATH, index=False)
        return render_template('index.html', message="Файл успешно загружен!", files=os.listdir(UPLOAD_FOLDER))
    return render_template('index.html', files=os.listdir(UPLOAD_FOLDER))

@app.route('/show_data', methods=['GET'])
def show_data():
    global processed_data
    if processed_data is not None:
        return render_template('show_data.html', processed_data=processed_data)
    else:
        return render_template('index.html', error="No processed data available")

@app.route('/show_descriptions', methods=['GET', 'POST'])
def show_descriptions():
    global processed_data
    if request.method == 'POST':
        update_description(request.form)
        return render_template('show_descriptions.html', processed_data=processed_data)
    if processed_data is not None:
        return render_template('show_descriptions.html', processed_data=processed_data)
    else:
        return render_template('index.html', error="No processed data available")

def update_description(form_data):
    global processed_data
    if processed_data is not None:
        for index, row in processed_data.iterrows():
            description_key = f"description_{index}"
            if description_key in form_data:
                processed_data.at[index, 'description'] = form_data[description_key]
        processed_data.to_csv(PROCESSED_FILE_PATH, index=False)

@app.route('/create_links', methods=['POST'])
def create_links_route():
    create_links()
    return render_template('index.html', message="Links created successfully!", files=os.listdir(UPLOAD_FOLDER))

def update_links(form_data):
    global processed_data
    if processed_data is not None:
        for index, row in processed_data.iterrows():
            value_key = f"value_{index}"
            if value_key in form_data:
                processed_data.at[index, 'value'] = form_data[value_key]
        processed_data.to_csv(PROCESSED_FILE_PATH, index=False)

@app.route('/show_connections/<element>', methods=['GET'])
def show_connections(element):
    global processed_data
    if processed_data is not None:
        row_with_value = processed_data[processed_data['value'] == element]
        if not row_with_value.empty:
            id_value = row_with_value.iloc[0]['id']
            connections = processed_data[
                (processed_data['source'] == id_value) | (processed_data['target'] == id_value)
            ].reset_index(drop=True)
            def get_name_and_description(element_id):
                name = processed_data[processed_data['id'] == element_id]['value'].iloc[0]
                description = processed_data[processed_data['id'] == element_id]['description'].iloc[0]
                return name, description
            connections['source'], connections['source_description'] = zip(*connections['source'].map(get_name_and_description))
            connections['target'], connections['target_description'] = zip(*connections['target'].map(get_name_and_description))
            # Swap source and target if necessary and update value
            for idx, row in connections.iterrows():
                if row['target'] == element:
                    connections.at[idx, 'source'], connections.at[idx, 'target'] = row['target'], row['source']
                    connections.at[idx, 'source_description'], connections.at[idx, 'target_description'] = row['target_description'], row['source_description']

            connections.drop(['description', 'id'], axis=1, inplace=True)
            with open('connections.csv', 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['source', 'source_description', 'value', 'target', 'target_description'])
                for index, row in connections.iterrows():
                    writer.writerow([row['source'], row['source_description'], row['value'], row['target'], row['target_description']])
            return render_template('show_connections.html', connections=connections.values.tolist(), id_value=id_value)
        else:
            return f"No row found with value '{element}'"
    else:
        return render_template('index.html', error="No processed data available")

@app.route('/show_links', methods=['GET', 'POST'])
def show_links():
    global processed_data
    if request.method == 'POST':
        update_links(request.form)
        links = create_links()
        return render_template('show_links.html', links=links)
    if processed_data is not None and not processed_data.empty:
        links = create_links()
        return render_template('show_links.html', links=links)
    else:
        return render_template('index.html', error="No processed data available")

@app.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True)
