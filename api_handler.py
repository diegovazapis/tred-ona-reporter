import requests
import pandas as pd
import warnings

class OnaAPIHandler:
    def __init__(self, api_token, form_id=None):
        self.api_token = api_token
        self.form_id = form_id
        self.base_url = "https://api.ona.io/api/v1"

    def query_filtered_data(self, form_id=None, filters=None, columns=None, limit=None):
        """
        Query data with dynamic filters (real-time consultation).
        
        This method queries ONA API in real-time without downloading the entire dataset.
        Filters are applied client-side as ONA API has limited server-side filtering.
        
        Args:
            form_id: ID of the form to query (uses self.form_id if None)
            filters: Dict with filters (e.g., {'cliente': 'ACME', 'sitio': 'Site1'})
            columns: List of columns to return (None = all)
            limit: Maximum number of records to return (None = all matching filters)
        
        Returns:
            Filtered DataFrame
        
        Example:
            handler = OnaAPIHandler(token, form_id)
            df = handler.query_filtered_data(
                filters={'grupo_cliente/Cliente': 'ACME'},
                columns=['Cliente', 'Sitio', 'fecha'],
                limit=100
            )
        """
        fid = form_id or self.form_id
        if not fid:
            raise ValueError("form_id must be provided either in constructor or as parameter")
        
        headers = {"Authorization": f"Token {self.api_token}"}
        url = f"{self.base_url}/data/{fid}"
        
        try:
            # Fetch data from ONA
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            
            # Apply client-side filters
            if filters:
                for column, value in filters.items():
                    if column in df.columns:
                        # Support both exact match and partial match (case-insensitive)
                        if isinstance(value, str):
                            df = df[df[column].astype(str).str.contains(value, case=False, na=False)]
                        else:
                            df = df[df[column] == value]
            
            # Apply column selection
            if columns:
                available_cols = [col for col in columns if col in df.columns]
                if available_cols:
                    df = df[available_cols]
            
            # Apply limit
            if limit and len(df) > limit:
                df = df.head(limit)
            
            return df
            
        except Exception as e:
            print(f"Error querying filtered data from ONA: {e}")
            return pd.DataFrame()

    def query_multi_forms(self, form_ids, filters=None, forms_metadata=None):
        """
        Query data from multiple forms with filters (real-time consultation).
        
        This replaces get_batch_data() with filtered, on-demand querying.
        
        Args:
            form_ids: List of form IDs to query
            filters: Dict with filters to apply to all forms
            forms_metadata: Dict mapping form_id to form_title
        
        Returns:
            Concatenated DataFrame with 'source_form_id' and 'source_form_title' columns
        """
        all_data = []
        
        for fid in form_ids:
            try:
                df = self.query_filtered_data(form_id=fid, filters=filters)
                
                if not df.empty:
                    # Tag source form
                    df['source_form_id'] = fid
                    if forms_metadata and fid in forms_metadata:
                        df['source_form_title'] = forms_metadata[fid]
                    all_data.append(df)
                    
            except Exception as e:
                print(f"Error querying form {fid}: {e}")
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()

    def get_unique_values(self, form_id, column_name, filters=None):
        """
        Get unique values from a specific column (optimized for dropdowns/selectors).
        
        This is useful for building dynamic filters without downloading full dataset.
        
        Args:
            form_id: ID of the form
            column_name: Name of the column to get unique values from
            filters: Optional filters to apply before getting unique values
        
        Returns:
            Sorted list of unique values
        """
        df = self.query_filtered_data(
            form_id=form_id,
            filters=filters,
            columns=[column_name]
        )
        
        if not df.empty and column_name in df.columns:
            return sorted(df[column_name].dropna().unique().tolist())
        
        return []

    # ==========================================
    # DEPRECATED METHODS (Maintained for backward compatibility)
    # ==========================================

    def get_data(self):
        """
        DEPRECATED: Use query_filtered_data() instead.
        
        Fetches ALL data from ONA.io for the specific form.
        This method downloads the entire dataset which may stress the server.
        """
        warnings.warn(
            "get_data() is deprecated and downloads entire datasets. "
            "Use query_filtered_data() for efficient, filtered queries.",
            DeprecationWarning,
            stacklevel=2
        )
        
        headers = {"Authorization": f"Token {self.api_token}"}
        url = f"{self.base_url}/data/{self.form_id}"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return pd.DataFrame(data)
        except Exception as e:
            print(f"Error fetching data from ONA: {e}")
            return pd.DataFrame()

    def get_form_schema(self, form_id=None):
        """
        Fetches the form definition (schema) to understand structure.
        """
        headers = {"Authorization": f"Token {self.api_token}"}
        
        fid = form_id or self.form_id
        if not fid:
            return {}
            
        url = f"{self.base_url}/forms/{fid}/form.json"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching schema for {fid}: {e}")
            return {}

    def get_user_forms(self):
        """
        Fetches ALL forms accessible by the user.
        This only fetches metadata (form list), not actual data, so it's efficient.
        """
        headers = {"Authorization": f"Token {self.api_token}"}
        url = f"{self.base_url}/forms"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching user forms: {e}")
            return []

    def get_batch_data(self, form_ids, forms_metadata=None):
        """
        DEPRECATED: Use query_multi_forms() instead.
        
        Fetches ALL data for multiple form IDs and concatenates them.
        This method downloads entire datasets which may stress the server.
        """
        warnings.warn(
            "get_batch_data() is deprecated and downloads entire datasets. "
            "Use query_multi_forms() for efficient, filtered queries.",
            DeprecationWarning,
            stacklevel=2
        )
        
        all_data = []
        for fid in form_ids:
            try:
                headers = {"Authorization": f"Token {self.api_token}"}
                url = f"{self.base_url}/data/{fid}"
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if data:
                    df = pd.DataFrame(data)
                    df['source_form_id'] = fid
                    if forms_metadata and fid in forms_metadata:
                        df['source_form_title'] = forms_metadata[fid]
                    all_data.append(df)
            except Exception as e:
                print(f"Error fetching batch data for {fid}: {e}")
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()
