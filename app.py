import streamlit as st
import pandas as pd
import os
import requests
import json
import yaml
import time
import base64
from engine import ReportEngine
from api_handler import OnaAPIHandler
from catalog_manager import CatalogManager
from data_processor import ReportDataProcessor
from local_db import LocalDB
from io import StringIO
try:
    import pygwalker as pyg
except ImportError:
    pyg = None

# ==========================================
# 0. Cached API Wrappers (Performance Boost)
# ==========================================

def safe_json_dumps(obj):
    """Encapsulates json.dumps with a converter for NumPy/Pandas types."""
    def converter(o):
        if hasattr(o, 'item'): return o.item()
        return str(o)
    return json.dumps(obj, default=converter)

@st.cache_data(ttl=300) # Cache for 5 minutes
def get_cached_unique_values(api_token, form_id, column_name, filters_json=None):
    handler = OnaAPIHandler(api_token)
    filters = json.loads(filters_json) if filters_json else None
    return handler.get_unique_values(form_id, column_name, filters=filters)

@st.cache_data(ttl=300)
def get_cached_filtered_data(api_token, form_id, filters_json=None, columns=None, limit=None):
    handler = OnaAPIHandler(api_token)
    filters = json.loads(filters_json) if filters_json else None
    return handler.query_filtered_data(form_id, filters=filters, columns=columns, limit=limit)

@st.cache_data(ttl=300)
def get_cached_multi_forms(api_token, form_ids, filters_json=None, forms_metadata_json=None):
    handler = OnaAPIHandler(api_token)
    filters = json.loads(filters_json) if filters_json else None
    forms_metadata = json.loads(forms_metadata_json) if forms_metadata_json else None
    return handler.query_multi_forms(form_ids, filters=filters, forms_metadata=forms_metadata)

@st.cache_data(ttl=600, show_spinner=False)
def get_csv_media_links(api_token, form_id, record_id):
    """
    Fetches a single record in CSV format to extract pre-constructed media links from ONA.
    This is ultra-efficient as it only requests one row.
    """
    import requests # Defensive import inside cached function
    if not record_id: return {}
    headers = {"Authorization": f"Token {api_token}"}
    # ONA constructs full URLs in CSV exports. We query only the specific record.
    url = f"https://api.ona.io/api/v1/data/{form_id}.csv?query={{\"_id\":{record_id}}}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            csv_text = resp.text
            # Debug: Save to file for user inspection
            if not os.path.exists("outputs"): os.makedirs("outputs")
            with open("outputs/last_media_links_debug.csv", "w", encoding="utf-8") as f:
                f.write(csv_text)
            
            df = pd.read_csv(StringIO(csv_text))
            if not df.empty:
                # Return a map of column_name -> URL for all cells containing 'http'
                record = df.iloc[0]
                links = {col: str(val) for col, val in record.items() if str(val).startswith("http")}
                return links
    except Exception as e:
        st.error(f"Error recuperando enlaces CSV: {e}")
    return {}

# ==========================================
# 1. Configuración & Estilos Odoo (TRED Edition)
# ==========================================
st.set_page_config(
    page_title="TRED | ERP DocGenerator", 
    layout="wide", 
    page_icon="assets/logo.png",
    initial_sidebar_state="collapsed"
)

# HELPER: Auto-Create Desktop Shortcut
def create_desktop_shortcut():
    try:
        desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        if not os.path.exists(desktop):
            desktop = os.path.join(os.environ['USERPROFILE'], 'OneDrive', 'Desktop')
            
        if not os.path.exists(desktop):
            print("Desktop folder not found. Skipping shortcut creation.")
            return False

        shortcut_path = os.path.join(desktop, "TRED DocGenerator.url")
        
        # Only create if it doesn't exist to avoid overwriting user changes
        if not os.path.exists(shortcut_path):
            cwd = os.getcwd()
            icon_path = os.path.join(cwd, "assets", "logo.ico")
            
            content = f"""[InternetShortcut]
URL=http://localhost:8501
IconIndex=0
IconFile={icon_path}
"""
            with open(shortcut_path, "w") as f:
                f.write(content)
            print(f"Shortcut created at {shortcut_path}")
            return True
    except Exception as e:
        print(f"Error creating shortcut: {e}")
        return False
    return False

# Run shortcut creation once on startup
if 'shortcut_checked' not in st.session_state:
    create_desktop_shortcut()
    st.session_state['shortcut_checked'] = True

