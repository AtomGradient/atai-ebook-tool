import argparse
import json
import os
import re
from atai_ebook_tool import parser

def sanitize_filename(name):
    """
    Sanitize folder name by replacing characters not allowed in filenames.
    """
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def main():
    arg_parser = argparse.ArgumentParser(
        description="Parse an ebook (e.g., EPUB, MOBI) and output a JSON file along with extracted images."
    )
    arg_parser.add_argument(
        "ebook", help="Path to the ebook file (e.g., ebook.epub, ebook.mobi)"
    )
    arg_parser.add_argument(
        "-o", "--output", default="output.json", help="Filename for the JSON output (will be placed in the book folder)"
    )
    args = arg_parser.parse_args()

    try:
        ebook_data = parser.parse_ebook(args.ebook)
    except Exception as e:
        print(f"Error parsing ebook: {e}")
        exit(1)

    # Create a folder named after the book title.
    book_title = ebook_data.get("title", "Unknown_Book")
    folder_name = sanitize_filename(book_title)
    os.makedirs(folder_name, exist_ok=True)

    # Create an "images" subfolder inside the book folder.
    images_folder = os.path.join(folder_name, "images")
    os.makedirs(images_folder, exist_ok=True)

    # Remove images from ebook_data for JSON dump (they're saved as separate files)
    images = ebook_data.pop("images", {})

    # Write output JSON into the book folder.
    output_json_path = os.path.join(folder_name, os.path.basename(args.output))
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(ebook_data, f, ensure_ascii=False, indent=4)
    print(f"Successfully wrote JSON output to {output_json_path}")

    # Save extracted images into the images folder.
    for filename, content in images.items():
        image_path = os.path.join(images_folder, filename)
        with open(image_path, "wb") as img_file:
            img_file.write(content)
            # print(f"Wrote image {filename} to {image_path}")

if __name__ == "__main__":
    main()
