#!/usr/bin/env python3
import os
import sys
import regex
import random
import pickle
import hashlib
import time

# -----------------------
# Regex Definitions
# -----------------------

# Revised regex that extracts a function definition including an optional preceding comment.
# It matches an optional comment block (or line comments) immediately preceding the function signature.
FUNC_REGEX = regex.compile(r'''
(?P<full>
    ^\s*                                   # Start-of-line optional whitespace
    (?P<comment>(?:/\*.*?\*/\s*|//.*?\n\s*)*)  # Optional preceding comments (block or line)
    (?:static\s+)?                         # Optional "static" keyword
    (?:inline\s+)?                         # Optional "inline" keyword
    (?P<ret>[a-zA-Z_][a-zA-Z0-9_\*\s]+?)\s+  # Return type (non-greedy)
    (?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\s*      # Function name
    \([^)]*\)\s*                           # Parameter list (anything until the first ')')
    \{                                     # Opening brace of function body
    (?:                                    # Non-capturing group for body content:
         [^{}]*                           #   Any characters except braces
         (?:\{[^{}]*\}[^{}]*)*             #   Optionally one level of nested braces
    )
    \}                                     # Closing brace of function body
)
''', regex.MULTILINE | regex.VERBOSE | regex.DOTALL)

# Simple regex to capture potential function calls (naïve approach)
CALL_REGEX = regex.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')
EXCLUDE_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof"}

# -----------------------
# Extraction Functions
# -----------------------

def extract_functions_from_source(source):
    """
    Given complete C source code as a string, return a dictionary mapping
    function names to their full source code (including any immediately preceding comments).
    If regex matching times out (after 1 second), skip this file.
    """
    functions = {}
    try:
        for match in FUNC_REGEX.finditer(source, timeout=1.0):
            func_name = match.group('name')
            func_source = match.group('full')
            functions[func_name] = func_source
    except TimeoutError:
        print("  Regex matching timed out on this file. Skipping function extraction.")
        return {}
    return functions

def find_called_functions(func_source):
    """
    Given a function's source code, return a set of names that appear to be called.
    """
    calls = CALL_REGEX.findall(func_source)
    return {name for name in calls if name not in EXCLUDE_KEYWORDS}

def find_c_files(path):
    """
    Given a directory, recursively find all files with .c or .h extension.
    """
    c_files = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.lower().endswith(('.c', '.h')):
                c_files.append(os.path.join(root, file))
    return c_files

def build_functions_dict(path):
    """
    Process a single file or all .c/.h files in a directory, and return a dictionary
    mapping function names to a tuple: (function source, filepath).
    Prints a START message when beginning and a FINISHED message (with elapsed time)
    when done processing each file.
    """
    all_functions = {}
    if os.path.isfile(path):
        files = [path]
    elif os.path.isdir(path):
        files = find_c_files(path)
    else:
        print(f"Invalid path: {path}")
        sys.exit(1)
    
    if not files:
        print(f"No .c/.h files found in {path}")
        sys.exit(1)
    
    total_files = len(files)
    print(f"Processing {total_files} file(s)...\n")
    for idx, filepath in enumerate(files, start=1):
        print(f"[{idx}/{total_files}] START processing: {filepath}")
        start_time = time.time()
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            continue

        funcs = extract_functions_from_source(source)
        if funcs:
            print(f"  Found {len(funcs)} function(s) in this file.")
        for name, code in funcs.items():
            # For simplicity, if a function name appears more than once, keep the first occurrence.
            if name not in all_functions:
                all_functions[name] = (code, filepath)
        elapsed = time.time() - start_time
        print(f"[{idx}/{total_files}] FINISHED processing: {filepath} in {elapsed:.2f} seconds.\n")
    return all_functions

# -----------------------
# Caching Helpers
# -----------------------

def get_cache_path(repo_path):
    """
    Compute a cache filename based on the repository path.
    Cache file is stored in a .cache folder relative to the current directory.
    """
    cache_dir = ".cache"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    repo_abs = os.path.abspath(repo_path)
    repo_hash = hashlib.md5(repo_abs.encode('utf-8')).hexdigest()
    cache_filename = f"funcs_cache_{repo_hash}.pkl"
    return os.path.join(cache_dir, cache_filename)

def load_cache(cache_path):
    """Load the cached function dictionary from the given path, if it exists."""
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)
            print(f"Loaded cache from {cache_path}")
            return data
        except Exception as e:
            print(f"Failed to load cache: {e}")
    return None

def save_cache(cache_path, data):
    """Save the function dictionary to the given cache path."""
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(data, f)
        print(f"Saved cache to {cache_path}")
    except Exception as e:
        print(f"Failed to save cache: {e}")

def get_code_tree(cnt, repo_path):
    """
    Returns a list of 'cnt' specimens from the repository.
    
    Each specimen is a dictionary with the following keys:
      - "functionName": the name of the function
      - "source": the full source code (including any immediately preceding comments)
      - "file": the file path where the function was found
      - "calledFunctions": a list of dictionaries for each function that is called
         within the function body (one level deep). Each sub-dictionary contains:
             "functionName", "source", "file"
    
    If repo_path is not provided, DEFAULT_REPO_PATH is used.
    """
    cache_path = get_cache_path(repo_path)
    functions = load_cache(cache_path)
    if functions is None:
        print("Cache not found or failed to load; scanning repository...")
        functions = build_functions_dict(repo_path)
        save_cache(cache_path, functions)
    else:
        print(f"Using cached data with {len(functions)} functions.\n")
    
    if not functions:
        print("No functions with bodies were found.")
        return []
    
    # Helper to build a specimen dictionary from a function name.
    def get_specimen(name):
        code, filepath = functions[name]
        calls = find_called_functions(code)
        called_specimens = []
        for call in calls:
            if call in functions:
                call_code, call_filepath = functions[call]
                called_specimens.append({
                    "functionName": call,
                    "source": call_code,
                    "file": call_filepath
                })
        return {
            "functionName": name,
            "source": code,
            "file": filepath,
            "calledFunctions": called_specimens
        }
    
    keys = list(functions.keys())
    if cnt >= len(keys):
        selected_keys = keys
    else:
        selected_keys = random.sample(keys, cnt)
    specimens = [get_specimen(name) for name in selected_keys]
    return specimens

# -----------------------
# Command-line Execution
# -----------------------

def main(path):
    cache_path = get_cache_path(path)
    functions = load_cache(cache_path)
    if functions is None:
        print("Cache not found or failed to load; scanning repository...")
        functions = build_functions_dict(path)
        save_cache(cache_path, functions)
    else:
        print(f"Using cached data with {len(functions)} functions.\n")
        
    if not functions:
        print("No functions with bodies were found.")
        sys.exit(0)

    print(f"\nTotal functions found: {len(functions)}\n")
    parent_func = random.choice(list(functions.keys()))
    parent_source, parent_file = functions[parent_func]
    print(f"Selected function: {parent_func} (from {parent_file})\n")
    print("== Function Source ==")
    print(parent_source)
    print("\n== Invoked Functions (with extracted source, if available) ==")
    called = find_called_functions(parent_source)
    for cf in called:
        if cf in functions:
            src, fname = functions[cf]
            print(f"\n--- {cf} (from {fname}) ---")
            print(src)
        else:
            print(f"\n--- {cf} (source not found) ---")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path_to_c_source_or_directory>")
        sys.exit(1)
    main(sys.argv[1])
