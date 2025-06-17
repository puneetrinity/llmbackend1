#!/usr/bin/env python3
"""
SQLAlchemy text() Auto-Fixer Script
===================================
Automatically fixes SQLAlchemy 2.0 compatibility issues by:
1. Adding missing 'from sqlalchemy import text' imports
2. Wrapping raw SQL strings in execute() calls with text()

Usage:
    python fix_sqlalchemy_text.py [directory_path]

Example:
    python fix_sqlalchemy_text.py .
    python fix_sqlalchemy_text.py app/
"""

import os
import re
import sys
import shutil
import argparse
from pathlib import Path
from typing import List, Tuple, Set
from datetime import datetime

class SQLAlchemyTextFixer:
    def __init__(self, dry_run: bool = False, backup: bool = True):
        self.dry_run = dry_run
        self.backup = backup
        self.files_processed = 0
        self.files_modified = 0
        self.changes_made = []
        
        # Patterns to match execute calls with raw SQL
        self.execute_patterns = [
            # session.execute("SELECT ...")
            r'(\w+\.execute\s*\(\s*)([\"\'])([^\"\']+)\2(\s*\))',
            # session.execute(f"SELECT ...")  
            r'(\w+\.execute\s*\(\s*)(f[\"\'])([^\"\']+)\2(\s*\))',
            # await session.execute("SELECT ...")
            r'(await\s+\w+\.execute\s*\(\s*)([\"\'])([^\"\']+)\2(\s*\))',
            # await session.execute(f"SELECT ...")
            r'(await\s+\w+\.execute\s*\(\s*)(f[\"\'])([^\"\']+)\2(\s*\))',
        ]
        
        # Pattern to detect if text import already exists
        self.text_import_pattern = r'from\s+sqlalchemy\s+import\s+.*\btext\b'
        self.sqlalchemy_import_pattern = r'from\s+sqlalchemy\s+import\s+'
        
    def is_python_file(self, filepath: Path) -> bool:
        """Check if file is a Python file"""
        return filepath.suffix == '.py' and not filepath.name.startswith('.')
    
    def has_sqlalchemy_execute(self, content: str) -> bool:
        """Check if file contains SQLAlchemy execute calls"""
        execute_indicators = [
            '.execute(',
            'session.execute',
            'conn.execute',
            'connection.execute'
        ]
        return any(indicator in content for indicator in execute_indicators)
    
    def has_text_import(self, content: str) -> bool:
        """Check if file already imports text from sqlalchemy"""
        return bool(re.search(self.text_import_pattern, content, re.MULTILINE))
    
    def add_text_import(self, content: str) -> Tuple[str, bool]:
        """Add text import to existing sqlalchemy imports or create new one"""
        lines = content.split('\n')
        modified = False
        
        # First, try to add to existing sqlalchemy import
        for i, line in enumerate(lines):
            if re.search(self.sqlalchemy_import_pattern, line):
                # Check if text is already imported
                if 'text' not in line:
                    # Add text to existing import
                    if line.rstrip().endswith(')'):
                        # Multi-line import
                        lines[i] = line.replace(')', ', text)')
                    else:
                        # Single line import
                        lines[i] = line.rstrip() + ', text'
                    modified = True
                    self.changes_made.append(f"Added 'text' to existing sqlalchemy import on line {i+1}")
                break
        else:
            # No existing sqlalchemy import found, add new one
            # Find the best place to add import (after other imports)
            import_section_end = 0
            for i, line in enumerate(lines):
                if line.startswith('from ') or line.startswith('import '):
                    import_section_end = i + 1
                elif line.strip() == '':
                    continue
                else:
                    break
            
            # Insert new import
            lines.insert(import_section_end, 'from sqlalchemy import text')
            modified = True
            self.changes_made.append(f"Added new 'from sqlalchemy import text' import at line {import_section_end + 1}")
        
        return '\n'.join(lines), modified
    
    def fix_execute_calls(self, content: str) -> Tuple[str, bool]:
        """Fix execute calls by wrapping SQL strings with text()"""
        modified_content = content
        modified = False
        
        for pattern in self.execute_patterns:
            def replace_execute(match):
                nonlocal modified
                prefix = match.group(1)  # session.execute(
                quote_type = match.group(2)  # " or ' or f" or f'
                sql_content = match.group(3)  # SQL content
                suffix = match.group(4)  # )
                
                # Skip if already wrapped with text()
                if 'text(' in prefix:
                    return match.group(0)
                
                # Handle f-strings
                if quote_type.startswith('f'):
                    new_call = f'{prefix}text(f{quote_type[1:]}{sql_content}{quote_type[1:]}){suffix}'
                else:
                    new_call = f'{prefix}text({quote_type}{sql_content}{quote_type}){suffix}'
                
                modified = True
                return new_call
            
            modified_content = re.sub(pattern, replace_execute, modified_content)
        
        return modified_content, modified
    
    def backup_file(self, filepath: Path) -> Path:
        """Create backup of original file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = filepath.with_suffix(f'.backup_{timestamp}{filepath.suffix}')
        shutil.copy2(filepath, backup_path)
        return backup_path
    
    def process_file(self, filepath: Path) -> bool:
        """Process a single Python file"""
        try:
            print(f"📄 Processing: {filepath}")
            
            # Read file content
            with open(filepath, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            self.files_processed += 1
            
            # Check if file needs processing
            if not self.has_sqlalchemy_execute(original_content):
                print(f"   ⏭️  Skipped (no SQLAlchemy execute calls)")
                return False
            
            content = original_content
            file_modified = False
            self.changes_made = []  # Reset for this file
            
            # Add text import if missing
            if not self.has_text_import(content):
                content, import_added = self.add_text_import(content)
                if import_added:
                    file_modified = True
            
            # Fix execute calls
            content, execute_fixed = self.fix_execute_calls(content)
            if execute_fixed:
                file_modified = True
                self.changes_made.append("Wrapped raw SQL strings with text()")
            
            if file_modified:
                if self.dry_run:
                    print(f"   🔍 DRY RUN - Would modify:")
                    for change in self.changes_made:
                        print(f"      • {change}")
                else:
                    # Create backup if requested
                    if self.backup:
                        backup_path = self.backup_file(filepath)
                        print(f"   💾 Backup created: {backup_path}")
                    
                    # Write modified content
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"   ✅ Modified:")
                    for change in self.changes_made:
                        print(f"      • {change}")
                
                self.files_modified += 1
                return True
            else:
                print(f"   ✨ Already correct (no changes needed)")
                return False
                
        except Exception as e:
            print(f"   ❌ Error processing {filepath}: {e}")
            return False
    
    def scan_directory(self, directory: Path) -> List[Path]:
        """Scan directory for Python files"""
        python_files = []
        
        for root, dirs, files in os.walk(directory):
            # Skip common directories we don't want to process
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', '.pytest_cache', 'venv', 'env', 'node_modules'}]
            
            for file in files:
                filepath = Path(root) / file
                if self.is_python_file(filepath):
                    python_files.append(filepath)
        
        return python_files
    
    def run(self, target_path: Path) -> None:
        """Run the fixer on target path"""
        print(f"🚀 SQLAlchemy text() Auto-Fixer")
        print(f"📁 Target: {target_path.absolute()}")
        print(f"🔧 Mode: {'DRY RUN' if self.dry_run else 'MODIFY FILES'}")
        print(f"💾 Backup: {'Yes' if self.backup else 'No'}")
        print("-" * 60)
        
        if target_path.is_file():
            # Process single file
            if self.is_python_file(target_path):
                self.process_file(target_path)
            else:
                print(f"❌ Not a Python file: {target_path}")
                return
        else:
            # Process directory
            python_files = self.scan_directory(target_path)
            
            if not python_files:
                print("❌ No Python files found in directory")
                return
            
            print(f"📊 Found {len(python_files)} Python files")
            print("-" * 60)
            
            for filepath in python_files:
                self.process_file(filepath)
        
        print("-" * 60)
        print(f"📈 Summary:")
        print(f"   📄 Files processed: {self.files_processed}")
        print(f"   ✅ Files modified: {self.files_modified}")
        
        if self.dry_run:
            print(f"\n🔍 This was a dry run. Use --no-dry-run to actually modify files.")
        elif self.files_modified > 0:
            print(f"\n🎉 Successfully fixed SQLAlchemy text() issues!")
            if self.backup:
                print(f"💾 Original files backed up with .backup_* extension")

def main():
    parser = argparse.ArgumentParser(
        description="Fix SQLAlchemy 2.0 text() compatibility issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fix_sqlalchemy_text.py .                    # Fix all files in current directory
  python fix_sqlalchemy_text.py app/                 # Fix all files in app/ directory
  python fix_sqlalchemy_text.py file.py              # Fix specific file
  python fix_sqlalchemy_text.py . --no-dry-run       # Actually modify files
  python fix_sqlalchemy_text.py . --no-backup        # Don't create backups
        """
    )
    
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Path to directory or file to process (default: current directory)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Show what would be changed without modifying files (default: True)'
    )
    
    parser.add_argument(
        '--no-dry-run',
        dest='dry_run',
        action='store_false',
        help='Actually modify files (disable dry run)'
    )
    
    parser.add_argument(
        '--no-backup',
        dest='backup',
        action='store_false',
        default=True,
        help='Do not create backup files'
    )
    
    args = parser.parse_args()
    
    target_path = Path(args.path)
    
    if not target_path.exists():
        print(f"❌ Path does not exist: {target_path}")
        sys.exit(1)
    
    # Create fixer and run
    fixer = SQLAlchemyTextFixer(dry_run=args.dry_run, backup=args.backup)
    fixer.run(target_path)

if __name__ == "__main__":
    main()