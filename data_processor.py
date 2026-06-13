import logging
import os

_logger = logging.getLogger(__name__)

class ReportDataProcessor:
    """Helper class for processing ONA submission data for reports (Standalone)"""
    
    def __init__(self, submission_data):
        """
        Initialize processor with submission dictionary
        
        Args:
            submission_data (dict): Raw JSON data from ONA
        """
        self.submission = submission_data
        self.attachments = self.submission.get('_attachments', [])
    
    def map_choices_to_labels(self, field_name, value, choices_dict, schema_map=None):
        if not choices_dict or not value:
            return value
        
        formatted_value = str(value).replace('_', ' ').title()
        
        list_name = None
        if schema_map:
            list_name = schema_map.get(f"_list_{field_name}")
            if not list_name and '/' in field_name:
                exclude_group = field_name.split('/')[-1]
                list_name = schema_map.get(f"_list_{exclude_group}")
                
        if not list_name:
            if field_name in choices_dict:
                list_name = field_name
            else:
                return formatted_value
        
        field_choices = choices_dict.get(list_name, {})
        
        if ' ' in str(value) and not field_choices.get(value):
            parts = str(value).split(' ')
            labels = []
            matched_any = False
            for p in parts:
                if p in field_choices:
                    labels.append(field_choices[p])
                    matched_any = True
                else:
                    labels.append(p)
            if matched_any:
                return ", ".join(labels)
        
        return field_choices.get(value, formatted_value)
    
    def get_field_label(self, field_name, schema_map, custom_labels=None):
        if custom_labels and field_name in custom_labels:
            return custom_labels[field_name]
            
        if not schema_map:
            return field_name.replace('_', ' ').replace('/', ' - ').title()
        
        if field_name in schema_map:
            item = schema_map[field_name]
            if isinstance(item, dict):
                return item.get('label', field_name).strip()
            return str(item).strip()
            
        if '/' in field_name:
            leaf = field_name.split('/')[-1]
            if leaf in schema_map:
                item = schema_map[leaf]
                if isinstance(item, dict):
                    return item.get('label', leaf).strip()
                return str(item).strip()
                
        return field_name.split('/')[-1].replace('_', ' ').title()
    
    def process_image_field(self, field_value, field_name=None, schema_map=None):
        result = {
            'is_image': False,
            'attachment_id': None,
            'filename': field_value,
            'download_url': None
        }
        
        if not field_value:
            return result
        
        value_str = str(field_value)
        is_potential_image = False
        
        if schema_map and field_name in schema_map:
             field_type = schema_map[field_name].get('type', '')
             if field_type in ('image', 'photo'):
                 is_potential_image = True
        
        if not is_potential_image and value_str.lower().endswith(('.jpg', '.png', '.jpeg', '.gif')):
             is_potential_image = True
             
        if is_potential_image:
            result['is_image'] = True
            
            # Find download URL from attachments context
            found_att = None
            for att in self.attachments:
                if att.get('filename') == value_str or att.get('name') == value_str:
                    found_att = att
                    break
            
            if not found_att:
                 clean_name = os.path.splitext(value_str)[0]
                 for att in self.attachments:
                     if clean_name in att.get('filename', '') or clean_name in att.get('name', ''):
                         found_att = att
                         break
            
            if found_att:
                 result['download_url'] = found_att.get('download_url')
                 result['attachment_id'] = found_att.get('id')

        return result
    
    def get_formatted_fields(self, schema_map, choices_dict, skip_fields=None, custom_labels=None):
        if skip_fields is None:
            skip_fields = [
                '_attachments', '_id', '_uuid', '_submission_time', 
                '_status', '_submitted_by', '_xform_id_string', '_version',
                'formhub/uuid', 'meta/instanceID', 'meta/deprecatedID', 
                'start', 'end', 'deviceid', 'subscriberid', 'simserial',
                'phonenumber', 'username', 'email', 'audit',
                '__version__', '_geolocation', '_tags', '_notes', 
                '_edited', '_bamboo_dataset_id', '_total_media',
                '_media_count', '_media_all_received'
            ]
        
        formatted_fields = []
        custom_labels = custom_labels or {}
        json_data = self.submission
        
        keys_to_process = []
        if schema_map:
             keys_to_process = list(schema_map.keys())
             for k in json_data.keys():
                 if k not in schema_map:
                     keys_to_process.append(k)
        else:
             keys_to_process = list(json_data.keys())

        for key in keys_to_process:
            found_key = key
            if key not in json_data:
                for dk in json_data.keys():
                    if dk.endswith(f"/{key}"):
                        found_key = dk
                        break
                
            if found_key not in json_data:
                continue
                
            value = json_data[found_key]
            
            if any(found_key.startswith(skip) or found_key.endswith(skip) for skip in skip_fields):
                continue
            
            if isinstance(value, (dict, list)):
                continue
            
            if not value:
                continue
            
            image_info = self.process_image_field(value, field_name=found_key, schema_map=schema_map)
            field_label = self.get_field_label(found_key, schema_map, custom_labels)
            field_value = self.map_choices_to_labels(found_key, value, choices_dict, schema_map)
            
            formatted_fields.append({
                'label': field_label,
                'value': field_value,
                'is_image': image_info['is_image'],
                'download_url': image_info['download_url'],
                'filename': image_info['filename']
            })
        
        return formatted_fields
