from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import aiofiles
from pathlib import Path

# Create FastAPI app
app = FastAPI(title="Simple File Viewer")

# Directory where uploaded files will be stored
UPLOADS_DIR = "uploads"

# Ensure uploads directory exists
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")


# Helper function to get all files
def get_all_files():
    files = []
    for filename in os.listdir(UPLOADS_DIR):
        if os.path.isfile(os.path.join(UPLOADS_DIR, filename)):
            files.append(
                {
                    "name": filename,
                    "size": os.path.getsize(os.path.join(UPLOADS_DIR, filename)),
                    "modified": os.path.getmtime(os.path.join(UPLOADS_DIR, filename)),
                }
            )
    return sorted(files, key=lambda x: x["name"])


# Helper function to read file contents
def read_file(filename):
    try:
        with open(os.path.join(UPLOADS_DIR, filename), "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # If UTF-8 fails, try different encodings
        try:
            with open(
                os.path.join(UPLOADS_DIR, filename), "r", encoding="latin-1"
            ) as f:
                return f.read()
        except:
            return "Error: Unable to read file. The file might be binary or use an unsupported encoding."
    except Exception as e:
        return f"Error reading file: {str(e)}"


# Home page route
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    files = get_all_files()
    content = ""
    active_file = ""

    # If there are files, display the first one by default
    if files:
        active_file = files[0]["name"]
        content = read_file(active_file)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "files": files,
            "content": content,
            "active_file": active_file,
        },
    )


# View file route
@app.get("/view/{filename}", response_class=HTMLResponse)
async def view_file(request: Request, filename: str):
    files = get_all_files()
    content = read_file(filename)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "files": files,
            "content": content,
            "active_file": filename,
        },
    )


# Get file content (for HTMX requests)
@app.get("/content/{filename}", response_class=HTMLResponse)
async def get_content(request: Request, filename: str):
    content = read_file(filename)

    return templates.TemplateResponse(
        "partials/content.html",
        {"request": request, "content": content, "active_file": filename},
    )


# Upload file endpoint
@app.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    try:
        # Save the uploaded file
        file_path = os.path.join(UPLOADS_DIR, file.filename)

        async with aiofiles.open(file_path, "wb") as out_file:
            while content := await file.read(1024 * 1024):  # 1MB chunks
                await out_file.write(content)

        # Get updated file list
        files = get_all_files()

        # Return the updated file list
        return templates.TemplateResponse(
            "partials/file_list.html",
            {"request": request, "files": files, "active_file": file.filename},
        )
    except Exception as e:
        files = get_all_files()
        return templates.TemplateResponse(
            "partials/file_list.html",
            {"request": request, "files": files, "upload_error": str(e)},
        )


# Delete file endpoint
@app.delete("/delete/{filename}", response_class=HTMLResponse)
async def delete_file(request: Request, filename: str):
    try:
        # Delete the file
        file_path = os.path.join(UPLOADS_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

        # Get updated file list
        files = get_all_files()

        # If there are files, set active_file to the first one
        active_file = files[0]["name"] if files else ""
        content = read_file(active_file) if active_file else ""

        # Return the updated file list
        return templates.TemplateResponse(
            "partials/file_list.html",
            {"request": request, "files": files, "active_file": active_file},
        )
    except Exception as e:
        files = get_all_files()
        return templates.TemplateResponse(
            "partials/file_list.html",
            {"request": request, "files": files, "delete_error": str(e)},
        )
