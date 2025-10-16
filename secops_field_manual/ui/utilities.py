import json
import os
import re
import sys
from collections import deque

# --- Config File Management ---
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".secops_field_manual_config.json")
MAX_HISTORY_SIZE = 10 # Max number of recent searches to remember

def _load_config():
    """A private helper to load the entire JSON config file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            # Return an empty dict if the file is empty
            content = f.read()
            if not content:
                return {}
            return json.loads(content)
    except (IOError, json.JSONDecodeError):
        return {}

def _save_config(config_data):
    """A private helper to save the entire JSON config file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        print(f"Error saving config file: {e}")

# --- Last DB Path ---
def save_last_db_path(db_path):
    config = _load_config()
    config['last_db_path'] = db_path
    _save_config(config)

def load_last_db_path():
    config = _load_config()
    return config.get("last_db_path")

# --- Saved Searches ---
def load_saved_searches():
    """Loads the dictionary of saved searches."""
    config = _load_config()
    return config.get("saved_searches", {})

def save_searches(searches_dict):
    """Saves the dictionary of saved searches."""
    config = _load_config()
    config['saved_searches'] = searches_dict
    _save_config(config)

# --- Search History ---
def load_search_history():
    """Loads the list of recently used search names."""
    config = _load_config()
    return config.get("search_history", [])

def record_search_in_history(search_name):
    """Adds a search to the top of the history list."""
    config = _load_config()
    history = deque(config.get("search_history", []), maxlen=MAX_HISTORY_SIZE)
    
    if search_name in history:
        history.remove(search_name)
    history.appendleft(search_name)
    
    config['search_history'] = list(history)
    _save_config(config)

# --- Parser ---
def parse_search_query(query_text):
    query_parts = {"positive": [], "negative": [], "exact": [], "filters": {}}
    filter_pattern = re.compile(r'(-)?(\w+):("([^"]+)"|(\S+))')
    general_text = filter_pattern.sub('', query_text)
    for match in filter_pattern.finditer(query_text):
        negation, key, _, quoted_value, unquoted_value = match.groups()
        value_str = quoted_value if quoted_value is not None else unquoted_value
        key = key.lower()
        if key not in query_parts["filters"]:
            query_parts["filters"][key] = []
        values = [v.strip() for v in value_str.split(',') if v.strip()]
        for value in values:
            final_value = f"-{value}" if negation or value.startswith('-') else value
            query_parts["filters"][key].append(final_value)
    exact_phrases = re.findall(r'"([^"]+)"', general_text)
    query_parts["exact"] = exact_phrases
    general_text = re.sub(r'"([^"]+)"', '', general_text)
    words = general_text.split()
    for word in words:
        if word.startswith('-') and len(word) > 1:
            query_parts["negative"].append(word[1:])
        elif word:
            query_parts["positive"].append(word)
    return query_parts

def resource_path(relative_path):
    """Get the absolute path to a resource, working for both dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))
    return os.path.join(base_path, relative_path)

def save_zoom_level(zoom_level):
    """Saves the current zoom level to the config file."""
    config = _load_config()
    config["zoom_level"] = zoom_level
    _save_config(config)

def load_zoom_level():
    """Loads the zoom level from the config file, defaulting to 0."""
    config = _load_config()
    return config.get("zoom_level", 0)
