import os
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
    Dummy implementation for MOBI parsing.
    Replace this with a real MOBI parser as needed.
    """
    return {
        "title": "Dummy MOBI Title",
        "author": "Dummy Author",
        "chapters": {
            "chapter 1": "Chapter 1 dummy content",
            "chapter 2": "Chapter 2 dummy content"
        },
        "images": {}
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
