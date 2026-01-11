import sqlite3
import os
from datetime import datetime
import re
import sys
from ..ui.constants import MITRE_ATTACK_TACTICS
from ..ui.error_handler import safe_db_operation

def get_default_db_path(folder_name, file_name):
    """
    Determines the correct location for the DB file, prioritizing
    the user's Documents folder, and creates the directory if necessary.
    """
    try:
        home = os.path.expanduser("~")
        documents_path = os.path.join(home, 'Documents')
        
        if not os.path.isdir(documents_path):
            documents_path = home
            
        db_dir = os.path.join(documents_path, folder_name)
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, file_name)
    except Exception as e:
        print(f"Error determining default DB path: {e}", file=sys.stderr)
        return file_name

@safe_db_operation
def init_db(db_file):
    """Initializes the database, adding the new artifact columns."""
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            description TEXT,
            artifact_type TEXT,
            artifact_value TEXT,
            content_modified_at TEXT,
            added_at TEXT,
            source TEXT,
            image_path TEXT,
            os TEXT,
            mitre TEXT,
            notes TEXT,
            resources TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL COLLATE NOCASE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS entry_tags (
            entry_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            FOREIGN KEY (entry_id) REFERENCES entries (id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE,
            PRIMARY KEY (entry_id, tag_id)
        )
    """)
    conn.commit()
    
    def add_column_if_not_exists(column_name, column_type):
        try:
            cur.execute(f"ALTER TABLE entries ADD COLUMN {column_name} {column_type}")
            conn.commit()
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e): raise e

    add_column_if_not_exists('artifact_type', 'TEXT')
    add_column_if_not_exists('artifact_value', 'TEXT')
    
    try:
        cur.execute("SELECT id, path FROM entries WHERE path IS NOT NULL AND path != '' AND artifact_value IS NULL")
        rows_to_migrate = cur.fetchall()
        if rows_to_migrate:
            print(f"Migrating {len(rows_to_migrate)} entries from old 'path' column...")
            for entry_id, path_value in rows_to_migrate:
                cur.execute("UPDATE entries SET artifact_type = 'File Path', artifact_value = ? WHERE id = ?", (path_value, entry_id))
            conn.commit()
    except sqlite3.OperationalError:
        pass

    conn.close()

def is_valid_sqlite_file(db_file):
    if not os.path.exists(db_file): return False
    try:
        with open(db_file, 'rb') as f:
            header = f.read(16)
        return header == b'SQLite format 3\x00'
    except IOError:
        return False

def check_db_schema(db_file):
    try:
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entries'")
        result = cur.fetchone()
        conn.close()
        return result is not None
    except sqlite3.DatabaseError:
        return False

def get_mitre_order(tags_string):
    if not tags_string: return ""
    selected_tags = {tag.strip() for tag in tags_string.split(',')}
    return ", ".join([tag for tag in MITRE_ATTACK_TACTICS if tag in selected_tags])

@safe_db_operation
def search_entries(db_file, parsed_query):
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    query = """
        SELECT DISTINCT e.id, e.title
        FROM entries e
        LEFT JOIN entry_tags et ON e.id = et.entry_id
        LEFT JOIN tags t ON et.tag_id = t.id
    """
    conditions = []
    params = []

    for field, values in parsed_query["filters"].items():
        for value in values:
            is_blank_search = value.lower() in ('blank', 'empty', 'null')
            
            column_map = {
                'artifact_value': 'e.artifact_value', 
                'artifact_type': 'e.artifact_type',
                'description': 'e.description', 
                'notes': 'e.notes', 
                'resources': 'e.resources', 
                'mitre': 'e.mitre', 
                'os': 'e.os', 
                'source': 'e.source'
            }

            if is_blank_search and field in column_map:
                col = column_map[field]
                conditions.append(f"({col} IS NULL OR {col} = '')")
                continue

            if field == "title":
                if value.startswith('-'):
                    title_val = value[1:].strip('"')
                    conditions.append("e.title NOT LIKE ?")
                    params.append(title_val)
                else:
                    title_val = value.strip('"')
                    conditions.append("e.title LIKE ?")
                    params.append(title_val)
            elif field == "tags":
                is_negative = value.startswith('-')
                tag_name = value[1:] if is_negative else value
                operator = "NOT IN" if is_negative else "IN"
                conditions.append(f"e.id {operator} (SELECT et.entry_id FROM entry_tags et JOIN tags t ON et.tag_id = t.id WHERE t.name LIKE ?)")
                params.append(f"%{tag_name}%")
            elif field in column_map:
                col = column_map[field]
                is_negative = value.startswith('-')
                val = value[1:] if is_negative else value
                operator = "NOT LIKE" if is_negative else "LIKE"
                conditions.append(f"{col} {operator} ?")
                params.append(f"%{val}%")
            elif field in ('added_after', 'added_before', 'modified_after', 'modified_before'):
                date_col = 'e.added_at' if 'added' in field else 'e.content_modified_at'
                operator = '>=' if 'after' in field else '<='
                conditions.append(f"DATE({date_col}) {operator} ?")
                params.append(value)

    for keyword in parsed_query["positive"]:
        kw = f"%{keyword}%"
        conditions.append("""
            (e.title LIKE ? OR e.description LIKE ? OR e.artifact_type LIKE ? OR e.artifact_value LIKE ? OR e.notes LIKE ? OR e.resources LIKE ? OR e.mitre LIKE ? OR
             e.id IN (SELECT et.entry_id FROM entry_tags et JOIN tags t ON et.tag_id = t.id WHERE t.name LIKE ?))
        """)
        params.extend([kw, kw, kw, kw, kw, kw, kw, kw])
        
    for keyword in parsed_query["negative"]:
        kw = f"%{keyword}%"
        conditions.append("""
            e.id NOT IN (SELECT id FROM entries WHERE title LIKE ? OR description LIKE ? OR artifact_type LIKE ? OR artifact_value LIKE ? OR notes LIKE ? OR resources LIKE ? OR mitre LIKE ?) AND 
            e.id NOT IN (SELECT et.entry_id FROM entry_tags et JOIN tags t ON et.tag_id = t.id WHERE t.name LIKE ?)
        """)
        params.extend([kw, kw, kw, kw, kw, kw, kw, kw])

    for phrase in parsed_query["exact"]:
        ph = f"%{phrase}%"
        conditions.append("(e.description LIKE ? OR e.notes LIKE ? OR e.resources LIKE ? OR e.artifact_value LIKE ?)")
        params.extend([ph, ph, ph, ph])
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY e.title COLLATE NOCASE ASC"
    
    cur.execute(query, tuple(params))
    results = cur.fetchall()
    conn.close()
    return results

@safe_db_operation
def get_tags_for_entry(db_file, entry_id):
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT t.name FROM tags t JOIN entry_tags et ON t.id = et.tag_id WHERE et.entry_id = ?", (entry_id,))
    tags = sorted([row[0] for row in cur.fetchall()], key=str.lower)
    conn.close()
    return tags

@safe_db_operation
def get_all_tags(db_file):
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM tags ORDER BY name COLLATE NOCASE")
    all_tags = cur.fetchall()
    conn.close()
    return all_tags

def _get_or_create_tag_id(cursor, tag_name):
    cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
        return cursor.lastrowid

safe_db_operation
def get_all_entries_for_export(db_file):
    """
    Fetches all entries and their tags, formatted for CSV export.
    Uses capitalized keys to match the CSV headers.
    """
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    try:
        # This query joins entries with their tags
        cur.execute("""
            SELECT 
                e.title, e.description, e.artifact_type, e.artifact_value, e.os, 
                e.mitre, e.notes, e.resources, e.content_modified_at,
                (SELECT GROUP_CONCAT(t.name, ', ') 
                 FROM tags t 
                 JOIN entry_tags et ON t.id = et.tag_id 
                 WHERE et.entry_id = e.id) as tags
            FROM entries e
            ORDER BY e.title COLLATE NOCASE
        """)
        
        # Manually create dictionaries with capitalized keys for the CSV
        entries_for_export = []
        for row in cur.fetchall():
            entries_for_export.append({
                "Title": row["title"],
                "Description": row["description"],
                "Artifact Type": row["artifact_type"],
                "Artifact Value": row["artifact_value"],
                "OS": row["os"],
                "MITRE": row["mitre"],
                "Tags": row["tags"],
                "Notes": row["notes"],
                "Resources": row["resources"],
                "Content Modified At": row["content_modified_at"]
            })
    finally:
        conn.close()
        
    return entries_for_export

@safe_db_operation
def get_database_summary(db_file):
    """Gathers various statistics about the current database."""
    summary = {}
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(id) FROM entries")
        summary['total_entries'] = cur.fetchone()[0]

        cur.execute("SELECT MAX(content_modified_at) FROM entries")
        last_update = cur.fetchone()[0]
        summary['last_update'] = last_update if last_update else "N/A"

        cur.execute("SELECT os, COUNT(id) FROM entries GROUP BY os")
        summary['os_counts'] = dict(cur.fetchall())

        cur.execute("SELECT COUNT(id) FROM entries WHERE artifact_value IS NULL OR artifact_value = ''")
        summary['empty_artifact_values'] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(id) FROM entries WHERE description IS NULL OR description = ''")
        summary['empty_descriptions'] = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(id) FROM entries WHERE image_path IS NOT NULL AND image_path != ''")
        summary['entries_with_images'] = cur.fetchone()[0]
        
        cur.execute("SELECT mitre FROM entries WHERE mitre IS NOT NULL AND mitre != ''")
        mitre_counts = {}
        for row in cur.fetchall():
            tactics = [t.strip() for t in row[0].split(',')]
            for tactic in tactics:
                if tactic: mitre_counts[tactic] = mitre_counts.get(tactic, 0) + 1
        summary['mitre_counts'] = mitre_counts

        cur.execute("SELECT t.name FROM tags t JOIN entry_tags et ON t.id = et.tag_id")
        tag_counts = {}
        for row in cur.fetchall():
            tag = row[0]
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        sorted_tags = sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
        summary['top_tags'] = sorted_tags[:5]
    finally:
        conn.close()
        
    return summary

@safe_db_operation
def insert_entry(db_file, title, description, artifact_type, artifact_value, image_path, os_val, mitre_val, notes, resources, tag_list, source, content_modified_at=None):
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    final_content_modified_at = content_modified_at if content_modified_at else now

    cur.execute("""
        INSERT INTO entries (title, description, artifact_type, artifact_value, content_modified_at, added_at, source, image_path, os, mitre, notes, resources)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, description, artifact_type, artifact_value, final_content_modified_at, now, source, image_path, os_val, mitre_val, notes, resources))
    
    new_entry_id = cur.lastrowid
    
    for tag_name in tag_list:
        tag_id = _get_or_create_tag_id(cur, tag_name)
        cur.execute("INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (new_entry_id, tag_id))
    
    conn.commit()
    conn.close()
    return True, new_entry_id

@safe_db_operation
def update_entry(db_file, entry_id, title, description, artifact_type, artifact_value, image_path, os_val, mitre_val, notes, resources, tag_list):
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    cur.execute("""
        UPDATE entries 
        SET title=?, description=?, artifact_type=?, artifact_value=?, content_modified_at=?, image_path=?, os=?, mitre=?, notes=?, resources=? 
        WHERE id=?
    """, (title, description, artifact_type, artifact_value, now, image_path, os_val, mitre_val, notes, resources, entry_id))
    
    cur.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
    for tag_name in tag_list:
        tag_id = _get_or_create_tag_id(cur, tag_name)
        cur.execute("INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (entry_id, tag_id))
    
    conn.commit()
    conn.close()

@safe_db_operation
def delete_entry(db_file, entry_id):
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("DELETE FROM entries WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()

@safe_db_operation
def rename_tag(db_file, tag_id, new_name):
    """Renames a tag. Decorator handles IntegrityError."""
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("UPDATE tags SET name = ? WHERE id = ?", (new_name, tag_id))
    conn.commit()
    conn.close()
    return True, ""

@safe_db_operation
def delete_tag(db_file, tag_id):
    """Deletes a tag. Decorator handles errors."""
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    conn.commit()
    conn.close()

@safe_db_operation
def get_all_tags_with_counts(db_path):
    """
    Returns a list of tuples (id, name, count) for all tags.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        # Assumes a schema where 'tags' has id, name and a linking table 'entry_tags'
        # Adjust table names if yours differ (e.g. if you store tags as strings in main table)
        
        # Option A: If you use a linking table (entries <-> tags)
        query = """
            SELECT t.id, t.name, COUNT(et.entry_id) as count
            FROM tags t
            LEFT JOIN entry_tags et ON t.id = et.tag_id
            GROUP BY t.id, t.name
            ORDER BY t.name
        """
        cur.execute(query)
        return cur.fetchall()
    except sqlite3.OperationalError:
        # Fallback if schema assumes tags are just in a 'tags' table without link count yet
        # or if specific table names differ. 
        cur.execute("SELECT id, name FROM tags ORDER BY name")
        tags = cur.fetchall()
        return [(t[0], t[1], 0) for t in tags] # Return 0 count if linking query fails
    finally:
        conn.close()

@safe_db_operation
def merge_tags(db_path, tag_ids_to_merge, new_tag_name):
    """
    Merges multiple tags into one.
    1. Gets or creates the 'target' tag ID for new_tag_name.
    2. Updates all entries using the old tag_ids to point to the target ID.
    3. Deletes the old tags.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        # 1. Find or Create Target Tag
        cur.execute("SELECT id FROM tags WHERE name = ?", (new_tag_name,))
        row = cur.fetchone()
        if row:
            target_id = row[0]
        else:
            cur.execute("INSERT INTO tags (name) VALUES (?)", (new_tag_name,))
            target_id = cur.lastrowid

        # 2. Re-link Entries
        # We need to be careful not to create duplicates in the entry_tags table
        # (i.e., if an entry is already tagged "Network" and we merge "net" into "Network",
        # we shouldn't try to add "Network" again, we should just remove "net").
        
        for old_id in tag_ids_to_merge:
            if old_id == target_id:
                continue
                
            # Get entries associated with the old tag
            cur.execute("SELECT entry_id FROM entry_tags WHERE tag_id = ?", (old_id,))
            entries_with_old_tag = [r[0] for r in cur.fetchall()]
            
            for entry_id in entries_with_old_tag:
                # Check if this entry already has the target tag
                cur.execute("SELECT 1 FROM entry_tags WHERE entry_id = ? AND tag_id = ?", (entry_id, target_id))
                already_has_target = cur.fetchone()
                
                if already_has_target:
                    # Just remove the old link
                    cur.execute("DELETE FROM entry_tags WHERE entry_id = ? AND tag_id = ?", (entry_id, old_id))
                else:
                    # Update the old link to point to the new tag
                    cur.execute("UPDATE entry_tags SET tag_id = ? WHERE entry_id = ? AND tag_id = ?", (target_id, entry_id, old_id))
            
            # 3. Delete the old tag definition
            cur.execute("DELETE FROM tags WHERE id = ?", (old_id,))

        conn.commit()
        return True, "Success"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()
