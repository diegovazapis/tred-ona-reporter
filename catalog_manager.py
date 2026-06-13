import json
import os
import pandas as pd
import io

class CatalogManager:
    
    def __init__(self, catalog_path="catalogo_equipos.json", projects_path="proyectos.json"):
        self.catalog_path = catalog_path
        self.projects_path = projects_path
        self.data = self.load_catalog()
        self.projects = self.load_projects()

    def load_catalog(self):
        if os.path.exists(self.catalog_path):
            try:
                with open(self.catalog_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading catalog: {e}")
                return {}
        return {}

    def load_projects(self):
        if os.path.exists(self.projects_path):
            try:
                with open(self.projects_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading projects: {e}")
                return {}
        return {}

    def save_catalog(self):
        try:
            with open(self.catalog_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving catalog: {e}")
            return False

    def save_projects(self):
        try:
            with open(self.projects_path, 'w', encoding='utf-8') as f:
                json.dump(self.projects, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving projects: {e}")
            return False

    def add_or_update_item(self, model_id, brand, short_desc, report_desc, specs_list, unidad="Pza", costo=0.0):
        """
        Updates a single equipment item.
        specs_list: list of strings (bullet points)
        """
        self.data[model_id] = {
            "marca": brand,
            "descripcion": short_desc,
            "descripcion_reporte": report_desc, 
            "caracteristicas": specs_list,
            "unidad_medida": unidad,
            "costo_unitario": float(costo)
        }
        return self.save_catalog()
    
    def add_or_update_project(self, project_id, client_name, scope_list, short_desc, conditions_list):
        """
        Updates a single project configuration.
        """
        self.projects[project_id] = {
            "cliente": client_name,
            "alcance": scope_list,
            "descripcion_breve": short_desc,
            "condiciones_comerciales": conditions_list
        }
        return self.save_projects()

    def delete_item(self, model_id):
        if model_id in self.data:
            del self.data[model_id]
            return self.save_catalog()
        return False
        
    def delete_project(self, project_id):
        if project_id in self.projects:
            del self.projects[project_id]
            return self.save_projects()
        return False

    def get_as_dataframe(self):
        """Convert JSON dict to DataFrame for UI display"""
        rows = []
        for model_id, info in self.data.items():
            row = {
                "ID (Modelo)": model_id,
                "Marca": info.get("marca", ""),
                "Unidad": info.get("unidad_medida", "Pza"),
                "Costo Unitario": info.get("costo_unitario", 0.0),
                "Descripción Corta": info.get("descripcion", ""),
                "Descripción Reporte": info.get("descripcion_reporte", ""),
                "Características (Sep. por |)": " | ".join(info.get("caracteristicas", []))
            }
            rows.append(row)
        return pd.DataFrame(rows)

    def get_projects_as_dataframe(self):
        """Convert Projects JSON to DataFrame"""
        rows = []
        for pid, info in self.projects.items():
            row = {
                "ID Proyecto": pid,
                "Cliente": info.get("cliente", ""),
                "Descripción Breve": info.get("descripcion_breve", ""),
                "Alcance (Sep. por |)": " | ".join(info.get("alcance", [])),
                "Condiciones (Sep. por |)": " | ".join(info.get("condiciones_comerciales", []))
            }
            rows.append(row)
        return pd.DataFrame(rows)

    def generate_template_excel(self):
        """Returns bytes of an empty Excel template for Equipos"""
        df = pd.DataFrame(columns=["ID (Modelo)", "Marca", "Unidad", "Costo Unitario", "Descripción Corta", "Descripción Reporte", "Características (Sep. por |)"])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()

    def process_bulk_upload(self, uploaded_file):
        """
        Reads Excel/CSV, validates, and merges into catalog.
        Returns (success_bool, message_string)
        """
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Normalize columns
            expected_cols = ["ID (Modelo)", "Marca", "Unidad", "Costo Unitario", "Descripción Corta", "Descripción Reporte", "Características (Sep. por |)"]
            if not all(col in df.columns for col in expected_cols):
                return False, f"Formato inválido. Columnas requeridas: {expected_cols}"
            
            count = 0
            for _, row in df.iterrows():
                model_id = str(row["ID (Modelo)"]).strip()
                if not model_id or pd.isna(model_id): continue
                
                specs_raw = str(row["Características (Sep. por |)"])
                specs_list = [s.strip() for s in specs_raw.split("|") if s.strip()]
                
                self.data[model_id] = {
                    "marca": str(row["Marca"]),
                    "unidad_medida": str(row.get("Unidad", "Pza")),
                    "costo_unitario": float(row.get("Costo Unitario", 0.0)),
                    "descripcion": str(row["Descripción Corta"]),
                    "descripcion_reporte": str(row["Descripción Reporte"]),
                    "caracteristicas": specs_list
                }
                count += 1
            
            self.save_catalog()
            return True, f"Se importaron/actualizaron {count} registros exitosamente."
            
        except Exception as e:
            return False, f"Error procesando archivo: {str(e)}"

    def validate_models(self, models_list):
        """
        Checks a list of model IDs.
        Returns: (valid_list, missing_list)
        """
        unique_models = set([str(m).strip() for m in models_list if pd.notna(m) and str(m).strip()])
        known_keys = set(self.data.keys())
        
        valid = list(unique_models.intersection(known_keys))
        missing = list(unique_models.difference(known_keys))
        return valid, missing
