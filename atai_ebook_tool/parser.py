import os
import shutil
import tempfile
import sys
import types
from bs4 import BeautifulSoup

class ImageCounter:
    def __init__(self):
        self.count = 1

def format_html_content(html_content, epub_images, image_mapping, image_counter):
    """
    Process HTML content:
      - Wraps annotations (<aside> tags or elements with class "annotation")
        in [note: ...].
      - Replaces each <img> tag with a standardized image source string using
        a sequential filename (e.g., src="../images/image_001.png").
      - Returns the cleaned text.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    body = soup.body if soup.body else soup

    # Process annotations: wrap <aside> tags
    for aside in body.find_all("aside"):
        note_text = aside.get_text(strip=True)
        aside.replace_with(f"[note: {note_text}]")
    # Also process any element with class "annotation"
    for tag in body.find_all(lambda tag: tag.has_attr("class") and "annotation" in tag.get("class", [])):
        note_text = tag.get_text(strip=True)
        tag.replace_with(f"[note: {note_text}]")

    # Process image tags: replace each <img> tag with standardized src
    for img in body.find_all("img"):
        original_src = img.get("src")
        if original_src:
            image_key = os.path.basename(original_src)
            if image_key in image_mapping:
                new_filename = image_mapping[image_key]
            else:
                new_filename = f"image_{image_counter.count:03}.png"
                image_counter.count += 1
                image_mapping[image_key] = new_filename
            # Replace the <img> tag with a standardized reference.
            new_img_str = f'src="../images/{new_filename}"'
            img.replace_with(new_img_str)

    formatted_text = body.get_text(separator="\n").strip()
    return formatted_text

def parse_epub(file_path):
    """
    Parses an EPUB file and returns a dictionary with metadata, chapter-wise
    content, and a mapping of new image filenames to binary content.

    - Chapters are stored as keys: "chapter 1", "chapter 2", etc.
    - All images referenced in the chapters are extracted from the EPUB.
    """
    try:
        from ebooklib import epub
    except ImportError:
        raise ImportError("ebooklib is required for parsing EPUB files. Install it via 'pip install ebooklib'.")

    book = epub.read_epub(file_path)

    # Extract basic metadata
    title_meta = book.get_metadata('DC', 'title')
    title = title_meta[0][0] if title_meta else "Unknown Title"

    author_meta = book.get_metadata('DC', 'creator')
    author = author_meta[0][0] if author_meta else "Unknown Author"

    # Build dictionary of image items from the EPUB.
    epub_images = {}
    for item in book.get_items():
        # Instead of using ITEM_IMAGE, check if media_type starts with "image/"
        if hasattr(item, "media_type") and item.media_type and item.media_type.startswith("image/"):
            key = os.path.basename(item.file_name)
            epub_images[key] = item.content

    image_mapping = {}  # Maps original image basename -> new filename (e.g., "cover.jpg" -> "image_001.png")
    image_counter = ImageCounter()

    # Process chapters: each EpubHtml item is treated as a separate chapter.
    chapters = {}
    chapter_counter = 1
    for item in book.get_items():
        if isinstance(item, epub.EpubHtml):
            try:
                content = item.get_content().decode("utf-8")
            except AttributeError:
                content = item.get_content()
            formatted = format_html_content(content, epub_images, image_mapping, image_counter)
            chapters[f"chapter {chapter_counter}"] = formatted
            chapter_counter += 1

    # Build new_images mapping: new filename -> binary content.
    new_images = {}
    for orig, new_filename in image_mapping.items():
        if orig in epub_images:
            new_images[new_filename] = epub_images[orig]

    return {
        "title": title,
        "author": author,
        "chapters": chapters,
        "images": new_images
    }


def parse_mobi(file_path):
    """
    Parses a MOBI file using the 'mobi' library (a fork of KindleUnpack) and
    splits its content by chapters according to the Table of Contents (TOC).
    
    Each TOC entry references an anchor ID (like #fileposXXXXX). We find each
    anchor in the main body, collect the content up to the next anchor, and
    store it as a separate chapter. Images are read from the 'Images' subfolder.
    """
    # 1. Ensure 'imghdr' is available (monkey-patch if missing).
    try:
        import imghdr
    except ModuleNotFoundError:
        imghdr = types.ModuleType("imghdr")
        def what(file, h=None):
            return None
        imghdr.what = what
        sys.modules["imghdr"] = imghdr

    # 2. Import 'mobi' for extraction.
    try:
        import mobi
    except ImportError:
        raise ImportError("The 'mobi' library is required for parsing MOBI files. Install it via 'pip install mobi'.")

    # 3. Extract the MOBI file into a temporary folder.
    tempdir, extracted_path = mobi.extract(file_path)
    ext = os.path.splitext(extracted_path)[1].lower()
    bookname = os.path.splitext(file_path)[0].lower()


    # We'll store our results here.
    data = {}

    if ext == ".epub":
        # If the extracted file is actually an EPUB, reuse the EPUB parser.
        from atai_ebook_tool import parser as p
        data = p.parse_epub(extracted_path)

    elif ext in [".html", ".htm"]:
        # 4. Read the main HTML file (e.g. 'book.html').
        with open(extracted_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract the overall book title (fallback if needed).
        title = soup.title.string.strip() if soup.title and soup.title.string else bookname
        # Attempt to extract the author from a meta tag (fallback if missing).
        author = "Unknown MOBI Author"
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            author = meta_author["content"].strip()

        # 5. Locate the Table of Contents by searching for a tag that has text "Table of Contents".
        toc_marker = soup.find(lambda tag: tag.string and "table of contents" in tag.string.lower())
        chapters = {}
        chapter_counter = 0

        if toc_marker:
            # a) Gather all TOC links after that marker (or inside that marker’s container).
            #    Often these appear as <a href="#fileposXXXXX">Chapter Title</a>.
            toc_links = toc_marker.find_all_next("a", href=True)
            # Filter out only those with href like "#filepos..."
            toc_entries = []
            for link in toc_links:
                if link["href"].startswith("#filepos"):
                    chapter_title = link.get_text(strip=True)
                    anchor_id = link["href"][1:]  # remove leading '#'
                    toc_entries.append((chapter_title, anchor_id))

            # b) For each TOC entry, gather HTML from that anchor until the next anchor.
            #    We'll build a list of anchor IDs for quick detection.
            anchor_ids = [aid for _, aid in toc_entries]

            # We want to handle images the same way we do for EPUB.
            # So let's gather them from the "Images" folder.
            extracted_dir = os.path.dirname(extracted_path)
            images_folder = os.path.join(extracted_dir, "Images")
            mobi_images = {}
            if os.path.isdir(images_folder):
                for image_file in os.listdir(images_folder):
                    if image_file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                        full_path = os.path.join(images_folder, image_file)
                        with open(full_path, 'rb') as img_f:
                            mobi_images[image_file] = img_f.read()
            else:
                # Fallback: scan the extracted directory for images
                for f in os.listdir(extracted_dir):
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                        full_path = os.path.join(extracted_dir, f)
                        with open(full_path, 'rb') as img_f:
                            mobi_images[f] = img_f.read()

            from atai_ebook_tool.parser import format_html_content, ImageCounter
            image_counter = ImageCounter()
            image_mapping = {}

            # c) Loop over each TOC entry, find the anchor in the main HTML, and gather content.
            for i, (chapter_title, anchor_id) in enumerate(toc_entries):
                if chapter_counter == 0: # Skip the first entry (often the cover page).
                    chapter_counter += 1
                    continue  
                # Find the start tag with that ID.
                start_tag = soup.find(id=anchor_id)
                if not start_tag:
                    # If we can't find the anchor in the main body, skip it.
                    continue

                # The next anchor ID is used to know where to stop collecting.
                next_anchor_id = toc_entries[i+1][1] if i+1 < len(toc_entries) else None

                # Gather all siblings from start_tag onward until we hit the next anchor.
                chapter_elems = [start_tag]  # include the start tag itself
                for sib in start_tag.next_siblings:
                    # If this sibling is a tag with an ID that matches the next anchor, stop.
                    if (
                        hasattr(sib, "attrs") and
                        isinstance(sib.attrs, dict) and
                        "id" in sib.attrs and
                        sib["id"] == next_anchor_id
                    ):
                        break
                    chapter_elems.append(sib)

                # Convert these elements back to HTML.
                chapter_html = "".join(str(elem) for elem in chapter_elems)
                # Format (images, annotations) with the shared helper function.
                formatted_chapter = format_html_content(chapter_html, mobi_images, image_mapping, image_counter)
                chapters[f"chapter {chapter_counter}"] = f"{chapter_title}\n\n{formatted_chapter}"
                chapter_counter += 1

            # Build new_images from image_mapping
            new_images = {}
            for orig, new_filename in image_mapping.items():
                if orig in mobi_images:
                    new_images[new_filename] = mobi_images[orig]

            data = {
                "title": title,
                "author": author,
                "chapters": chapters,
                "images": new_images
            }
        else:
            # If no TOC marker found, just treat the entire file as a single-chapter ebook.
            data = single_chapter_fallback(soup, file_path=extracted_path)

    else:
        # For other extracted file types (e.g. PDF), return a dummy result.
        data = {
            "title": bookname,
            "author": "Unknown MOBI Author",
            "chapters": {"chapter 1": f"Extracted file type {ext} is not supported for chapter parsing."},
            "images": {}
        }

    # Clean up: remove the temporary extraction directory.
    shutil.rmtree(tempdir)
    return data

def single_chapter_fallback(soup, file_path):
    """
    If no Table of Contents is found, fallback to a single-chapter parse
    using the entire 'book.html'. This is similar to the earlier approach.
    """
    title = soup.title.string.strip() if soup.title and soup.title.string else "Unknown MOBI Title"
    author = "Unknown MOBI Author"
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = meta_author["content"].strip()

    # Convert entire soup to string for single-chapter approach.
    html_content = str(soup)

    extracted_dir = os.path.dirname(file_path)
    images_folder = os.path.join(extracted_dir, "Images")
    mobi_images = {}
    if os.path.isdir(images_folder):
        for image_file in os.listdir(images_folder):
            if image_file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                full_path = os.path.join(images_folder, image_file)
                with open(full_path, 'rb') as img_f:
                    mobi_images[image_file] = img_f.read()
    else:
        # Fallback: scan the extracted directory itself.
        for f in os.listdir(extracted_dir):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                full_path = os.path.join(extracted_dir, f)
                with open(full_path, 'rb') as img_f:
                    mobi_images[f] = img_f.read()

    from atai_ebook_tool.parser import format_html_content, ImageCounter
    image_counter = ImageCounter()
    image_mapping = {}
    formatted = format_html_content(html_content, mobi_images, image_mapping, image_counter)

    new_images = {}
    for orig, new_filename in image_mapping.items():
        if orig in mobi_images:
            new_images[new_filename] = mobi_images[orig]

    return {
        "title": title,
        "author": author,
        "chapters": {"chapter 1": formatted},
        "images": new_images
    }



def parse_ebook(file_path):
    """
    Determines the ebook format by file extension and calls the appropriate parser.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".epub":
        return parse_epub(file_path)
    elif ext == ".mobi":
        return parse_mobi(file_path)
    else:
        raise ValueError(f"Unsupported ebook format: {ext}")
