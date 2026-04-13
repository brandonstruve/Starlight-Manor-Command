import os
import urllib.parse
from tkinter import filedialog, Tk

def clean_filenames():
    # Initialize Tkinter and hide the root window
    root = Tk()
    root.withdraw()

    # 1. Choose the folder
    folder_path = filedialog.askdirectory(title="Select Folder to Clean Filenames")
    
    if not folder_path:
        print("No folder selected. Exiting.")
        return

    print(f"Processing folder: {folder_path}")

    # 2. Iterate through files
    for filename in os.listdir(folder_path):
        # Skip directories
        old_file_path = os.path.join(folder_path, filename)
        if os.path.isdir(old_file_path):
            continue

        # 3. Perform the cleanup
        # unquote handles %20 -> space and other URL encoded characters
        new_name = urllib.parse.unquote(filename)
        
        # Optional: Add any additional surgical string replacements here
        # e.g., new_name = new_name.replace(' - ', '-') 

        if new_name != filename:
            new_file_path = os.path.join(folder_path, new_name)
            
            # 4. Rename with a safety check
            try:
                os.rename(old_file_path, new_file_path)
                print(f"Renamed: {filename} -> {new_name}")
            except OSError as e:
                print(f"Error renaming {filename}: {e}")

    print("Cleanup complete.")

if __name__ == "__main__":
    clean_filenames()