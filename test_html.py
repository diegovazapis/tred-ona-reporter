import os
import sys

from html_engine import generate_bitacora_html

header_record = {
    '_id': 123,
    'cliente': 'PJ',
    'nombre_sitio': 'Ejem',
    '_geolocation': '[19.0, -99.0]'
}

instances_data = [
    {
        'form_name': 'Reporte 1',
        'date_str': '2026-06-12',
        'record_dict': {
            'q1': 'v1',
            '_attachments': []
        },
        'schema': {
            'children': [
                {'type': 'text', 'name': 'q1', 'label': 'Question 1'}
            ]
        }
    }
]

try:
    html = generate_bitacora_html(header_record, instances_data, {}, 'fake_token')
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
