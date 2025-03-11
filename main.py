import os
from typing import List, Optional
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
from pydantic import BaseModel
import json
import PyPDF2
from docx import Document
from io import StringIO
from prompt_templates import RESUME_OPTIMIZATION_PROMPT, INTERVIEW_TIPS_PROMPT

app = FastAPI(title="AI-Powered Resume & Interview Tips")

# Set up templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuration for open-webui API
WEBUI_ENABLED = True  # Set to use open-webui API
WEBUI_BASE_URL = "https://chat.ivislabs.in/api"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjBkYzU4ZTdmLTQ3ZmEtNDY2YS1iMWY0LThmNzJiMzdmNTEwYiJ9.AgBA-_nJqW837k1xmghqqRWe7XUDYjgIJw0Bh6OmAII"  # Replace with your actual API key if needed
# Default model based on available models
DEFAULT_MODEL = "gemma2:2b"  # Update to one of the available models

# Fallback to local Ollama API if needed
OLLAMA_ENABLED = True  # Set to False to use only the web UI API
OLLAMA_HOST = "localhost"
OLLAMA_PORT = "11434"
OLLAMA_API_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api"

class GenerationRequest(BaseModel):
    resume_text: str
    job_description: str
    include_interview_tips: bool = True
    tone: Optional[str] = "professional"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    try:
        content = await file.read()
        if file.filename.endswith('.pdf'):
            pdf_reader = PyPDF2.PdfFileReader(StringIO(content))
            resume_text = ""
            for page_num in range(pdf_reader.numPages):
                resume_text += pdf_reader.getPage(page_num).extract_text()
        elif file.filename.endswith('.docx'):
            doc = Document(StringIO(content))
            resume_text = "\n".join([para.text for para in doc.paragraphs])
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        return {"resume_text": resume_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/generate")
async def generate_resume_optimization(
    resume_text: str = Form(...),
    job_description: str = Form(...),
    include_interview_tips: bool = Form(True),
    tone: str = Form("professional"),
    model: str = Form(DEFAULT_MODEL)
):
    try:
        # Build the prompt for resume optimization
        resume_prompt = RESUME_OPTIMIZATION_PROMPT.format(
            resume_text=resume_text,
            job_description=job_description,
            tone=tone
        )
        
        # Build the prompt for interview tips (if requested)
        interview_prompt = ""
        if include_interview_tips:
            interview_prompt = INTERVIEW_TIPS_PROMPT.format(
                job_description=job_description,
                tone=tone
            )
        
        # Combine prompts
        combined_prompt = f"{resume_prompt}\n\n{interview_prompt}" if include_interview_tips else resume_prompt
        
        # Try using the open-webui API first if enabled
        if WEBUI_ENABLED:
            try:
                # Prepare message for API format
                messages = [
                    {
                        "role": "user",
                        "content": combined_prompt
                    }
                ]
                
                # Debug: Print request payload
                request_payload = {
                    "model": model,
                    "messages": messages
                }
                print(f"Attempting open-webui API with payload: {json.dumps(request_payload)}")
                
                # Call Chat Completions API
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{WEBUI_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {API_KEY}",
                            "Content-Type": "application/json"
                        },
                        json=request_payload,
                        timeout=60.0
                    )
                    
                    # Debug: Print response details
                    print(f"Open-webui API response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        # Extract generated text from the response with fallback options
                        generated_text = ""
                        
                        # Try different possible response formats
                        if "choices" in result and len(result["choices"]) > 0:
                            choice = result["choices"][0]
                            if "message" in choice and "content" in choice["message"]:
                                generated_text = choice["message"]["content"]
                            elif "text" in choice:
                                generated_text = choice["text"]
                        elif "response" in result:
                            generated_text = result["response"]
                        
                        if generated_text:
                            return {"generated_text": generated_text}
            except Exception as e:
                print(f"Open-webui API attempt failed: {str(e)}")
        
        # Fallback to direct Ollama API if enabled and web UI failed
        if OLLAMA_ENABLED:
            print("Falling back to direct Ollama API")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{OLLAMA_API_URL}/generate",
                    json={
                        "model": model,
                        "prompt": combined_prompt,
                        "stream": False
                    },
                    timeout=60.0
                )
                
                if response.status_code != 200:
                    raise HTTPException(status_code=500, detail="Failed to generate content from Ollama API")
                
                result = response.json()
                generated_text = result.get("response", "")
                
                return {"generated_text": generated_text}
                
        # If we get here, both attempts failed
        raise HTTPException(status_code=500, detail="Failed to generate content from any available LLM API")
            
    except Exception as e:
        import traceback
        print(f"Error generating resume optimization: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error generating resume optimization: {str(e)}")

@app.get("/models")
async def get_models():
    try:
        # Try the open-webui models API first if enabled
        if WEBUI_ENABLED:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{WEBUI_BASE_URL}/models",
                        headers={
                            "Authorization": f"Bearer {API_KEY}"
                        }
                    )
                    
                    if response.status_code == 200:
                        models_data = response.json()
                        
                        # Handle the specific response format we received
                        if "data" in models_data and isinstance(models_data["data"], list):
                            model_names = []
                            for model in models_data["data"]:
                                if "id" in model:
                                    model_names.append(model["id"])
                            
                            # If models found, return them
                            if model_names:
                                return {"models": model_names}
            except Exception as e:
                print(f"Error fetching models from open-webui API: {str(e)}")
        
        # Fallback to Ollama's API if enabled
        if OLLAMA_ENABLED:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{OLLAMA_API_URL}/tags")
                    if response.status_code == 200:
                        models = response.json().get("models", [])
                        model_names = [model.get("name") for model in models]
                        return {"models": model_names}
            except Exception as e:
                print(f"Error fetching models from Ollama: {str(e)}")
        
        # If all attempts fail, return default model and some common models
        fallback_models = [DEFAULT_MODEL, "gemma2:2b", "qwen2.5:0.5b", "deepseek-r1:1.5b", "deepseek-coder:latest"]
        return {"models": fallback_models}
    except Exception as e:
        print(f"Unexpected error in get_models: {str(e)}")
        return {"models": [DEFAULT_MODEL]}

@app.post("/ats_score")
async def ats_score(resume_text: str = Form(...), job_description: str = Form(...)):
    try:
        # Simple keyword matching for ATS scoring
        required_keywords = ["SQL", "Algorithms", "Excel", "Statistics"]
        found_keywords = [keyword for keyword in required_keywords if keyword.lower() in resume_text.lower()]
        keyword_score = (len(found_keywords) / len(required_keywords)) * 10

        # Simple formatting score based on length
        formatting_score = min(len(resume_text) / 1000 * 20, 20)

        # Simple length score
        length_score = min(len(resume_text) / 500 * 10, 10)

        # Total ATS score
        ats_score = keyword_score + formatting_score + length_score

        # Feedback
        missing_keywords = [keyword for keyword in required_keywords if keyword.lower() not in resume_text.lower()]
        feedback = "Your resume is ATS-friendly." if ats_score >= 70 else "Your resume is not ATS-friendly. Consider making significant changes."

        return {
            "missing_keywords": missing_keywords,
            "keyword_score": keyword_score,
            "formatting_score": formatting_score,
            "length_score": length_score,
            "ats_score": ats_score,
            "ats_feedback": feedback
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating ATS score: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)