# Helper for Base64 Image
import base64
def get_img_as_base64(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

logo_path = "assets/logo.png"
logo_base64 = ""
if os.path.exists(logo_path):
    logo_base64 = get_img_as_base64(logo_path)

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"]  {{
        font-family: 'Inter', sans-serif;
        color: #374151 !important;
    }}
    :root {{
        --odoo-purple: #714B67;
        --odoo-teal: #017E84;
        --tred-pink: #E91E63;
        --tred-purple-soft: #F3E5F5;
        --bg-light: #F9F9F9;
        --card-bg: #FFFFFF;
        --text-color: #374151;
    }}
    
    /* Top Right Logo Injection */
    .top-right-logo {{
        position: fixed;
        top: 10px; /* Adjust vertical center in header */
        right: 20px;
        z-index: 99999;
        height: 40px; /* Adjust to fit header height */
    }}

    .stApp {{ 
        background-color: var(--bg-light); 
        color: var(--text-color);
    }}
    p, li, div, span {{
        color: var(--text-color);
    }}
    h1, h2, h3, h4, h5, h6 {{ 
        color: var(--odoo-purple) !important; 
        font-weight: 600 !important; 
    }}
    
    /* Header decoration override */
    div[data-testid="stDecoration"] {{
        background-image: none;
        background-color: transparent;
        height: 0px;
    }}
    header[data-testid="stHeader"] {{
        border-bottom: 2px solid transparent;
        border-image: linear-gradient(90deg, #9C27B0, #E91E63);
        border-image-slice: 1;
        background-color: transparent;
    }}
    /* EXPLICITLY HIDE DEPLOY BUTTON & TOOLBAR */
    .stDeployButton, div[data-testid="stToolbar"] {{ display: none !important; }}

    /* Menu Styling */
    div[role="radiogroup"] > label > div:first-child {{ display: none; }}
    
    div[role="radiogroup"] label {{
        background-color: white;
        padding: 6px 12px;
        margin-bottom: 4px;
        border-radius: 4px;
        border: 1px solid #E5E7EB;
        cursor: pointer;
        transition: all 0.2s;
        text-align: center;
        font-weight: 500;
        color: #4B5563 !important;
        font-size: 0.9rem;
    }}
    div[role="radiogroup"] label:hover {{
        border-color: #9C27B0;
        background-color: var(--tred-purple-soft);
        color: #9C27B0 !important;
    }}
    div[role="radiogroup"] label[data-checked="true"] {{
        background-color: var(--tred-purple-soft) !important;
        border: 1px solid #9C27B0;
        color: #9C27B0 !important;
        font-weight: 700;
        box-shadow: 0 1px 2px rgba(156, 39, 176, 0.15);
    }}
    
    .stButton button {{ 
        background-color: var(--odoo-teal) !important; 
        color: white !important; 
        border: none !important;
        border-radius: 4px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        padding: 0.4rem 1rem;
    }}
    /* Custom Sidebar Toggle */
    [data-testid="stSidebarCollapsedControl"] {{
        position: fixed;
        top: 0px;
        left: 0;
        z-index: 1000000;
        background: linear-gradient(90deg, #9C27B0, #E91E63);
        border-radius: 0 0 12px 0; /* Corner shape */
        color: white !important;
        border: none;
        padding: 4px 12px;
        min-width: auto;
        display: flex;
        align-items: center;
        gap: 6px;
        height: 32px; /* Slim height */
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        transition: all 0.2s;
    }}
    [data-testid="stSidebarCollapsedControl"]:hover {{
        padding-right: 16px;
        border-radius: 0 0 20px 0; /* Animation */
    }}
    
    [data-testid="stSidebarCollapsedControl"]::after {{
        content: "MENÚ";
        font-weight: 600;
        font-size: 0.8rem;
        color: white;
        letter-spacing: 0.5px;
    }}
    [data-testid="stSidebarCollapsedControl"] svg {{
        fill: white !important;
        color: white !important;
        width: 1rem;
        height: 1rem;
    }}
</style>
<!-- Injected Logo -->
<img src="data:image/png;base64,{logo_base64}" class="top-right-logo" alt="TRED Logo">
""", unsafe_allow_html=True)

# ==========================================
# 2. Funciones de Carga y Configuración
# ==========================================
# === UTILS: MEDIA HANDLER ===
@st.cache_data(show_spinner=False)
def fetch_ona_image(filename, api_token, form_id=None, attachments_list=None):
    """
    Downloads an image from ONA.io using the API token.
    Improved version with basename matching and multiple mapping strategies.
    """
    if not filename or not isinstance(filename, str) or str(filename).lower() == 'nan':
        return None
    
    import os
    base_name = os.path.basename(filename)
    urls = []
    
    # Pattern -1: Check direct CSV links from session (Highest priority & accuracy)
    if 'current_media_links' in st.session_state:
        # Try to find a link that matches this filename
        for col, link in st.session_state['current_media_links'].items():
            if filename in link or base_name in link:
                urls.append(link)
                break

    # Pattern 0: Check attachments list (Reliable for private forms)
    if attachments_list:
        for attachment in attachments_list:
            att_filename = attachment.get('filename', '')
            att_name = attachment.get('name', '')
            
            # Match by full path or just basename
            if filename in att_filename or base_name in os.path.basename(att_filename) or base_name == att_name:
                dl_url = attachment.get('download_url')
                if dl_url:
                    urls.append(dl_url if dl_url.startswith('http') else f"https://api.ona.io{dl_url}")
                break

    # Pattern 1: Direct URL if provided by CSV/User
    if filename.startswith("http"):
        urls.append(filename)
    
    # Pattern 2: Global files API logic
    urls.append(f"https://api.ona.io/api/v1/files/{filename}")
    
    # Pattern 3: Data-specific endpoint
    if form_id:
        urls.append(f"https://api.ona.io/api/v1/data/{form_id}/{filename}")
    
    # Prioritize: If we found a High Confidence link (CSV or exact match), try ONLY that first
    # This prevents trying 3 broken URLs and waiting for timeouts.
    
    import requests # Defensive import inside cached function
    
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

def render_calendar_selector(available_dates, key_prefix="cal_sel"):
    """
    Renders a clickable calendar using Streamlit columns and buttons.
    Returns the selected date (datetime.date) or None.
    """
    import calendar
    from datetime import datetime
    
    # CSS for compact calendar
    st.markdown("""
        <style>
            .stButton > button {
                padding: 2px 5px !important;
                font-size: 0.8rem !important;
                min-height: 25px !important;
            }
            .cal-header {
                text-align: center;
                font-weight: bold;
                color: #714B67;
                padding: 2px;
                font-size: 0.9rem;
            }
        </style>
    """, unsafe_allow_html=True)

    # State for navigation
    month_key = f"{key_prefix}_m"
    year_key = f"{key_prefix}_y"
    selected_key = f"{key_prefix}_selected"
    
    if month_key not in st.session_state:
        # Default to latest available date or today
        if len(available_dates) > 0:
            target = max(available_dates)
            st.session_state[month_key] = target.month
            st.session_state[year_key] = target.year
        else:
            now = datetime.now()
            st.session_state[month_key] = now.month
            st.session_state[year_key] = now.year
            
    curr_m = st.session_state[month_key]
    curr_y = st.session_state[year_key]
    
    # Navigation Header
    c_p, c_t, c_n = st.columns([1, 3, 1])
    month_names = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                   "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    with c_p:
        if st.button("←", key=f"{key_prefix}_btn_p"):
            if st.session_state[month_key] == 1:
                st.session_state[month_key] = 12
                st.session_state[year_key] -= 1
            else:
                st.session_state[month_key] -= 1
            st.rerun()
    with c_t:
        st.markdown(f"<div class='cal-header'>{month_names[curr_m-1]} {curr_y}</div>", unsafe_allow_html=True)
    with c_n:
        if st.button("→", key=f"{key_prefix}_btn_n"):
            if st.session_state[month_key] == 12:
                st.session_state[month_key] = 1
                st.session_state[year_key] += 1
            else:
                st.session_state[month_key] += 1
            st.rerun()

    # Grid Header
    cols = st.columns(7)
    days_short = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]
    for i, d in enumerate(days_short):
        cols[i].markdown(f"<center style='font-size:0.7rem; color:#888;'>{d}</center>", unsafe_allow_html=True)

    # Calendar Grid
    cal = calendar.monthcalendar(curr_y, curr_m)
    for week in cal:
        w_cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                continue
            
            # Check if this day has records
            is_available = any(d.day == day and d.month == curr_m and d.year == curr_y for d in available_dates)
            
            btn_label = f"{day}"
            if is_available:
                btn_label = f"{day} 🔴"
                
            if w_cols[i].button(btn_label, key=f"{key_prefix}_day_{day}_{curr_m}_{curr_y}", use_container_width=True):
                from datetime import date
                st.session_state[selected_key] = date(curr_y, curr_m, day)
                st.rerun()

    return st.session_state.get(selected_key)

# --- CONFIGURACIÓN DE PÁGINA ---
CONFIG_FILE = "config.json"
MAPPING_FILE = "mapping.yaml"

# Simple encryption for token storage
def _get_machine_key():
    """Generate a simple key from machine-specific data"""
    import platform
    key_base = f"{platform.node()}{os.getenv('USERNAME', 'default')}"
    return base64.b64encode(key_base.encode())[:32]

def encrypt_token(token):
    """Simple XOR-based encryption for token"""
    if not token:
        return ""
    key = _get_machine_key()
    encrypted = bytearray()
    for i, char in enumerate(token.encode()):
        encrypted.append(char ^ key[i % len(key)])
    return base64.b64encode(bytes(encrypted)).decode()

def decrypt_token(encrypted_token):
    """Decrypt token"""
    if not encrypted_token:
        return ""
    try:
        key = _get_machine_key()
        encrypted = base64.b64decode(encrypted_token.encode())
        decrypted = bytearray()
        for i, byte in enumerate(encrypted):
            decrypted.append(byte ^ key[i % len(key)])
        return bytes(decrypted).decode()
    except:
        # If decryption fails, assume it's plain text (migration)
        return encrypted_token

def load_config():
    config = {"ona_api_token": "", "selected_forms": [], "last_sync_time": 0}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Decrypt token if present
            if 'ona_api_token_encrypted' in config:
                config['ona_api_token'] = decrypt_token(config['ona_api_token_encrypted'])
            elif 'ona_api_token' in config and config['ona_api_token']:
                # Migrate plain text token to encrypted
                plain_token = config['ona_api_token']
                config['ona_api_token_encrypted'] = encrypt_token(plain_token)
                del config['ona_api_token']
                # Save encrypted version
                with open(CONFIG_FILE, 'w') as fw:
                    json.dump(config, fw, indent=2)
                config['ona_api_token'] = plain_token
                
    # Override with st.secrets for Cloud deployments
    try:
        if "ona_api_token" in st.secrets:
            config['ona_api_token'] = st.secrets["ona_api_token"]
        if "ona_form_id" in st.secrets:
            config['ona_form_id'] = st.secrets["ona_form_id"]
    except Exception:
        pass
        
    return config

def save_config(config):
    # Encrypt token before saving
    save_config_data = config.copy()
    if 'ona_api_token' in save_config_data and save_config_data['ona_api_token']:
        save_config_data['ona_api_token_encrypted'] = encrypt_token(save_config_data['ona_api_token'])
        del save_config_data['ona_api_token']
    with open(CONFIG_FILE, 'w') as f:
        json.dump(save_config_data, f, indent=2)

def load_mapping():
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, 'r', encoding='utf-8') as f: return yaml.safe_load(f)
    return {}

app_config = load_config()
mapping_config = load_mapping()
report_types = mapping_config.get('report_types', {})
grouping_config = mapping_config.get('config', {})

# Initialize Report Engine
engine = ReportEngine(mapping_config='mapping.yaml', catalog_data='catalogo_equipos.json', auth_token=app_config.get('ona_api_token'))
from history_manager import HistoryManager
hist_mgr = HistoryManager()

# --- Auto-Connect Logic on Startup ---
if app_config.get("ona_api_token") and 'forms_cache' not in st.session_state:
    try:
        handler = OnaAPIHandler(app_config.get("ona_api_token"))
        # Using st.spinner while loading in the background
        forms_list = handler.get_user_forms()
        if forms_list:
            st.session_state['forms_cache'] = {f['formid']: f['title'] for f in forms_list}
            # Also try to load column mapping for the primary form if configured
            if app_config.get("ona_form_id") and 'mapping_sample_columns' not in st.session_state:
                sample_df = handler.query_filtered_data(form_id=app_config.get("ona_form_id"), limit=1)
                if not sample_df.empty:
                    st.session_state['mapping_sample_columns'] = list(sample_df.columns)
    except Exception as e:
        st.sidebar.error(f"Error al conectar automáticamente con ONA: {e}")

# ==========================================
# 3. Sidebar Navigation
# ==========================================

with st.sidebar:
    st.markdown("### 🏢 Menú Operativo")
    
    # Navigation
    # Use session state to control selection if needed (e.g. from History load)
    valid_nav_options = ["Dashboard BI", "Analítica Global", "Historial Generado", "Gestión de Catálogo", "Propuesta técnica", "Ingeniería (Memorias)", "Obra (Bitácoras)", "Configuración"]
    
    if 'main_nav_radio' not in st.session_state or st.session_state['main_nav_radio'] not in valid_nav_options:
        st.session_state['main_nav_radio'] = "Dashboard BI"

    selected_module = st.radio(
        "Navegación", 
        valid_nav_options,
        index=0, # This index is ignored if key is present and in state, but good for fallback
        key="main_nav_radio",
        label_visibility="collapsed"
    )

# ==========================================
# 4. Wizards & Views - REFACTORED FOR REAL-TIME QUERIES
# ==========================================
# --- Custom CSS for Premium UI ---
st.markdown("""
<style>
    .report-card {
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .report-group-header {
        color: #714B67;
        border-bottom: 2px solid #714B67;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        font-weight: 700;
    }
    .repeat-item-card {
        background-color: white;
        border-left: 4px solid #714B67;
        padding: 0.8rem;
        margin-bottom: 0.6rem;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stImage > img {
        object-fit: cover;
        border-radius: 6px;
        max-height: 220px;
        width: 100%;
    }
    .field-label {
        color: #6B7280;
        font-size: 0.65rem;
        font-weight: 600;
        margin-bottom: 0;
        line-height: 1.1;
    }
    .field-value {
        color: #111827;
        font-weight: 500;
        margin-bottom: 0.3rem;
        font-size: 0.8rem;
        line-height: 1.2;
    }
</style>
""", unsafe_allow_html=True)



def find_value_in_record(record, target_name):
    """
    Helper to find a value in a record where keys might be prefixed (e.g. 'group/field').
    """
    # Exact match
    if target_name in record:
        return record[target_name]
    
    # Try match by suffix (handling ONA nested keys)
    for k, v in record.items():
        if k == target_name or k.endswith(f"/{target_name}"):
            return v
    return None

def inject_nested_value(data_dict, path, value):
    """
    Helper to inject a value into a nested dict/list structure based on a path like 'group[0]/field'.
    """
    parts = path.replace('[', '/[').split('/')
    curr = data_dict
    for i, part in enumerate(parts):
        if part.startswith('['):
            idx = int(part[1:-1])
            # Ensure list is long enough
            while len(curr) <= idx:
                curr.append({})
            if i == len(parts) - 1:
                curr[idx] = value
            else:
                curr = curr[idx]
        else:
            if i == len(parts) - 1:
                curr[part] = value
            else:
                if part not in curr:
                    # Look ahead to see if next part is an index
                    if i + 1 < len(parts) and parts[i+1].startswith('['):
                        curr[part] = []
                    else:
                        curr[part] = {}
                curr = curr[part]

def item_has_data(schema_item, record):
    """
    Recursively checks if a schema item (group/repeat) has any non-empty data in the provided record.
    """
    s_type = schema_item.get('type')
    name = schema_item.get('name')
    
    # Base case: Simple fields
    if s_type not in ['group', 'repeat']:
        val = find_value_in_record(record, name)
        return bool(val is not None and str(val).strip() != "" and str(val).lower() != 'nan')
    
    # Recursive case: Group/Repeat
    if s_type == 'repeat':
        items = find_value_in_record(record, name)
        if isinstance(items, list) and items:
            # Check if ANY item in repeat has data matching the schema children
            for item in items:
                for child in schema_item.get('children', []):
                    if item_has_data(child, item):
                        return True
        return False
        
    elif s_type == 'group':
        # Check if ANY child in group has data
        for child in schema_item.get('children', []):
            # If child is a group/repeat, recurse. If simple, check value.
            if item_has_data(child, record):
                return True
        return False
        
    return False

def display_record_details(record, schema_children, form_id, level=0, root_record=None, interactive=False, item_path=""):
    """
    Renders ONA record data in a multi-column 'canvas' layout (2-3 items per row).
    root_record is maintained across recursion to provide access to _attachments.
    If interactive=True, it allows selecting equipment models from catalog.
    """
    if root_record is None:
        root_record = record
        
    # Collect flat fields to arrange them in columns
    flat_fields = []
    
    cat_manager = CatalogManager() if interactive else None
    
    for child in schema_children:
        child_type = child.get('type')
        name = child.get('name')
        current_path = f"{item_path}/{name}" if item_path else name
        if child_type == 'group':
            # Skip empty groups
            if not item_has_data(child, record):
                continue

            # Render previous flat fields before starting a new group
            render_field_grid(flat_fields, record, form_id, root_record=root_record)
            flat_fields = []
            
            label = child.get('label', name)
            st.markdown(f"<div class='report-group-header'>{'#' * (level + 1)} 📂 {label}</div>", unsafe_allow_html=True)
            display_record_details(record, child.get('children', []), form_id, level + 1, root_record=root_record, interactive=interactive, item_path=current_path)
            
        elif child_type == 'repeat':
            render_field_grid(flat_fields, record, form_id, root_record=root_record)
            flat_fields = []
            
            label = child.get('label', name)
            repeat_data = find_value_in_record(record, name)
            if isinstance(repeat_data, list) and len(repeat_data) > 0:
                st.markdown(f"**🔄 {label} ({len(repeat_data)} ítems)**")
                for i, item in enumerate(repeat_data):
                    item_id_path = f"{current_path}[{i}]"
                    with st.container():
                        st.markdown(f"<div class='repeat-item-card'>", unsafe_allow_html=True)
                        
                        st.markdown(f"**Elemento {i+1}**")
                        
                        # --- INTERACTIVE SELECTION ---
                        if interactive:

                            # Model Selector
                            models = sorted(list(cat_manager.data.keys()))
                            current_key = f"sel_model_{item_id_path}"
                            current_sel = st.session_state.get(current_key)
                            
                            sel_idx = models.index(current_sel) if current_sel in models else None
                            
                            sel_model = st.selectbox(
                                "Seleccionar Modelo de Catálogo:",
                                options=models,
                                index=sel_idx,
                                key=current_key,
                                placeholder="Selecciona un equipo..."
                            )
                            if sel_model:
                                item_info = cat_manager.data[sel_model]
                                st.caption(f"✅ **{item_info.get('marca')}**: {item_info.get('descripcion')}")
                            
                            # Quick Add to Catalog
                            with st.expander("➕ ¿No está el equipo? Agregar al catálogo"):
                                with st.form(f"quick_add_{item_id_path}"):
                                    qq1, qq2 = st.columns(2)
                                    with qq1:
                                        q_id = st.text_input("ID/Modelo", key=f"q_id_{item_id_path}")
                                        q_brand = st.text_input("Marca", key=f"q_brand_{item_id_path}")
                                    with qq2:
                                        q_unit = st.text_input("Unidad", value="Pza", key=f"q_unit_{item_id_path}")
                                    
                                    q_desc = st.text_area("Descripción Técnica para Reporte", key=f"q_desc_{item_id_path}")
                                    if st.form_submit_button("Guardar en Catálogo"):
                                        if q_id and q_brand:
                                            cat_manager.add_or_update_item(q_id, q_brand, q_brand, q_desc, [], unidad=q_unit, costo=0.0)
                                            st.session_state[f"sel_model_{item_id_path}"] = q_id
                                            st.success(f"Añadido: {q_id}")
                                            st.rerun()
                                        else:
                                            st.error("ID y Marca son obligatorios.")

                        display_record_details(item, child.get('children', []), form_id, level + 1, root_record=root_record, interactive=interactive, item_path=item_id_path)
                        st.markdown("</div>", unsafe_allow_html=True)
        else:
            # Check if it has a value before adding to grid
            value = find_value_in_record(record, name)
            if value is not None and str(value).strip() != "" and str(value) != "nan":
                flat_fields.append(child)
                
    # Final flush
    render_field_grid(flat_fields, record, form_id, root_record=root_record)



def render_single_field(child, record, form_id, root_record=None):
    name = child.get('name')
    label = child.get('label', name)
    value = find_value_in_record(record, name)
    child_type = child.get('type')
    
    st.markdown(f"<p class='field-label' style='margin-bottom:0; color:#888; font-size:0.75rem;'>{label}</p>", unsafe_allow_html=True)
    
    if child_type in ['photo', 'image'] or (isinstance(value, str) and value.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4'))):
        api_token = app_config.get('ona_api_token')
        # Use root_record for attachments context
        attachments = (root_record or record).get('_attachments', [])
        
        # Support comma separated image lists from grouped reports
        val_list = [v.strip() for v in str(value).split(',')] if value and ',' in str(value) else [value]
        
        for val in val_list:
            if not val or str(val).lower() == 'nan': continue
            img_bytes = fetch_ona_image(val, api_token, form_id, attachments_list=attachments)
            if img_bytes:
                st.image(img_bytes, use_container_width=True) # Full width of the 1/3 column
            else:
                st.warning(f"📎 {val}")
    
    elif child_type == 'geopoint':
        try:
            parts = str(value).split(' ')
            if len(parts) >= 2:
                lat, lon = float(parts[0]), float(parts[1])
                st.markdown(f"<p style='font-size:0.9rem; font-weight:600; margin-top:0;'>📍 `{lat}, {lon}`</p>", unsafe_allow_html=True)
                map_df = pd.DataFrame({'lat': [lat], 'lon': [lon]})
                st.map(map_df, zoom=14, height=200) # Smaller map as requested
        except:
            st.markdown(f"<p style='font-size:0.9rem; font-weight:600; margin-top:0;'>📍 {value}</p>", unsafe_allow_html=True)
    
    else:
        formatted_val = value
        if child_type == 'select one':
            options = child.get('children', [])
            formatted_val = next((opt.get('label') for opt in options if opt.get('name') == str(value)), value)
        elif child_type == 'select all that apply':
            options = child.get('children', [])
            selected_vals = str(value).split(' ')
            labels = [next((opt.get('label') for opt in options if opt.get('name') == s_val), s_val) for s_val in selected_vals]
            formatted_val = ", ".join(labels)
        
        st.markdown(f"<p style='font-size:0.95rem; font-weight:500; margin-top:0; color:#111;'>{formatted_val}</p>", unsafe_allow_html=True)

def render_field_grid(fields, record, form_id, root_record=None):
    """
    Renders fields in a strict 3-column grid to match the Word report layout.
    """
    if not fields: return
    
    # Filter valid fields first
    valid_fields = []
    for f in fields:
        val = find_value_in_record(record, f.get('name'))
        if val is not None and str(val).strip() != "" and str(val).lower() != 'nan':
            valid_fields.append(f)
            
    if not valid_fields: return

    # Batch in 3s
    for i in range(0, len(valid_fields), 3):
        batch = valid_fields[i:i+3]
        cols = st.columns(3)
        for j, field in enumerate(batch):
            with cols[j]:
                # Design: Card-like container
                with st.container():
                    render_single_field(field, record, form_id, root_record=root_record)

def render_wizard(report_key, report_label):
    # Initialize choices_map at function scope to avoid NameError
    choices_map = {}

    """
    Refactored wizard with incremental real-time queries.
    Flow: Form Selection → Query Clients → Query Sites → Generate Report + Detailed View
    """
    st.header(f"📑 {report_label}")
    
    # Check prerequisites
    if 'forms_cache' not in st.session_state:
        st.warning("⚠️ Conecta tu Token en Configuración primero.")
        return
    
    form_opts = st.session_state['forms_cache']
    # Step 1: Form selection (Auto-select if configured)
    report_config = report_types.get(report_key, {})
    forced_id = report_config.get('default_form_id')
    
    default_forms = []
    if forced_id and (forced_id in form_opts or str(forced_id) in form_opts):
        default_forms = [forced_id if forced_id in form_opts else str(forced_id)]
    
    selected_forms_wizard = st.multiselect(
        "1️⃣ Selecciona Formulario(s)",
        options=list(form_opts.keys()),
        format_func=lambda x: form_opts[x],
        default=default_forms,
        key=f"wizard_{report_key}_forms",
        placeholder="Elige uno o más formularios..."
    )
    
    if not selected_forms_wizard:
        st.info("👆 Selecciona al menos un formulario para comenzar.")
        return
        
    # Legacy fallback for variables that expect a single form
    selected_form_wizard = selected_forms_wizard[0]
    # --- DYNAMIC MAPPING LOGIC ---
    handler = OnaAPIHandler(app_config.get('ona_api_token'))
    forms_map = mapping_config.get('forms', {})
    
    # Step 2: Query unique clients across all forms
    with st.spinner("Cargando clientes disponibles..."):
        clientes_set = set()
        for fid in selected_forms_wizard:
            spec_map = forms_map.get(fid, forms_map.get(str(fid), {}))
            col_cli = spec_map.get('column_cliente', grouping_config.get('column_cliente', ''))
            if col_cli:
                c_list = get_cached_unique_values(app_config.get('ona_api_token'), fid, col_cli)
                if c_list: clientes_set.update(c_list)
        clientes_list = sorted(list(clientes_set))
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        prev_client = st.session_state.get(f"wizard_{report_key}_cliente")
        sel_client = st.selectbox(
            "2️⃣ Cliente (Opcional)", 
            options=["-- Todos los Clientes --"] + clientes_list, 
            index=0, 
            key=f"wizard_{report_key}_cliente"
        )
        
        actual_client = sel_client if sel_client != "-- Todos los Clientes --" else None
        
        if sel_client != prev_client:
            if 'current_media_links' in st.session_state: del st.session_state['current_media_links']
            if 'history_quote_rows' in st.session_state: del st.session_state['history_quote_rows']
    
    # Step 3: Query sites for selected client
    sel_site = None
    with st.spinner(f"Cargando sitios..."):
        sites_set = set()
        for fid in selected_forms_wizard:
            spec_map = forms_map.get(fid, forms_map.get(str(fid), {}))
            col_cli = spec_map.get('column_cliente', grouping_config.get('column_cliente', ''))
            col_sit = spec_map.get('column_sitio', grouping_config.get('column_sitio', ''))
            if col_sit:
                filter_dict_sites = {col_cli: actual_client} if actual_client and col_cli else {}
                s_list = get_cached_unique_values(
                    app_config.get('ona_api_token'),
                    fid,
                    col_sit,
                    filters_json=safe_json_dumps(filter_dict_sites) if filter_dict_sites else None
                )
                if s_list: sites_set.update(s_list)
        sites_list = sorted(list(sites_set))
        
    if sites_list:
        with col2:
            prev_site = st.session_state.get(f"wizard_{report_key}_sitio")
            sel_site = st.selectbox(
                "3️⃣ Sitio (Opcional)",
                options=["-- Todos los Sitios --"] + sites_list,
                index=0,
                key=f"wizard_{report_key}_sitio"
            )
            actual_site = sel_site if sel_site != "-- Todos los Sitios --" else None
            
            if sel_site != prev_site:
                if 'current_media_links' in st.session_state: del st.session_state['current_media_links']
                if 'history_quote_rows' in st.session_state: del st.session_state['history_quote_rows']
    else:
        with col2:
            actual_site = None
            st.info("Sin sitios para este cliente.")
    
    # Step 4: Instance Selection (Date)
    # We proceed unconditionally since site is optional
    with st.spinner(f"Buscando historial..."):
        all_instances = []
        for fid in selected_forms_wizard:
            spec_map = forms_map.get(fid, forms_map.get(str(fid), {}))
            col_cli = spec_map.get('column_cliente', grouping_config.get('column_cliente', ''))
            col_sit = spec_map.get('column_sitio', grouping_config.get('column_sitio', ''))
            
            filter_dict_inst = {}
            if actual_site and col_sit: filter_dict_inst[col_sit] = actual_site
            if actual_client and col_cli: filter_dict_inst[col_cli] = actual_client
            
            cols_to_fetch = ['_submission_time', '_id']
            if col_cli: cols_to_fetch.append(col_cli)
            if col_sit: cols_to_fetch.append(col_sit)
            cols_to_fetch.append('_submitted_by')
            
            df_fid = get_cached_filtered_data(
                api_token=app_config.get('ona_api_token'),
                form_id=fid,
                filters_json=safe_json_dumps(filter_dict_inst),
                columns=cols_to_fetch
            )
            
            if not df_fid.empty:
                df_fid['form_id'] = fid
                df_fid['Formulario'] = form_opts[fid]
                if col_cli and col_cli in df_fid.columns:
                    df_fid['col_cliente'] = df_fid[col_cli]
                if col_sit and col_sit in df_fid.columns:
                    df_fid['col_sitio'] = df_fid[col_sit]
                all_instances.append(df_fid)
                
        if all_instances:
            instances_df = pd.concat(all_instances, ignore_index=True)
        else:
            instances_df = pd.DataFrame()
    
    if not instances_df.empty:
        instances_df['_datetime'] = pd.to_datetime(instances_df['_submission_time'])
        instances_df['_date_str'] = instances_df['_datetime'].dt.strftime('%d/%m/%Y')
        instances_df['_time_str'] = instances_df['_datetime'].dt.strftime('%H:%M:%S')
        
        available_dates = instances_df['_datetime'].dt.date.unique()
        
        with col3:
            st.markdown("**4️⃣ Selección de Registros**")
            
            selected_key = f"wiz_{report_key}_selected"
            selected_date = st.session_state.get(selected_key)
            
            if report_key == 'bitacora_obra':
                instances_df = instances_df.sort_values('_datetime', ascending=False)
                st.markdown("**Selecciona los Registros a agrupar en la tabla:**")
                
                display_cols = ['Formulario', '_date_str', '_time_str']
                final_display_cols = ['Formulario', 'Fecha', 'Hora']
                
                if 'col_sitio' in instances_df.columns:
                    display_cols.append('col_sitio')
                    final_display_cols.append('Sitio')
                if 'col_cliente' in instances_df.columns:
                    display_cols.append('col_cliente')
                    final_display_cols.append('Cliente')
                if '_submitted_by' in instances_df.columns:
                    display_cols.append('_submitted_by')
                    final_display_cols.append('Técnico')
                    
                display_df = instances_df[display_cols].copy()
                display_df.columns = final_display_cols
                
                event = st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    selection_mode="multi-row",
                    on_select="rerun",
                    key=f"wizard_{report_key}_table"
                )
                
                selected_rows = event.selection.rows
                
                if not selected_rows:
                    st.info("💡 Haz clic en la casilla izquierda de las filas de la tabla superior para seleccionar los formularios que quieres unir.")
                    return
                
                # Format for sel_ids to track form_id and instance_id
                sel_ids = [str(instances_df.iloc[idx]['_id']) for idx in selected_rows]
                sel_instances = [{
                    'form_id': instances_df.iloc[idx]['form_id'], 
                    '_id': instances_df.iloc[idx]['_id'],
                    'client': instances_df.iloc[idx]['col_cliente'] if 'col_cliente' in instances_df.columns else 'N/A',
                    'site': instances_df.iloc[idx]['col_sitio'] if 'col_sitio' in instances_df.columns else 'N/A',
                    'form_name': instances_df.iloc[idx]['Formulario']
                } for idx in selected_rows]
            else:
                if not selected_date:
                    with st.popover("📅 Abrir Calendario de Levantamientos", use_container_width=True):
                        selected_date = render_calendar_selector(available_dates, key_prefix=f"wiz_{report_key}")
                
                if selected_date:
                    day_instances = instances_df[instances_df['_datetime'].dt.date == selected_date]
                    if not day_instances.empty:
                        st.markdown(f"📅 **Fecha:** `{selected_date.strftime('%d/%m/%Y')}`")
                        day_instances = day_instances.sort_values('_datetime', ascending=False)
                        
                        if len(day_instances) > 1:
                            sel_instance_id = st.selectbox(
                                "Selecciona la Hora / Registro:",
                                options=day_instances['_id'].tolist(),
                                format_func=lambda x: f"{day_instances[day_instances['_id'] == x]['Formulario'].values[0]} - {day_instances[day_instances['_id'] == x]['_time_str'].values[0]}",
                                key=f"wizard_{report_key}_instance",
                                index=0
                            )
                        else:
                            sel_instance_id = day_instances.iloc[0]['_id']
                            st.info(f"🕒 {day_instances.iloc[0]['Formulario']} - {day_instances.iloc[0]['_time_str']}")
                        
                        if st.button("🔄 Cambiar Fecha", key=f"reset_cal_{report_key}"):
                            if selected_key in st.session_state:
                                del st.session_state[selected_key]
                            st.rerun()
                            
                        sel_ids = [str(sel_instance_id)]
                        match = day_instances[day_instances['_id'] == sel_instance_id]
                        sel_instances = [{
                            'form_id': match.iloc[0]['form_id'], 
                            '_id': match.iloc[0]['_id'],
                            'client': match.iloc[0]['col_cliente'] if 'col_cliente' in match.columns else 'N/A',
                            'site': match.iloc[0]['col_sitio'] if 'col_sitio' in match.columns else 'N/A',
                            'form_name': match.iloc[0]['Formulario']
                        }]
                    else:
                        st.warning("No hay registros para esta fecha.")
                        if st.button("Volver al Calendario"):
                            if selected_key in st.session_state:
                                del st.session_state[selected_key]
                            st.rerun()
                else:
                    st.info("💡 Por favor, selecciona un día en el calendario.")
                    return
        
        # Fetch the specific record data for the selected instance
        if 'sel_instances' in locals() and sel_instances:
                # sel_ids and sel_instances are already correctly populated for both Bitacora and Propuesta
                
                # FLASH DOWNLOAD: Fetch CSV media links side-car
                if 'current_media_links' not in st.session_state or st.session_state.get('last_instance_id') != str(sel_ids):
                    with st.spinner("⏳ Sincronizando enlaces de medios (CSV Flash)..."):
                        keys_to_del = [k for k in st.session_state.keys() if k.startswith("sel_model_")]
                        for k in keys_to_del: del st.session_state[k]
                        
                        if not st.session_state.get('editing_history_id'):
                            if 'extra_items' in st.session_state: st.session_state['extra_items'] = []
                        
                        all_links = {}
                        for inst in sel_instances:
                            links = get_csv_media_links(app_config.get('ona_api_token'), inst['form_id'], inst['_id'])
                            all_links.update(links)
                        st.session_state['current_media_links'] = all_links
                        st.session_state['last_instance_id'] = str(sel_ids)

                with st.spinner("Cargando registro(s) seleccionado(s)..."):
                    instances_data = []
                    has_data = False
                    for inst in reversed(sel_instances): 
                        filtered = get_cached_filtered_data(
                            api_token=app_config.get('ona_api_token'),
                            form_id=inst['form_id'],
                            filters_json=safe_json_dumps({'_id': inst['_id']})
                        )
                        if not filtered.empty:
                            has_data = True
                            r_dict = filtered.iloc[0].to_dict()
                            
                            # Get the schema for this specific form
                            inst_schema = handler.get_form_schema(inst['form_id'])
                            
                            instances_data.append({
                                'record_dict': r_dict,
                                'schema': inst_schema,
                                'form_name': inst.get('form_name', 'Formulario'),
                                'date_str': r_dict.get('_submission_time', '').split('T')[0],
                                'form_id': inst['form_id']
                            })
                            
                    if has_data:
                        # Use the oldest selected record as the header
                        header_record = instances_data[0]['record_dict'].copy()
                        
                        true_client = sel_client
                        if true_client == "-- Todos los Clientes --":
                            true_client = sel_instances[-1].get('client', 'N/A')
                        
                        true_site = sel_site
                        if true_site == "-- Todos los Sitios --":
                            true_site = sel_instances[-1].get('site', 'N/A')
                            
                        # Save true client and site in session state
                        st.session_state['true_client'] = true_client
                        st.session_state['true_site'] = true_site
                        
                        st.session_state['instances_data'] = instances_data
                        
                        record_dict = header_record
                    else:
                        record_dict = {}
        # END OF sel_instances BLOCK
        else:
            return
    else:
        st.error("No se encontraron registros para este sitio.")
        has_data = False
    
    if 'has_data' in locals() and has_data and record_dict:
        
        # --- 1. DATA COLLECTION & CATALOG OPS ---
        cat_manager = CatalogManager()
        
        # Metadata Wizard (Used for both Propuesta and Bitacora)
        if report_key in ["propuesta_tecnica", "bitacora_obra"]:
            with st.expander("📝 Datos del Documento (Asistente de Impresión)", expanded=True):
                    # Manual Project Selection
                    # Load saved projects
                    saved_projects = cat_manager.projects
                    proj_options = ["-- Cargar desde Catálogo --"] + sorted(list(saved_projects.keys()))
                    
                    selected_proj_id = st.selectbox("Cargar Datos de Proyecto Guardado (Opcional)", proj_options)
                    
                    # Defaults
                    if selected_proj_id != "-- Cargar desde Catálogo --":
                        p_data = saved_projects[selected_proj_id]
                        def_proj_id = selected_proj_id
                        def_desc = p_data.get('descripcion_breve', "")
                        def_scope = "\n".join(p_data.get('alcance', []))
                        def_conds = "\n".join(p_data.get('condiciones_comerciales', []))
                    else:
                        def_proj_id = ""
                        def_desc = ""
                        def_scope = ""
                        def_conds = "50% anticipo, 50% contra entrega."

                    # LOOK FOR HISTORY PRELOAD
                    preload = st.session_state.get('history_preload_texts', {})
                    if preload:
                        # If we loaded from history, use those values primarily
                        def_proj_id = preload.get('proyecto_id', def_proj_id)
                        def_desc = preload.get('descripcion_breve', def_desc)
                        def_scope = preload.get('alcance_proyecto', def_scope)
                        def_conds = preload.get('condiciones_comerciales', def_conds)
                        # Clear it so it doesn't stick forever? Maybe not yet.

                    c_w1, c_w2 = st.columns(2)
                    with c_w1:
                        project_name = st.text_input("Nombre/ID del Proyecto", value=def_proj_id, placeholder="Ej: Seguridad Perimetral - San Luis")
                        brief_desc = st.text_area("Descripción Breve del Proyecto", value=def_desc, placeholder="Ej: Instalación de 4 cámaras con almacenamiento...")
                    with c_w2:
                        alcance = st.text_area("Alcance del Proyecto (Listado)", value=def_scope, placeholder="• Instalación\n• Configuración\n• Pruebas")
                        comercial_cond = st.text_area("Condiciones Comerciales", value=def_conds)
                    
                    issuer_name = st.text_input("Firma de quien emite", value=preload.get('firma_emisor', ""), placeholder="Nombre del responsable")
                    
                    record_dict.update({
                        'proyecto_id': project_name,
                        'descripcion_breve': brief_desc,
                        'alcance_proyecto': alcance,
                        'condiciones_comerciales': comercial_cond,
                        'firma_emisor': issuer_name
                    })

            # Calculate Quote Rows
            quote_rows = []
            
            # Check History Override
            if report_key == "propuesta_tecnica" and st.session_state.get('editing_history_id') and 'history_quote_rows' in st.session_state:
                 quote_rows = st.session_state['history_quote_rows']
                 # We skip fresh calculation to preserve the saved state exactly.
            
            elif report_key == "propuesta_tecnica":
                # FRESH CALCULATION
                selected_counts = {}
                for key, val in st.session_state.items():
                    if key.startswith("sel_model_") and val:
                         # key format: sel_model_{ona_uuid}
                         ona_uuid = key.replace("sel_model_", "")
                         model_id_val = val # e.g. "AXIS-P1467"
                         
                         if model_id_val != "-- Seleccionar --":
                             if model_id_val in selected_counts:
                                 selected_counts[model_id_val] += 1
                             else:
                                 selected_counts[model_id_val] = 1
                
                # Build rows from counts
                for mod_id, count in selected_counts.items():
                    info = cat_manager.data.get(mod_id, {})
                    desc = info.get("descripcion", mod_id)
                    cost = info.get("costo_unitario", 0.0)
                    unit = info.get("unidad_medida", "Pza")
                    
                    subtotal = count * cost
                    
                    quote_rows.append({
                        "CANT": count,
                        "DESCRIPCIÓN": desc, # Short desc for table
                        "C.U MXN": f"${cost:,.2f}",
                        "C.T MXN": f"${subtotal:,.2f}",
                        # Hidden "Medida" for internal use if needed, but not for table display
                        # "Medida": unit 
                    })

                # Append Extra Items
                for item in st.session_state.get('extra_items', []):
                     q = float(item.get('qty', 0))
                     c = float(item.get('cost', 0))
                     sub = q * c
                     quote_rows.append({
                        "CANT": int(q) if q.is_integer() else q,
                        "DESCRIPCIÓN": item.get('desc', 'Sin descripción'),
                        "C.U MXN": f"${c:,.2f}",
                        "C.T MXN": f"${sub:,.2f}"
                    })

            # Display Quote Table (HIDDEN AS REQUESTED)
            # if quote_rows:
            #     st.markdown("### 💰 Tabla de Cotización (Previsualización)")
            #     df_quote = pd.DataFrame(quote_rows)
            #     st.table(df_quote)
            #     
            #     # Calculate Totals for UI Display
            #     total_sub = 0.0
            #     for row in quote_rows:
            #         try:
            #             val = float(str(row["C.T MXN"]).replace("$", "").replace(",", ""))
            #             total_sub += val
            #         except: pass
            #     
            #     iva = total_sub * 0.16
            #     total_final = total_sub + iva
            #     
            #     c_t1, c_t2, c_t3 = st.columns(3)
            #     c_t1.metric("Subtotal", f"${total_sub:,.2f}")
            #     c_t2.metric("IVA 16%", f"${iva:,.2f}")
            #     c_t3.metric("TOTAL", f"${total_final:,.2f}")
            # --- 2. ACTION BUTTONS & CANVAS ---
            with st.spinner("Cargando estructura del reporte..."):
                schema = handler.get_form_schema(selected_form_wizard)
                
                # Build choices_map for label resolution
                if schema:
                    for child in schema.get('children', []):
                         # If it's a select field and has embedded choices (xlsform converted)
                        if child.get('type', '').startswith('select_') and 'children' in child:
                             list_name = child.get('select_from_list_name', child.get('name'))
                             # Map internal value -> label
                             choices_map[list_name] = {opt['name']: opt['label'] for opt in child.get('children', []) if 'name' in opt}
            
            st.divider()
            c_header, c_btn = st.columns([4, 1])
            with c_header:
                st.markdown(f"## 📋 Vista Previa de {report_label}")
            with c_btn:
                # Use session state to handle the generate -> download flow
                gen_key = f"gen_state_{report_key}_{sel_site}"
                
                # Dynamic Button Label
                is_editing_history = st.session_state.get('editing_history_id') is not None
                btn_label_wizard = "💾 Actualizar y Regenerar" if is_editing_history else "🚀 Preparar Reporte"
                
                if st.button(btn_label_wizard, type="primary", key=f"wizard_{report_key}_generate", use_container_width=True):
                     with st.spinner("Generando documento..."):
                        # Merge data for Engine
                        if 'current_media_links' in st.session_state:
                            record_dict.update(st.session_state['current_media_links'])
                        record_dict['tabla_cotizacion'] = quote_rows
                        
                        # Map explicit wizard choices to standard keys for the HTML template
                        record_dict['cliente'] = sel_client
                        record_dict['nombre_sitio'] = sel_site
                        
                        # --- AUTO-SAVE HISTORY (Snapshoting) ---
                        try:
                            from history_manager import HistoryManager
                            hist_mgr = HistoryManager()
                            # Snapshot specific data valuable for re-generation
                            snapshot = {
                                'quote_rows': quote_rows,
                                'extra_items': st.session_state.get('extra_items', []),
                                'selectors': {
                                    'form_id': selected_form_wizard,
                                    'client': sel_client,
                                    'site': sel_site,
                                    # We can try to save the date/record selection key too
                                    # 'record_id': record_dict.get('_id') 
                                },
                                'custom_texts': {
                                    'proyecto_id': record_dict.get('proyecto_id'),
                                    'descripcion_breve': record_dict.get('descripcion_breve'),
                                    'alcance_proyecto': record_dict.get('alcance_proyecto'),
                                    'condiciones_comerciales': record_dict.get('condiciones_comerciales'),
                                    'firma_emisor': record_dict.get('firma_emisor')
                                }
                            }
                            # Identify Project from record
                            pid = record_dict.get('proyecto_id') or "Sin Proyecto"
                            
                            # Check if we are updating an existing record
                            update_id = st.session_state.get('editing_history_id')
                            
                            hist_mgr.save_generation_record(
                                project_id=pid,
                                report_type=report_key,
                                site_name=sel_site,
                                ona_record_id=str(record_dict.get('_id', 'unknown')),
                                data_snapshot=snapshot,
                                record_id=update_id  # <--- PASS UPDATE ID
                            )
                            # print("Snapshot saved.")
                        except Exception as e:
                            print(f"History Save Error: {e}")
                            
                        # -----------------------------------------------------------------
                        # RENDER REPORT (DOCX or HTML)
                        # -----------------------------------------------------------------
                        if report_key == 'bitacora_obra':
                            from html_engine import generate_bitacora_html
                            auth_token = app_config.get('ona_api_token')
                            
                            with st.spinner("Descargando imágenes y generando formato web..."):
                                html_out = generate_bitacora_html(record_dict, st.session_state.get('instances_data', []), choices_map, auth_token)
                                st.session_state[gen_key] = html_out.encode('utf-8')
                                st.session_state[f"{gen_key}_is_html"] = True
                        else:
                            # Pass schema for {{DETALLE_TECNICO}} support
                            import tempfile
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                                tmp_path = tmp.name
                            
                            engine.generate_report(record_dict, tmp_path, report_type=report_key, schema=schema, choices_dict=choices_map)
                            
                            with open(tmp_path, "rb") as f:
                                st.session_state[gen_key] = f.read()
                            
                            try:
                                os.remove(tmp_path)
                            except: pass
                            st.session_state[f"{gen_key}_is_html"] = False
                            
                        st.success("✅ Reporte generado y guardado en historial.")
                
                # Show Download / Preview if ready
                if gen_key in st.session_state:
                    is_html = st.session_state.get(f"{gen_key}_is_html", False)
                    if is_html:
                        st.info("💡 **Instrucciones:** Descarga el archivo HTML, haz doble clic para abrirlo en tu navegador y automáticamente aparecerá la ventana para **Guardar como PDF**.")
                        st.download_button(
                            label="📥 Descargar Documento (HTML para Imprimir)",
                            data=st.session_state[gen_key],
                            file_name=f"{report_key}_{sel_site}.html",
                            mime="text/html",
                            key=f"dl_btn_{gen_key}",
                            type="secondary",
                            use_container_width=True
                        )
                        st.divider()
                        st.markdown("### Vista Previa")
                        st.components.v1.html(st.session_state[gen_key].decode('utf-8'), height=800, scrolling=True)
                    else:
                        st.download_button(
                            label="📥 Descargar Propuesta (Word)",
                            data=st.session_state[gen_key],
                            file_name=f"{report_key}_{sel_site}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_btn_{gen_key}",
                            type="secondary",
                            use_container_width=True
                        )

            # --- 3. UI CANVAS (Interactive/Detailed) ---
            if schema and 'children' in schema:
                instances_list = st.session_state.get('instances_data', [])
                if instances_list:
                    for inst in instances_list:
                        st.markdown(f"### ▶ {inst.get('form_name')} - {inst.get('date_str')}")
                        if inst.get('schema') and 'children' in inst['schema']:
                            display_record_details(inst['record_dict'], inst['schema']['children'], selected_form_wizard, interactive=(report_key == "propuesta_tecnica"))
                else:
                    display_record_details(record_dict, schema['children'], selected_form_wizard, interactive=(report_key == "propuesta_tecnica"))
                
                if report_key == "propuesta_tecnica":
                    st.divider()
                    st.markdown("## 💰 Propuesta Económica (Estructura)")
                    with st.expander("➕ Añadir Ítems Extra desde Catálogo", expanded=False):
                        ex_all_models = sorted(list(cat_manager.data.keys()))
                        c_ex1, c_ex2 = st.columns([3, 1])
                        ex_sel = c_ex1.selectbox("Seleccionar:", options=["-- Nuevo/Actualizar --"] + ex_all_models, key="extra_model_sel")
                        ex_qty = c_ex2.number_input("Cantidad", min_value=1, value=1, key="extra_qty_sel")
                        
                        if ex_sel != "-- Nuevo/Actualizar --":
                            if st.button("Añadir a la Propuesta", use_container_width=True):
                                if 'extra_items' not in st.session_state: st.session_state['extra_items'] = []
                                st.session_state['extra_items'].append({'model': ex_sel, 'qty': ex_qty})
                                st.rerun()
                        
                        st.divider()
                        st.markdown("**Gestión Directa de Catálogo**")
                        is_ex_edit = (ex_sel != "-- Nuevo/Actualizar --")
                        ex_edit_data = cat_manager.data.get(ex_sel, {}) if is_ex_edit else {}
                        with st.form("extra_catalog_form"):
                            ce1, ce2 = st.columns([2, 1])
                            with ce1:
                                ex_id = st.text_input("ID Modelo", value=ex_sel if is_ex_edit else "")
                                ex_brand = st.text_input("Marca", value=ex_edit_data.get('marca', ""))
                            with ce2:
                                ex_unit = st.text_input("Unidad", value=ex_edit_data.get('unidad_medida', "Servicio" if not is_ex_edit else "Pza"))
                            ex_rep_desc = st.text_area("Descripción Técnica (Reporte)", value=ex_edit_data.get('descripcion_reporte', ""))
                            ex_specs = st.text_area("Características (Listado)", value="\n".join(ex_edit_data.get('caracteristicas', [])))
                            if st.form_submit_button("💾 Guardar en Catálogo"):
                                if ex_id and ex_brand:
                                    specs_list = [s.strip() for s in ex_specs.split('\n') if s.strip()]
                                    cat_manager.add_or_update_item(ex_id, ex_brand, ex_brand, ex_rep_desc, specs_list, unidad=ex_unit, costo=0.0)
                                    st.success(f"Catálogo actualizado: {ex_id}")
                                    st.rerun()

                    if quote_rows:
                        st.table(pd.DataFrame(quote_rows))
                        if st.session_state.get('extra_items') and st.button("🗑️ Limpiar Ítems Extra"):
                            st.session_state['extra_items'] = []
                            st.rerun()
            else:
                st.error("Error al cargar esquema.")
        else:
            st.error("No se encontraron datos.")

# ==========================================
# 5. Routing Components
# ==========================================

if selected_module == "Configuración":
    st.header("⚙️ Configuración del Sistema")
    
    # 1. API CONNECTION
    with st.expander("🔌 Conexión API y Datos", expanded=True):
        api_token = st.text_input("Token de ONA", value=app_config.get("ona_api_token", ""), type="password")
        
        # Determine button label based on state
        btn_label = "🔓 Conectar y Cargar Formularios" if 'forms_cache' not in st.session_state else "🔄 Actualizar Lista de Formularios"
        
        if st.button(btn_label):
            handler = OnaAPIHandler(api_token)
            forms_list = handler.get_user_forms()
            if forms_list:
                st.session_state['forms_cache'] = {f['formid']: f['title'] for f in forms_list}
                app_config["ona_api_token"] = api_token
                save_config(app_config)
                st.success(f"Conectado: {len(forms_list)} formularios disponibles.")
                st.rerun()
            else:
                st.error("Error de Token o sin formularios.")

        if 'forms_cache' in st.session_state:
            st.divider()
            form_opts = st.session_state['forms_cache']
            
            # Form Selection for Schema Mapping
            c_f1, c_f2 = st.columns([3, 1])
            with c_f1:
                selected_form_id = st.selectbox("Formulario para Mapeo", list(form_opts.keys()), format_func=lambda x: f"{form_opts[x]} ({x})")
            with c_f2:
                st.write("") # Spacer
                st.write("")
                if st.button("📋 Obtener Columnas para Mapeo"):
                    handler = OnaAPIHandler(app_config.get("ona_api_token"))
                    
                    # Query only 5 records to get column structure (lightweight)
                    with st.spinner("Obteniendo estructura del formulario..."):
                        sample_df = handler.query_filtered_data(form_id=selected_form_id, limit=5)
                    
                    if not sample_df.empty:
                        app_config["ona_form_id"] = selected_form_id
                        save_config(app_config)
                        
                        # Store only column names, not the data
                        st.session_state['mapping_sample_columns'] = list(sample_df.columns)
                        st.success(f"✅ Columnas cargadas: {len(sample_df.columns)} campos disponibles.")
                        st.rerun()
                    else:
                        st.error("Formulario vacío o sin datos.")
        else:
            st.info("👆 Haz clic en 'Conectar' para ver tus formularios.")

    # 2. SCHEMA MAPPING
    st.subheader("🗺️ Mapeo de Columnas (Schema Mapping)")
    st.markdown("Asocia los campos de ONA con las variables clave del sistema. Esto permite cambiar de formulario sin romper la app.")
    
    # Use stored column names from lightweight sample
    available_cols = st.session_state.get('mapping_sample_columns', [])
    
    if available_cols:
        all_cols = sorted(available_cols)
        
        with st.form("mapping_form"):
            st.write("Selecciona las columnas que corresponden a:")
            
            curr_client = grouping_config.get('column_cliente', '')
            curr_site = grouping_config.get('column_sitio', '')
            
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                new_client = st.selectbox(
                    "Cliente (Agrupador)", 
                    options=all_cols, 
                    index=all_cols.index(curr_client) if curr_client in all_cols else 0,
                    help="Columna que contiene el nombre del cliente (ej. group_info/client_name)."
                )
            with c_m2:
                new_site = st.selectbox(
                    "Sitio (Identificador)", 
                    options=all_cols, 
                    index=all_cols.index(curr_site) if curr_site in all_cols else 0,
                    help="Columna que contiene el nombre único del sitio."
                )
                
            if st.form_submit_button("💾 Guardar Nueva Configuración"):
                new_mapping = mapping_config.copy()
                if 'config' not in new_mapping: new_mapping['config'] = {}
                
                new_mapping['config']['column_cliente'] = new_client
                new_mapping['config']['column_sitio'] = new_site
                
                with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
                    yaml.dump(new_mapping, f, allow_unicode=True, default_flow_style=False)
                
                # Update runtime config
                grouping_config['column_cliente'] = new_client
                grouping_config['column_sitio'] = new_site
                
                st.success("✅ Mapeo actualizado. La aplicación ahora usará estas columnas.")
                st.rerun()
    else:
        if 'forms_cache' not in st.session_state:
            st.warning("⚠️ Paso 1: Primero conecta tu cuenta ONA en el panel de arriba ('🔌 Conexión API y Datos').")
        else:
            st.warning("⚠️ Paso 2: Obtén las columnas del formulario (botón 'Obtener Columnas para Mapeo' arriba) para habilitar el mapeo.")

elif selected_module == "Dashboard BI":
    st.title("📊 Análisis Operativo (Self-Service)")
    st.markdown("Utiliza el editor visual para explorar tus datos como en Tableau.")
    
    if 'forms_cache' not in st.session_state:
        st.warning("⚠️ Conecta tu Token de ONA en la sección 'Configuración' primero.")
    else:
        form_opts = st.session_state['forms_cache']
        
        # Dashboard Mode Selector
        bi_mode = st.radio("Modo de Análisis", ["Individual", "Global (Múltiples Formularios)"], horizontal=True)
        
        if bi_mode == "Individual":
            selected_forms_bi = st.selectbox(
                "Selecciona el formulario a analizar:",
                list(form_opts.keys()),
                format_func=lambda x: form_opts[x],
                key="bi_form_selector"
            )
            selected_forms_bi = [selected_forms_bi] if selected_forms_bi else []
            spec_file = f"dashboard_specs/spec_{selected_forms_bi[0]}.json" if selected_forms_bi else None
        else:
            selected_forms_bi = st.multiselect(
                "Selecciona los formularios para el dashboard global:",
                list(form_opts.keys()),
                format_func=lambda x: form_opts[x],
                key="bi_multi_selector"
            )
            spec_file = "dashboard_specs/spec_global.json" if selected_forms_bi else None
        
        # Calculated Fields UI
        with st.expander("🧮 Campos Calculados y Métricas", expanded=False):
            st.markdown("Crea nuevas columnas a partir de fórmulas matemáticas simples entre columnas existentes.")
            if 'bi_calculations' not in st.session_state:
                st.session_state['bi_calculations'] = []
            
            with st.form("calc_form"):
                c1, c2 = st.columns([1, 2])
                calc_name = c1.text_input("Nombre del nuevo campo", placeholder="ej. Ratio_Cumplimiento")
                calc_formula = c2.text_input("Fórmula (ej. `campo_A / campo_B`)", help="Usa backticks (`) para nombres de columnas con espacios.")
                if st.form_submit_button("➕ Añadir Campo"):
                    if calc_name and calc_formula:
                        st.session_state['bi_calculations'].append({'name': calc_name, 'formula': calc_formula})
                        st.success(f"Campo '{calc_name}' añadido.")
                        st.rerun()
            
            if st.session_state['bi_calculations']:
                st.write("**Campos configurados:**")
                for i, calc in enumerate(st.session_state['bi_calculations']):
                    c1, c2 = st.columns([5, 1])
                    c1.code(f"{calc['name']} = {calc['formula']}")
                    if c2.button("🗑️", key=f"del_calc_{i}"):
                        st.session_state['bi_calculations'].pop(i)
                        st.rerun()

        # Filters panel
        with st.expander("🔍 Filtros Avanzados de Carga", expanded=False):
            col_cliente = grouping_config.get('column_cliente', '')
            col_sitio = grouping_config.get('column_sitio', '')
            
            col1, col2 = st.columns(2)
            with col1:
                filter_bi_cliente = st.text_input("Filtrar por Cliente", key="bi_cliente_filter")
            with col2:
                filter_bi_sitio = st.text_input("Filtrar por Sitio", key="bi_sitio_filter")
            
            limit_bi = st.number_input("Límite de registros por formulario", min_value=10, max_value=10000, value=1000, step=100)
        
        # Load data button
        if st.button("📊 Cargar/Actualizar Datos", type="primary", use_container_width=True):
            if not selected_forms_bi:
                st.warning("Selecciona al menos un formulario.")
            else:
                handler = OnaAPIHandler(app_config.get('ona_api_token'))
                
                # Build filters
                filters_bi = {}
                if filter_bi_cliente and col_cliente:
                    filters_bi[col_cliente] = filter_bi_cliente
                if filter_bi_sitio and col_sitio:
                    filters_bi[col_sitio] = filter_bi_sitio
                
                # Query data from all selected forms
                with st.spinner("Consultando ONA..."):
                    if bi_mode == "Individual":
                        df_bi = handler.query_filtered_data(
                            form_id=selected_forms_bi[0],
                            filters=filters_bi if filters_bi else None,
                            limit=limit_bi
                        )
                    else:
                        df_bi = handler.query_multi_forms(
                            form_ids=selected_forms_bi,
                            filters=filters_bi if filters_bi else None,
                            forms_metadata=form_opts
                        )
                
                if not df_bi.empty:
                    # Apply calculations
                    for calc in st.session_state.get('bi_calculations', []):
                        try:
                            df_bi[calc['name']] = df_bi.eval(calc['formula'])
                        except Exception as e:
                            st.error(f"Error en fórmula '{calc['formula']}': {e}")
                    
                    st.session_state['bi_dataset'] = df_bi
                    st.session_state['bi_last_query'] = {
                        'forms': [form_opts[f] for f in selected_forms_bi],
                        'records': len(df_bi),
                        'timestamp': time.time(),
                        'spec_file': spec_file
                    }
                    st.success(f"✅ Cargados {len(df_bi)} registros.")
                    st.rerun()
                else:
                    st.warning("No se encontraron datos.")
        
        # Display BI tool if data loaded
        if 'bi_dataset' in st.session_state and not st.session_state['bi_dataset'].empty:
            df_bi = st.session_state['bi_dataset']
            last_query = st.session_state.get('bi_last_query', {})
            current_spec = last_query.get('spec_file')
            
            # Show data info
            st.caption(f"📊 Analizando: {', '.join(last_query.get('forms', []))} | {last_query.get('records', 0)} registros")
            
            # Ensure spec file directory exists
            if not os.path.exists("dashboard_specs"):
                os.makedirs("dashboard_specs")
                
            # PyGWalker integration
            if pyg:
                with st.container():
                    # If spec file exists, PyGWalker will load it. 
                    # If it doesn't, it will create it upon saving.
                    pyg.walk(df_bi, spec=current_spec, env='Streamlit', dark='light')
                    st.info(f"💡 El diseño del dashboard se guarda automáticamente en: `{current_spec}`")
            else:
                st.warning("⚠️ PyGWalker no está instalado. Mostrando tabla estática.")
                st.dataframe(df_bi, use_container_width=True)
        else:
            st.info("👆 Selecciona el/los formularios y haz clic en 'Cargar Datos'.")

elif selected_module == "Historial Generado":
    st.title("🗄️ Historial de Documentos")
    records = hist_mgr.list_history()
    if not records:
        st.info("No hay historial disponible.")
    else:
        def load_history_callback(record_id, snapshot, report_type):
            st.session_state['editing_history_id'] = record_id
            st.session_state['extra_items'] = snapshot.get('extra_items', [])
            st.session_state['history_preload_texts'] = snapshot.get('custom_texts', {})
            st.session_state['history_quote_rows'] = snapshot.get('quote_rows', [])
            
            # Pre-fill Selectors if available
            selectors = snapshot.get('selectors', {})
            if selectors.get('form_id'):
                st.session_state[f"wizard_{report_type}_form"] = selectors['form_id']
            if selectors.get('client'):
                st.session_state[f"wizard_{report_type}_cliente"] = selectors['client']
            if selectors.get('site'):
                st.session_state[f"wizard_{report_type}_sitio"] = selectors['site']
            
            # Force navigation (Modified in callback, safe for next run)
            st.session_state['main_nav_radio'] = "Propuesta técnica"

        for rec in records:
            with st.expander(f"📅 {rec.get('created_at_fmt')} | {rec.get('site_name')}"):
                st.button(
                    "✏️ Cargar al Editor", 
                    key=f"btn_{rec['id']}",
                    on_click=load_history_callback,
                    args=(rec['id'], rec.get('data', {}), rec.get('report_type', 'propuesta_tecnica'))
                )

elif selected_module == "Gestión de Catálogo":
    st.title("📦 Gestión de Catálogo y Proyectos")
    
    # Initialize Manager
    cat_manager = CatalogManager()
    
    tab_equipos, tab_proyectos = st.tabs(["🔧 Equipos", "📁 Proyectos"])
    
    with tab_equipos:
        # --- EQUIPOS ---
        st.markdown("Administra la base de datos de modelos, precios y especificaciones.")
        
        c1, c2 = st.columns([1, 1])
        with c1:
            uploaded_file = st.file_uploader("Importar Excel/CSV", type=['xlsx', 'csv'])
            if uploaded_file:
                if st.button("Procesar Archivo"):
                    success, msg = cat_manager.process_bulk_upload(uploaded_file)
                    if success: st.success(msg)
                    else: st.error(msg)
        with c2:
            st.download_button(
                label="Descargar Plantilla Vacía",
                data=cat_manager.generate_template_excel(),
                file_name="plantilla_catalogo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.divider()

        # CRUD Form
        with st.expander("➕ / ✏️ Agregar o Editar Equipo", expanded=False):
            # Select Equipment to Edit
            equip_options = ["-- Nuevo Equipo --"] + sorted(list(cat_manager.data.keys()))
            selected_equip_key = st.selectbox("Seleccionar Equipo para Editar:", equip_options)
            
            # Init values
            init_id = ""
            init_brand = ""
            init_desc = ""
            init_unit = "Pza"
            init_cost = 0.0
            init_rep_desc = ""
            init_specs = ""
            
            if selected_equip_key != "-- Nuevo Equipo --":
                item_data = cat_manager.data.get(selected_equip_key, {})
                init_id = selected_equip_key
                init_brand = item_data.get("marca", "")
                init_desc = item_data.get("descripcion", "")
                init_unit = item_data.get("unidad_medida", "Pza")
                init_cost = float(item_data.get("costo_unitario", 0.0))
                init_rep_desc = item_data.get("descripcion_reporte", "")
                # Handle specs list vs string
                raw_specs = item_data.get("caracteristicas", [])
                if isinstance(raw_specs, list):
                    init_specs = "\n".join(raw_specs)
                else:
                    init_specs = str(raw_specs)

            c_crud1, c_crud2 = st.columns([1, 1])
            id_input = c_crud1.text_input("ID Modelo (Único)", value=init_id, help="Ej: AXIS-P1467")
            brand_input = c_crud2.text_input("Marca", value=init_brand, help="Ej: Axis")
            
            c_crud3, c_crud4, c_crud5 = st.columns([2, 1, 1])
            desc_input = c_crud3.text_input("Descripción Corta (Para Tabla)", value=init_desc)
            unit_input = c_crud4.text_input("Unidad", value=init_unit)
            cost_input = c_crud5.number_input("Costo Unitario (USD/MXN)", value=init_cost, min_value=0.0)
            
            report_desc_input = st.text_area("Descripción Detallada (Para Reporte)", value=init_rep_desc, height=100)
            specs_input = st.text_area("Características (Una por línea o separadas por |)", value=init_specs, height=100)
            
            if st.button("Guardar Equipo"):
                if id_input:
                    specs_list = [s.strip() for s in specs_input.replace('\n', '|').split('|') if s.strip()]
                    if cat_manager.add_or_update_item(id_input, brand_input, desc_input, report_desc_input, specs_list, unit_input, cost_input):
                        st.success(f"Guardado: {id_input}")
                        st.rerun()
                    else:
                        st.error("Error al guardar.")
                else:
                    st.warning("El ID es obligatorio.")

        # VIEW TABLE
        df_cat = cat_manager.get_as_dataframe()
        if not df_cat.empty:
            st.dataframe(df_cat, use_container_width=True)
            
            # Delete logic
            to_del = st.selectbox("Seleccionar para eliminar:", ["-- Seleccionar --"] + list(cat_manager.data.keys()))
            if to_del != "-- Seleccionar --":
                if st.button(f"🗑️ Eliminar {to_del}"):
                    cat_manager.delete_item(to_del)
                    st.success("Eliminado.")
                    st.rerun()
        else:
            st.info("El catálogo está vacío.")

    with tab_proyectos:
        # --- PROYECTOS ---
        st.markdown("Configura datos maestros por Proyecto (Alcance, Condiciones, etc.) para auto-completar reportes.")
        
        # Select Project to Edit
        project_options = ["-- Nuevo Proyecto --"] + list(cat_manager.projects.keys())
        selected_prj_key = st.selectbox("Seleccionar Proyecto para Editar:", project_options)
        
        # Determine initial values
        init_id = ""
        init_client = ""
        init_desc = ""
        init_scope = ""
        init_conds = ""
        
        if selected_prj_key != "-- Nuevo Proyecto --":
            p_data = cat_manager.projects.get(selected_prj_key, {})
            init_id = selected_prj_key
            init_client = p_data.get("cliente", "")
            init_desc = p_data.get("descripcion_breve", "")
            # Convert lists back to string
            init_scope = "\n".join(p_data.get("alcance", [])) if isinstance(p_data.get("alcance"), list) else p_data.get("alcance", "")
            init_conds = "\n".join(p_data.get("condiciones_comerciales", [])) if isinstance(p_data.get("condiciones_comerciales"), list) else p_data.get("condiciones_comerciales", "")
            
        with st.expander("➕ / ✏️ Detalles del Proyecto", expanded=True):
            cp1, cp2 = st.columns(2)
            # If editing, lock ID or allow change (usually lock is safer, but user might want to clone. Let's allow edit but warn)
            prj_id = cp1.text_input("ID Proyecto (Coincidir con ONA)", value=init_id, help="Ej: C5-Hidalgo")
            prj_client = cp2.text_input("Nombre Cliente", value=init_client)
            
            prj_desc = st.text_area("Descripción Breve del Proyecto", value=init_desc, height=70)
            
            cp3, cp4 = st.columns(2)
            prj_scope = cp3.text_area("Alcance (Separar por | o Enter)", value=init_scope, height=150, help="Lista de puntos del alcance")
            prj_conds = cp4.text_area("Condiciones Comerciales (Separar por | o Enter)", value=init_conds, height=150, help="Vigencia, tiempos de entrega, etc.")
            
            c_btn1, c_btn2 = st.columns([1, 4])
            with c_btn1:
                if st.button("Guardar Proyecto"):
                    if prj_id:
                        scope_list = [s.strip() for s in prj_scope.replace('\n', '|').split('|') if s.strip()]
                        conds_list = [s.strip() for s in prj_conds.replace('\n', '|').split('|') if s.strip()]
                        
                        if cat_manager.add_or_update_project(prj_id, prj_client, scope_list, prj_desc, conds_list):
                            st.success(f"Proyecto {prj_id} guardado.")
                            st.rerun()
                        else:
                            st.error("Error al guardar proyecto.")
                    else:
                        st.warning("ID Proyecto requerido.")
            
            with c_btn2:
                if selected_prj_key != "-- Nuevo Proyecto --":
                    if st.button("🗑️ Eliminar Proyecto"):
                        cat_manager.delete_project(selected_prj_key)
                        st.success(f"Proyecto {selected_prj_key} eliminado.")
                        st.rerun()

        # Table Projects
        df_prj = cat_manager.get_projects_as_dataframe()
        if not df_prj.empty:
            st.dataframe(df_prj, use_container_width=True)
            
            del_prj = st.selectbox("Eliminar Proyecto:", ["-- Seleccionar --"] + list(cat_manager.projects.keys()), key="del_prj_sel")
            if del_prj != "-- Seleccionar --":
                if st.button(f"🗑️ Eliminar {del_prj}", key="del_prj_btn"):
                    cat_manager.delete_project(del_prj)
                    st.success("Eliminado.")
                    st.rerun()
        else:
            st.info("No hay proyectos configurados.")

elif selected_module == "Analítica Global":
    st.title("🌎 Centro de Comando Global")
    st.markdown("Navegación en tiempo real de datos desde ONA. Aplica filtros y consulta solo lo que necesitas.")
    
    if 'forms_cache' not in st.session_state:
        st.warning("⚠️ Primero conecta tu Token de ONA en la sección 'Configuración'.")
    else:
        form_opts = st.session_state['forms_cache']
        
        # Sidebar: Query configuration
        with st.sidebar:
            st.divider()
            st.markdown("### 🔍 Configuración de Consulta")
            
            # Form selection
            selected_forms_global = st.multiselect(
                "Formularios a Consultar",
                list(form_opts.keys()),
                format_func=lambda x: form_opts[x],
                help="Selecciona uno o más formularios para analizar"
            )
            
            if selected_forms_global:
                col_cliente = grouping_config.get('column_cliente', 'Cliente')
                col_sitio = grouping_config.get('column_sitio', 'nombre_sitio')
                
                # Dynamic filters
                st.markdown("**Filtros Dinámicos:**")
                filter_cliente_global = st.text_input("Cliente", placeholder="Ej: ACME", key="global_cliente")
                filter_sitio_global = st.text_input("Sitio", placeholder="Ej: Site-01", key="global_sitio")
                
                # Query button
                if st.button("🔍 Consultar Datos", type="primary", use_container_width=True):
                    handler = OnaAPIHandler(app_config.get('ona_api_token'))
                    
                    # Build filters
                    filters_global = {}
                    if filter_cliente_global and col_cliente:
                        filters_global[col_cliente] = filter_cliente_global
                    if filter_sitio_global and col_sitio:
                        filters_global[col_sitio] = filter_sitio_global
                    
                    # Query from ONA
                    with st.spinner("Consultando ONA en tiempo real..."):
                        gdf = get_cached_multi_forms(
                            api_token=app_config.get('ona_api_token'),
                            form_ids=selected_forms_global,
                            filters_json=safe_json_dumps(filters_global) if filters_global else None,
                            forms_metadata_json=safe_json_dumps(form_opts)
                        )
                    
                    if not gdf.empty:
                        st.session_state['query_result'] = gdf
                        st.session_state['last_query_time'] = time.time()
                        st.session_state['last_query_info'] = {
                            'forms': [form_opts[f] for f in selected_forms_global],
                            'records': len(gdf),
                            'filters': filters_global
                        }
                        st.success(f"✅ Consultados {len(gdf)} registros desde ONA.")
                        st.rerun()
                    else:
                        st.warning("No se encontraron datos con los criterios seleccionados.")
        
        # Main content area
        gdf = st.session_state.get('query_result', pd.DataFrame())
    
    if not gdf.empty:
        st.markdown("""
            <style>
            .stTabs [data-baseweb="tab-list"] {
                gap: 24px;
                border-bottom: 2px solid #714B67;
            }
            .stTabs [data-baseweb="tab"] {
                height: 40px;
                white-space: pre-wrap;
                background-color: transparent;
                border: none;
                color: #4B5563;
                font-weight: 500;
            }
            .stTabs [aria-selected="true"] {
                color: #714B67 !important;
            font-weight: 700 !important;
            }
            </style>
        """, unsafe_allow_html=True)
        
        tab_summary, tab_map, tab_table, tab_photos = st.tabs(["� Vista Resumen", "�🗺️ Mapa", "📊 Tabla", "🖼️ Galería"])
        
        # Define mapping columns for filtering
        col_cliente = grouping_config.get('column_cliente', 'Cliente')
        col_sitio = grouping_config.get('column_sitio', 'nombre_sitio')
        
        # Additional in-page filters (client-side filtering on already loaded data)
        with st.expander("🔍 Filtros Adicionales (sobre datos cargados)", expanded=False):
            st.caption("Estos filtros se aplican sobre los datos ya consultados, sin necesidad de re-consultar ONA.")
            
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                forms_avail = sorted(gdf['source_form_title'].unique().tolist()) if 'source_form_title' in gdf.columns else []
                f_form = st.multiselect("Por Formulario", forms_avail, key="page_filter_form")
            with col_f2:
                clients_avail = sorted(gdf[col_cliente].dropna().unique().tolist()) if col_cliente in gdf.columns else []
                f_client = st.multiselect("Por Cliente", clients_avail, key="page_filter_client")
            with col_f3:
                f_site_search = st.text_input("Buscar Sitio", key="page_filter_site")
        
        # Apply client-side filters
        filtered_gdf = gdf.copy()
        if f_form:
            filtered_gdf = filtered_gdf[filtered_gdf['source_form_title'].isin(f_form)]
        if f_client:
            filtered_gdf = filtered_gdf[filtered_gdf[col_cliente].isin(f_client)]
        if f_site_search:
            filtered_gdf = filtered_gdf[filtered_gdf[col_sitio].astype(str).str.contains(f_site_search, case=False, na=False)]

        # --- TABS CONTENT ---
        
        with tab_summary:
            st.subheader("📋 Resumen Compacto de Sitios")
            st.markdown("Vista optimizada: Datos del Sitio | Ubicación | Fachada")
            
            # Identify potential facade/photo columns
            photo_cols = [c for c in filtered_gdf.columns if any(k in c.lower() for k in ['foto', 'fachada', 'img', 'photo', 'image'])]
            lat_col = next((c for c in filtered_gdf.columns if 'latitude' in c.lower()), None)
            lon_col = next((c for c in filtered_gdf.columns if 'longitude' in c.lower()), None)
            
            # CSS for compact rows
            st.markdown("""
                <style>
                .compact-row { 
                    border-bottom: 1px solid #eee; 
                    padding: 8px 0; 
                    display: flex; 
                    align-items: center;
                }
                .compact-info { flex: 2; }
                .compact-loc { flex: 2; }
                .compact-img { flex: 1; text-align: right; }
                </style>
            """, unsafe_allow_html=True)

            if filtered_gdf.empty:
                st.info("No hay datos para mostrar.")
            else:
                api_token = app_config.get('ona_api_token')
                for idx, row in filtered_gdf.head(100).iterrows(): # Limit for summary
                    c1, c2, c3 = st.columns([3, 3, 2])
                    
                    with c1:
                        st.markdown(f"**{row.get(col_sitio, 'S/N')}**")
                        st.caption(f"👤 {row.get(col_cliente, 'S/C')}")
                    
                    with c2:
                        lat, lon = row.get(lat_col), row.get(lon_col)
                        if pd.notna(lat) and pd.notna(lon):
                            st.markdown(f"📍 `{lat:.5f}, {lon:.5f}`")
                            st.caption(f"[🌐 Ver en Maps](https://www.google.com/maps/search/?api=1&query={lat},{lon})")
                        else:
                            st.caption("📍 Sin ubicación")
                    
                    with c3:
                        # Find first available photo
                        img_path = None
                        for p_col in photo_cols:
                            if pd.notna(row.get(p_col)):
                                img_path = row.get(p_col)
                                break
                        
                        if img_path:
                            # Use proxy to fetch image - passing attachments list for efficiency
                            img_data = fetch_ona_image(img_path, api_token, row.get('source_form_id'), attachments_list=row.get('_attachments', []))
                            if img_data:
                                st.image(img_data, width=150)
                            else:
                                st.caption(f"🖼️ {img_path[:10]}...")
                        else:
                            st.caption("🚫 Sin foto")
                    st.divider()

        with tab_map:
            st.subheader("📍 Mapa de Registros")
            if lat_col and lon_col:
                map_data = filtered_gdf[[lat_col, lon_col]].dropna()
                map_data.columns = ['lat', 'lon']
                if not map_data.empty:
                    st.map(map_data)
                    selected_record = st.selectbox(
                        "Selecciona para ver detalle completo:",
                        range(len(filtered_gdf)),
                        format_func=lambda x: f"{filtered_gdf.iloc[x].get(col_sitio, 'N/A')} ({filtered_gdf.iloc[x].get('source_form_title', 'Form')})",
                        key="map_record_selector"
                    )
                    if selected_record is not None:
                        st.json(filtered_gdf.iloc[selected_record].to_dict())
                else:
                    st.info("Sin coordenadas en los registros actuales.")
            else:
                st.warning("No se detectaron columnas de GPS.")

        with tab_table:
            st.subheader("📊 Datos Crudos")
            common_cols = ['source_form_title', col_cliente, col_sitio, '_submission_time']
            actual_cols = [c for c in common_cols if c in filtered_gdf.columns]
            extra_cols = st.multiselect("Columnas extra:", [c for c in filtered_gdf.columns if c not in actual_cols], key="table_extra_cols")
            st.dataframe(filtered_gdf[actual_cols + extra_cols], use_container_width=True)
            
            csv = filtered_gdf.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar CSV", data=csv, file_name="ona_data.csv", mime="text/csv")

        with tab_photos:
            st.subheader("🖼️ Galería Detallada")
            if not photo_cols:
                st.info("No hay columnas de fotos.")
            else:
                api_token = app_config.get('ona_api_token')
                for idx, row in filtered_gdf.head(30).iterrows():
                    st.markdown(f"🚩 **{row.get(col_sitio)}** | {row.get(col_cliente)}")
                    p_cols_ui = st.columns(4)
                    for i, p_col in enumerate(photo_cols):
                        img_path = row.get(p_col)
                        if pd.notna(img_path):
                            with p_cols_ui[i % 4]:
                                # Passing attachments list for efficiency
                                img_data = fetch_ona_image(img_path, api_token, row.get('source_form_id'), attachments_list=row.get('_attachments', []))
                                if img_data:
                                    st.image(img_data, caption=p_col, use_container_width=True)
                                else:
                                    st.caption(f"❌ {img_path[:15]}")
                    st.divider()
        st.divider()
    else:
        st.info("👆 Selecciona formularios en el sidebar y haz clic en 'Consultar Datos' para comenzar.")


elif selected_module == "Gestión de Catálogo":
    st.title("📦 Gestión Maestra de Catálogo")
    st.markdown("Base de datos centralizada de equipos y redacciones técnicas.")
    
    manager = CatalogManager()
    
    tab1, tab2, tab3 = st.tabs(["📋 Inventario", "✏️ Alta/Edición", "📤 Carga Masiva"])
    
    with tab1:
        st.subheader("Inventario Actual")
        df_cat = manager.get_as_dataframe()
        if not df_cat.empty:
            st.dataframe(df_cat, use_container_width=True)
        else:
            st.info("El catálogo está vacío.")
            
    with tab2:
        st.subheader("Alta o Edición de Equipo")
        
        # --- EDIT SELECTOR ---
        existing_models = sorted(list(manager.data.keys()))
        col_sel, col_new = st.columns([3, 1])
        
        selected_to_edit = col_sel.selectbox(
            "Seleccionar equipo para editar (opcional):",
            ["-- Nuevo Registro --"] + existing_models,
            index=0,
            key="cat_edit_selector"
        )
        
        if col_new.button("✨ Limpiar / Nuevo", use_container_width=True):
            st.session_state['cat_edit_selector'] = "-- Nuevo Registro --"
            st.rerun()

        # Load data if an item is selected
        edit_data = {}
        is_editing = False
        if selected_to_edit != "-- Nuevo Registro --":
            edit_data = manager.data[selected_to_edit]
            is_editing = True
            
        c1, c2 = st.columns([2, 1])
        with c1:
            model_id = st.text_input("ID Modelo (Clave Única)", value=selected_to_edit if is_editing else "", placeholder="Ej. ANT-OMNI-5G")
            brand = st.text_input("Marca", value=edit_data.get('marca', ""))
        with c2:
            short_desc = st.text_input("Descripción Corta", value=edit_data.get('descripcion', ""), placeholder="Ej. Antena Omnidireccional")
            unit_val = st.text_input("Unidad", value=edit_data.get('unidad_medida', "Pza"))
            
        report_desc = st.text_area("Descripción Técnica (Reporte)", value=edit_data.get('descripcion_reporte', ""), placeholder="Redacción larga que aparecerá en el documento generado...", height=100)
        specs_raw = st.text_area("Características (Listado)", value="\n".join(edit_data.get('caracteristicas', [])), placeholder="Una característica por línea...", height=100)
        
        btn_label = "Update 💾 Actualizar Equipo" if is_editing else "💾 Guardar Nuevo Equipo"
        if st.button(btn_label, type="primary"):
            if model_id and brand:
                specs_list = [s.strip() for s in specs_raw.split('\n') if s.strip()]
                if manager.add_or_update_item(model_id, brand, short_desc, report_desc, specs_list, unidad=unit_val, costo=0.0):
                    st.success(f"Equipo '{model_id}' {'actualizado' if is_editing else 'guardado'} correctamente.")
                    st.rerun()
                else:
                    st.error("Error al guardar.")
            else:
                st.warning("El ID y la Marca son obligatorios.")

    with tab3:
        st.subheader("Carga Masiva (Excel/CSV)")
        st.markdown("1. Descarga la plantilla. 2. Llénala con tus equipos. 3. Súbela para actualizar el catálogo.")
        
        # Download Template
        template_bytes = manager.generate_template_excel()
        st.download_button(
            label="📥 Descargar Plantilla Maestra (.xlsx)",
            data=template_bytes,
            file_name="plantilla_catalogo_tred.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Upload
        uploaded_file = st.file_uploader("Subir Archivo de Carga", type=['xlsx', 'csv'])
        if uploaded_file:
            if st.button("🔄 Procesar Carga"):
                success, msg = manager.process_bulk_upload(uploaded_file)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

elif selected_module == "Propuesta técnica":
    if 'propuesta_tecnica' in report_types: render_wizard('propuesta_tecnica', "Propuesta técnica")

# === MODIFIED MODULE: MEMORIA TÉCNICA (MULTI-SOURCE) ===
elif selected_module == "Ingeniería (Memorias)":
    st.title("🏗️ Generador de Memorias Técnicas (Multi-Form)")
    st.info("Fusión de múltiples formularios para un mismo sitio.")

    # Step 1: Select Forms
    if 'forms_cache' not in st.session_state:
        st.warning("⚠️ Conecta tu Token en 'Configuración'.")
    else:
        form_opts = st.session_state['forms_cache']
        selected_forms_memoria = st.multiselect(
            "1️⃣ Selecciona los Formularios a procesar:",
            options=list(form_opts.keys()),
            format_func=lambda x: form_opts[x]
        )
        
        if not selected_forms_memoria:
            st.info("👆 Selecciona al menos un formulario para continuar.")
        else:
            col_cliente = grouping_config.get('column_cliente', '')
            col_sitio = grouping_config.get('column_sitio', '')
            
            if not col_cliente or not col_sitio:
                st.error("⚠️ Configura el mapeo de columnas en 'Configuración' primero.")
            else:
                handler = OnaAPIHandler(app_config.get('ona_api_token'))
                
                # Step 2: Query unique clients from all selected forms
                st.divider()
                st.markdown("### 2️⃣ Selección del Cliente y Sitio")
                
                with st.spinner("Cargando clientes de formularios seleccionados..."):
                    all_clients = set()
                    for fid in selected_forms_memoria:
                        clients_temp = get_cached_unique_values(app_config.get('ona_api_token'), fid, col_cliente)
                        all_clients.update(clients_temp)
                
                if not all_clients:
                    st.warning("No se encontraron clientes en los formularios seleccionados.")
                else:
                    sel_client = st.selectbox(
                        "Cliente",
                        options=sorted(all_clients),
                        index=None,
                        placeholder="Filtrar por cliente...",
                        key="memoria_cliente"
                    )
                    
                    if sel_client:
                        # Step 3: Query sites for selected client
                        with st.spinner(f"Cargando sitios para {sel_client}..."):
                            all_sites = set()
                            for fid in selected_forms_memoria:
                                sites_temp = get_cached_unique_values(
                                    app_config.get('ona_api_token'),
                                    fid,
                                    col_sitio,
                                    filters_json=safe_json_dumps({col_cliente: sel_client})
                                )
                                all_sites.update(sites_temp)
                        
                        if all_sites:
                            sel_site = st.selectbox(
                                "Sitio Objetivo",
                                options=sorted(all_sites),
                                index=None,
                                placeholder="Elige el sitio...",
                                key="memoria_sitio"
                            )
                            
                            if sel_site:
                                st.divider()
                                st.markdown("### 3️⃣ Validación Previa (Pre-Flight Check)")
                                
                                # Query data for validation
                                with st.spinner("Consultando datos del sitio..."):
                                    site_data_frames = []
                                    memoria_media_links = {}
                                    for fid in selected_forms_memoria:
                                        df_temp = get_cached_filtered_data(
                                            api_token=app_config.get('ona_api_token'),
                                            form_id=fid,
                                            filters_json=safe_json_dumps({col_cliente: sel_client, col_sitio: sel_site})
                                        )
                                        if not df_temp.empty:
                                            site_data_frames.append(df_temp)
                                            # Fetch CSV links for the first matching record of each form for the memory
                                            first_id = df_temp.iloc[0]['_id']
                                            links = get_csv_media_links(app_config.get('ona_api_token'), fid, first_id)
                                            memoria_media_links.update(links)
                                
                                if not site_data_frames:
                                    st.warning("No se encontraron datos para este cliente/sitio en los formularios seleccionados.")
                                else:
                                    # Consolidate data
                                    consolidated_df = pd.concat(site_data_frames, ignore_index=True)
                                    st.success(f"✅ Encontrados {len(consolidated_df)} registros de {len(site_data_frames)} formulario(s).")
                                    
                                    # Model validation
                                    model_col = "modelo_equipo"
                                    
                                    if model_col not in consolidated_df.columns:
                                        st.warning(f"No se detectó la columna '{model_col}' para validar equipos.")
                                        ready_to_gen = True
                                    else:
                                        models_found = consolidated_df[model_col].dropna().unique().tolist()
                                        manager = CatalogManager()
                                        valid, missing = manager.validate_models(models_found)
                                        
                                        if missing:
                                            st.error(f"🛑 ALERTA: Detectados {len(missing)} modelos desconocidos.")
                                            st.write("Estos equipos NO tienen ficha técnica. El reporte saldría incompleto.")
                                            st.code(missing)
                                            st.info("💡 Ve a 'Gestión de Catálogo' y dálos de alta.")
                                            ready_to_gen = False
                                        else:
                                            st.success("✅ Validado. Todos los equipos existen en el catálogo.")
                                            ready_to_gen = True
                                    
                                    if ready_to_gen:
                                        st.markdown("### 4️⃣ Generación")
                                        if st.button("🚀 Generar Memoria Técnica", type="primary"):
                                            engine = ReportEngine(mapping_config="mapping.yaml", catalog_data="catalogo_equipos.json", auth_token=app_config.get('ona_api_token'))
                                            if not os.path.exists("outputs"): os.makedirs("outputs")
                                            
                                            # Merge data from all rows
                                            consolidated_data = {}
                                            for _, row in consolidated_df.iterrows():
                                                clean_row = {k: v for k, v in row.to_dict().items() if pd.notna(v)}
                                                consolidated_data.update(clean_row)
                                            
                                            # Inject CSV media links
                                            consolidated_data.update(memoria_media_links)
                                            
                                            filename = f"outputs/Memoria_{sel_site}.docx"
                                            engine.generate_report(consolidated_data, filename, report_type="memoria_tecnica")
                                            st.success(f"✅ Memoria generada: {filename}")
                        else:
                            st.info("No se encontraron sitios para el cliente seleccionado.")

elif selected_module == "Obra (Bitácoras)":
    if 'bitacora_obra' in report_types: render_wizard('bitacora_obra', "Bitácora")
