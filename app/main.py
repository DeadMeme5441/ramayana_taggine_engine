# app/main.py
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import aiofiles
import json
from pathlib import Path
from typing import Dict, List, Optional

from app.tag_parser import DocumentTags

# Create FastAPI app
app = FastAPI(title="Ramayana Tagging Engine")

# Directory where uploaded files will be stored
UPLOADS_DIR = "uploads"
METADATA_DIR = "metadata"

# Ensure directories exist
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")


# Helper function to get all files with metadata
def get_all_files():
    files = []
    for filename in os.listdir(UPLOADS_DIR):
        file_path = os.path.join(UPLOADS_DIR, filename)
        if os.path.isfile(file_path):
            # Check if metadata exists
            base_name = os.path.splitext(filename)[0]
            metadata_path = os.path.join(METADATA_DIR, f"{base_name}_tags.json")
            has_metadata = os.path.exists(metadata_path)

            # Get tag count and error count if metadata exists
            tag_count = 0
            error_count = 0
            if has_metadata:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    tag_count = len(metadata.get("tags", []))
                    error_count = len(metadata.get("opening_errors", [])) + len(
                        metadata.get("closing_errors", [])
                    )

            files.append(
                {
                    "name": filename,
                    "size": os.path.getsize(file_path),
                    "modified": os.path.getmtime(file_path),
                    "has_metadata": has_metadata,
                    "tag_count": tag_count,
                    "error_count": error_count,
                }
            )
    return sorted(files, key=lambda x: x["name"])


# Helper function to read file contents with metadata
def read_file_with_metadata(filename: str):
    try:
        # Get file content
        file_path = os.path.join(UPLOADS_DIR, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Get tag metadata if it exists
        base_name = os.path.splitext(filename)[0]
        metadata_path = os.path.join(METADATA_DIR, f"{base_name}_tags.json")

        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                return {"content": content, "metadata": metadata}

        return {"content": content, "metadata": None}
    except UnicodeDecodeError:
        # If UTF-8 fails, try different encodings
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                return {"content": f.read(), "metadata": None}
        except:
            return {
                "content": "Error: Unable to read file. The file might be binary or use an unsupported encoding.",
                "metadata": None,
            }
    except Exception as e:
        return {"content": f"Error reading file: {str(e)}", "metadata": None}


# Home page route
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    files = get_all_files()
    file_data = {"content": "", "metadata": None}
    active_file = ""

    # Check for error parameter
    upload_error = request.query_params.get("error")

    # If there are files, display the first one by default
    if files:
        active_file = files[0]["name"]
        file_data = read_file_with_metadata(active_file)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "files": files,
            "file_data": file_data,
            "active_file": active_file,
            "upload_error": upload_error,
        },
    )


# View file route
@app.get("/view/{filename}", response_class=HTMLResponse)
async def view_file(request: Request, filename: str):
    files = get_all_files()
    file_data = read_file_with_metadata(filename)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "files": files,
            "file_data": file_data,
            "active_file": filename,
        },
    )


# Get file content (for HTMX requests)
@app.get("/view_content/{filename}", response_class=HTMLResponse)
async def view_content(request: Request, filename: str):
    file_data = read_file_with_metadata(filename)

    return templates.TemplateResponse(
        "partials/content.html",
        {"request": request, "file_data": file_data, "active_file": filename},
    )


# Get tags (for HTMX requests)
@app.get("/view_tags/{filename}", response_class=HTMLResponse)
async def view_tags(request: Request, filename: str):
    file_data = read_file_with_metadata(filename)

    return templates.TemplateResponse(
        "partials/tag_display.html",
        {"request": request, "file_data": file_data, "active_file": filename},
    )


# Upload file endpoint
@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    try:
        # Save the uploaded file
        file_path = os.path.join(UPLOADS_DIR, file.filename)

        async with aiofiles.open(file_path, "wb") as out_file:
            while content := await file.read(1024 * 1024):  # 1MB chunks
                await out_file.write(content)

        # Process the file for tags
        try:
            doc_tags = DocumentTags(file_path)
            metadata_path = doc_tags.save_metadata(METADATA_DIR)
        except Exception as e:
            print(f"Error processing tags: {str(e)}")
            # Continue even if tag processing fails

        # Redirect to home page to refresh everything
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        print(f"Upload error: {str(e)}")
        # Redirect to home page even on error
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url=f"/?error={str(e)}", status_code=303)


# Delete file endpoint
@app.delete("/delete/{filename}", response_class=HTMLResponse)
async def delete_file(request: Request, filename: str):
    try:
        # Delete the file
        file_path = os.path.join(UPLOADS_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        # Delete metadata if it exists
        base_name = os.path.splitext(filename)[0]
        metadata_path = os.path.join(METADATA_DIR, f"{base_name}_tags.json")
        if os.path.exists(metadata_path):
            os.remove(metadata_path)

        # Get updated file list
        files = get_all_files()

        # Return the updated file list
        return templates.TemplateResponse(
            "partials/file_list.html",
            {"request": request, "files": files, "active_file": ""},
        )
    except Exception as e:
        files = get_all_files()
        return templates.TemplateResponse(
            "partials/file_list.html",
            {"request": request, "files": files, "delete_error": str(e)},
        )


# Process existing file for tags
@app.post("/process/{filename}", response_class=HTMLResponse)
async def process_file(request: Request, filename: str):
    try:
        file_path = os.path.join(UPLOADS_DIR, filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {filename} not found")

        # Process the file for tags
        doc_tags = DocumentTags(file_path)
        metadata_path = doc_tags.save_metadata(METADATA_DIR)

        # Get file data with metadata
        file_data = read_file_with_metadata(filename)

        # Return the updated content view
        return templates.TemplateResponse(
            "partials/content.html",
            {"request": request, "file_data": file_data, "active_file": filename},
        )
    except Exception as e:
        file_data = {"content": f"Error processing file: {str(e)}", "metadata": None}
        return templates.TemplateResponse(
            "partials/content.html",
            {"request": request, "file_data": file_data, "active_file": filename},
        )


# Get tag metadata as JSON
@app.get("/api/tags/{filename}")
async def get_tags_json(filename: str):
    base_name = os.path.splitext(filename)[0]
    metadata_path = os.path.join(METADATA_DIR, f"{base_name}_tags.json")

    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            return metadata

    return {"error": "Metadata not found for this file"}
