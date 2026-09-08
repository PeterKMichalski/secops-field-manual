import csv
import os
import sqlite3
from datetime import datetime
from ..data.database import insert_entry, get_all_entries_for_export, get_mitre_order

def _open_csv_with_fallback(csv_path):
    """
    Tries to open a CSV file with multiple common encodings.
    """
    try:
        return open(csv_path, mode='r', encoding='utf-8-sig', newline='')
    except UnicodeDecodeError:
        try:
            return open(csv_path, mode='r', encoding='latin-1', newline='')
        except UnicodeDecodeError:
            raise IOError("Could not decode the file. Please ensure it is saved as UTF-8 or Latin-1.")

def compare_data_sources(current_entries_dict, external_entries_list):
    """
    Compares two data sources and categorizes entries.
    All dictionary keys and titles are normalized to lowercase.
    """
    comparison = {'new': [], 'conflicting': [], 'duplicates': []}
    
    content_keys = ['description', 'artifact_type', 'artifact_value', 'os', 'mitre', 'notes', 'resources', 'tags']

    for ext_entry in external_entries_list:
        # Normalize all keys from the external source to lowercase
        ext_entry_lower = {str(k).lower().replace(' ', '_'): v for k, v in ext_entry.items()}
        title = ext_entry_lower.get('title')
        if not title:
            continue

        if title.lower() not in current_entries_dict:
            comparison['new'].append(ext_entry_lower)
        else:
            is_duplicate = True
            curr_entry = current_entries_dict[title.lower()]
            
            for key in content_keys:
                curr_val = curr_entry.get(key) or ""
                ext_val = ext_entry_lower.get(key) or ""

                if key == 'tags':
                    curr_val = sorted([t.strip().lower() for t in (str(curr_val) or "").split(',') if t.strip()])
                    ext_val = sorted([t.strip().lower() for t in (str(ext_val) or "").split(',') if t.strip()])

                if str(curr_val).lower() != str(ext_val).lower():
                    is_duplicate = False
                    break
            
            if is_duplicate:
                comparison['duplicates'].append(ext_entry_lower)
            else:
                comparison['conflicting'].append(ext_entry_lower)

    return comparison

def perform_import(target_db_path, entries_to_add, source_filename):
    """
    Performs a merge/import operation for a list of entry dictionaries.
    """
    new_ids = []
    conn = sqlite3.connect(target_db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT title FROM entries")
        existing_titles = {row[0].lower() for row in cur.fetchall()}

        for entry in entries_to_add:
            title = entry.get('title')
            if not title: continue

            final_title = title
            if title.lower() in existing_titles:
                suffix_name = os.path.splitext(source_filename)[0].replace(' ', '_')
                copy_num = 1
                while True:
                    new_title = f"{title} [{suffix_name}_{copy_num}]"
                    if new_title.lower() not in existing_titles:
                        final_title = new_title
                        break
                    copy_num += 1
            
            mitre_raw = entry.get('mitre') or ''
            mitre_normalized = get_mitre_order(mitre_raw) if mitre_raw else ''
            mitre_val = mitre_normalized if mitre_normalized else mitre_raw

            success, new_id = insert_entry(
                target_db_path, final_title,
                entry.get('description',''),
                entry.get('artifact_type', 'Other'),
                entry.get('artifact_value',''),
                entry.get('image_path',''),
                entry.get('os',''),
                mitre_val,
                entry.get('notes',''),
                entry.get('resources',''),
                [t.strip() for t in (entry.get('tags') or "").split(',') if t.strip()],
                f"Merge from {source_filename}",
                entry.get('content_modified_at')
            )
            if success:
                new_ids.append(new_id)
                existing_titles.add(final_title.lower())
    finally:
        conn.close()
    return new_ids

def perform_bulk_import_from_csv(target_db_path, csv_path, source_filename):
    """
    High-performance bulk import from a CSV.
    """
    infile = _open_csv_with_fallback(csv_path)
    with infile:
        reader = csv.DictReader(infile)
        external_entries_list = list(reader)

    current_entries_list = get_all_entries_for_export(target_db_path) or []
    current_entries_dict = {
        entry['Title'].lower(): {k.lower().replace(' ', '_'): v for k, v in entry.items()}
        for entry in current_entries_list
    }

    comparison = compare_data_sources(current_entries_dict, external_entries_list)

    entries_to_add = comparison['new'] + comparison['conflicting']
    new_ids = perform_import(target_db_path, entries_to_add, source_filename)
    
    summary = {
        'inserted': len(comparison['new']),
        'conflicting': len(comparison['conflicting']),
        'skipped': len(comparison['duplicates']),
        'new_ids': new_ids
    }
    return summary

