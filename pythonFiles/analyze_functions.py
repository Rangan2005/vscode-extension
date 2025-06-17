import sys
import os
import ast
import json

class FunctionCounter:
    """Recursively scan a directory and count top-level functions in .py files."""
    def __init__(self, base_path):
        self.base_path = base_path

    def count_in_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                node = ast.parse(f.read(), filename=file_path)
        except (SyntaxError, UnicodeDecodeError):
            return None
        count = sum(isinstance(n, ast.FunctionDef) for n in node.body)
        return count

    def scan(self):
        result = {}
        for root, dirs, files in os.walk(self.base_path):
            rel_root = os.path.relpath(root, self.base_path)
            for fname in files:
                if fname.endswith('.py'):
                    full_path = os.path.join(root, fname)
                    count = self.count_in_file(full_path)
                    if count is None:
                        continue
                    if rel_root == '.' or rel_root == '':
                        rel_path = fname
                    else:
                        rel_path = os.path.join(rel_root, fname)
                    result[rel_path] = count
        return result

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No folder path provided"}))
        sys.exit(1)
    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print(json.dumps({"error": f"Not a directory: {folder}"}))
        sys.exit(1)
    counter = FunctionCounter(folder)
    data = counter.scan()
    print(json.dumps(data))

if __name__ == "__main__":
    main()