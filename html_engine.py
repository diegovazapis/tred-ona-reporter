import os
import base64
import requests
import streamlit as st
from jinja2 import Template
from datetime import datetime

@st.cache_data(show_spinner=False)
def fetch_ona_image(filename, api_token, form_id=None, attachments_list=None):
    if not filename or not isinstance(filename, str) or str(filename).lower() == 'nan':
        return None
    base_name = os.path.basename(filename)
    urls = []
    
    if 'current_media_links' in st.session_state:
        for col, link in st.session_state['current_media_links'].items():
            if filename in link or base_name in link:
                urls.append(link)
                break

    if attachments_list:
        for attachment in attachments_list:
            att_filename = attachment.get('filename', '')
            att_name = attachment.get('name', '')
            if filename in att_filename or base_name in os.path.basename(att_filename) or base_name == att_name:
                dl_url = attachment.get('download_url')
                if dl_url:
                    urls.append(dl_url if dl_url.startswith('http') else f"https://api.ona.io{dl_url}")
                break

    if filename.startswith("http"):
        urls.append(filename)
    urls.append(f"https://api.ona.io/api/v1/files/{filename}")
    if form_id:
        urls.append(f"https://api.ona.io/api/v1/data/{form_id}/{filename}")
    
    for url in urls:
        try:
            # Handle S3 redirects properly without forwarding Auth header
            # And do NOT send Auth header to direct S3 URLs (Pattern -1)
            if "api.ona.io" in url:
                headers = {'Authorization': f"Token {api_token}"} if api_token else {}
                resp1 = requests.get(url, headers=headers, allow_redirects=False, timeout=10)
                
                if resp1.status_code in [301, 302, 303, 307] and 'Location' in resp1.headers:
                    final_url = resp1.headers['Location']
                    response = requests.get(final_url, timeout=15)
                else:
                    response = resp1
            else:
                response = requests.get(url, timeout=15)
                
            if response.status_code == 200:
                return response.content
        except Exception as e:
            continue
    return None

def generate_bitacora_html(header_record, instances_data, choices_map, auth_token):
    
    instances_grouped = []
    
    for inst in instances_data:
        fields_flat = []
        record_dict = inst.get('record_dict', {})
        schema = inst.get('schema', {})
        current_attachments = record_dict.get('_attachments', [])
        form_id = inst.get('form_id')
        
        def find_val(rec, target):
            if target in rec: return rec[target]
            for k, v in rec.items():
                if k == target or k.endswith(f"/{target}"): return v
            return None

        def process_node(node, current_record):
            ntype = node.get('type')
            if ntype == 'group':
                for child in node.get('children', []):
                    process_node(child, current_record)
            elif ntype == 'repeat':
                key = node.get('name')
                repeat_data = find_val(current_record, key)
                if isinstance(repeat_data, list):
                    for item in repeat_data:
                        for child in node.get('children', []):
                            process_node(child, item)
            elif ntype not in ['note', 'calculate', 'start', 'end', 'today', 'deviceid', 'phonenumber']:
                key = node.get('name')
                raw_val = find_val(current_record, key)
                
                # Filter empty values and "nan"
                if raw_val is not None and str(raw_val).strip() != "" and str(raw_val).lower() != "nan":
                    label = node.get('label', key)
                    if isinstance(label, list): label = label[0] # Handle multiple languages
                    if isinstance(label, dict): label = list(label.values())[0]
                    
                    is_image = ntype in ['photo', 'image', 'file'] or (isinstance(raw_val, str) and raw_val.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4')))
                    
                    if is_image:
                        image_files = [v.strip() for v in str(raw_val).split(',')] if ',' in str(raw_val) else [str(raw_val)]
                        images_data = []
                        for img_val in image_files:
                            if not img_val or str(img_val).lower() == 'nan': continue
                            
                            # Use robust fetch_ona_image from app.py
                            img_bytes = fetch_ona_image(img_val, auth_token, form_id=form_id, attachments_list=current_attachments)
                            
                            if img_bytes:
                                b64 = base64.b64encode(img_bytes).decode('utf-8')
                                images_data.append({'url': img_val, 'base64': f"data:image/jpeg;base64,{b64}"})
                            else:
                                # Fallback so the field is not silently ignored
                                images_data.append({'url': img_val, 'base64': None, 'error': f"Error descargando: {img_val}"})
                        
                        if images_data:
                            fields_flat.append({'label': label, 'value': images_data, 'is_image': True})
                    else:
                        # Resolve choice label if select one/multiple
                        if ntype == 'select one':
                            options = node.get('children', [])
                            if options:
                                raw_val = next((opt.get('label') for opt in options if opt.get('name') == str(raw_val)), raw_val)
                        elif ntype == 'select all that apply':
                            options = node.get('children', [])
                            if options:
                                selected_vals = str(raw_val).split(' ')
                                labels = [next((opt.get('label') for opt in options if opt.get('name') == s_val), s_val) for s_val in selected_vals]
                                raw_val = ", ".join(labels)
                        
                        fields_flat.append({'label': label, 'value': str(raw_val), 'is_image': False})

        # Add dynamically collected fields
        for child in schema.get('children', []):
            process_node(child, record_dict)
            
        # Group in chunks of 3 for the table layout
        grouped_fields = [fields_flat[i:i+3] for i in range(0, len(fields_flat), 3)]
        
        instances_grouped.append({
            'form_name': inst.get('form_name', 'Formulario'),
            'date': inst.get('date_str', ''),
            'grouped_fields': grouped_fields
        })
    
    # Use localized month names
    months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    now = datetime.now()
    print_date = f"{now.day} de {months[now.month-1]} de {now.year}"
    
    template_path = os.path.join(os.getcwd(), 'templates', 'bitacora_template.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template_str = f.read()
        
    template = Template(template_str)
    
    html_out = template.render(
        record=header_record,
        instances_grouped=instances_grouped,
        print_date=print_date
    )
    
    return html_out
