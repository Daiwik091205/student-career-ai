import os
import json
import time
import re
import threading
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# Models with active quota and fallback order
# gemini-3.1-flash-lite has active, high-volume quota
MODELS = [
    'gemini-3.1-flash-lite',
    'gemini-3.5-flash-lite',
    'gemini-3.5-flash'
]

# Strict 5 Requests Per Minute (RPM) limit with a minimum 13-second spacing
MAX_RPM = 5
MIN_REQUEST_INTERVAL = 13.0  # seconds

_request_lock = threading.Lock()
_request_timestamps = []

def _wait_for_rate_limit():
    """
    Enforces a strict rate limit for Gemini API calls:
    - Maximum 5 requests in any rolling 60-second window.
    - At least 13 seconds between consecutive requests.
    """
    with _request_lock:
        now = time.time()
        # Discard timestamps older than 60 seconds
        cutoff = now - 60.0
        while _request_timestamps and _request_timestamps[0] < cutoff:
            _request_timestamps.pop(0)

        # If we reached 5 requests in the rolling 60-second window, wait
        if len(_request_timestamps) >= MAX_RPM:
            wait_time = 60.0 - (now - _request_timestamps[0]) + 1.0
            if wait_time > 0:
                time.sleep(wait_time)

        # Ensure at least 13 seconds since the previous request
        if _request_timestamps:
            elapsed_since_last = time.time() - _request_timestamps[-1]
            if elapsed_since_last < MIN_REQUEST_INTERVAL:
                time.sleep(MIN_REQUEST_INTERVAL - elapsed_since_last)

        _request_timestamps.append(time.time())

def call_gemini_safe(prompt):
    """
    Calls Gemini with rate limiting and automatic model fallback across
    active models if a model encounters quota or 429 limits.
    """
    last_error = None
    
    for model_name in MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            for attempt in range(2):
                _wait_for_rate_limit()
                try:
                    response = model.generate_content(prompt)
                    return response.text.strip(), None
                except Exception as e:
                    err_str = str(e)
                    is_rate_limit = (
                        "429" in err_str or 
                        "Quota exceeded" in err_str or 
                        "ResourceExhausted" in err_str or
                        "rate-limits" in err_str
                    )
                    last_error = err_str
                    if is_rate_limit:
                        # If a daily limit or high delay is reported, break immediately to try next fallback model
                        if "GenerateRequestsPerDay" in err_str or "limit: 20" in err_str:
                            break
                        # Short retry delay
                        match = re.search(r'retry.*?(\d+(?:\.\d+)?)\s*s', err_str, re.IGNORECASE)
                        if not match:
                            match = re.search(r'seconds:\s*(\d+)', err_str, re.IGNORECASE)
                        delay = float(match.group(1)) + 1.0 if match else 13.0
                        if delay > 25.0:
                            # Too long to wait for this model, switch to fallback model
                            break
                        time.sleep(delay)
                    else:
                        break
        except Exception as e:
            last_error = str(e)
            continue
            
    return None, last_error or "All models exceeded rate limits."

def extract_skills_from_project(project_description):
    if not api_key: return "API key missing"
    
    prompt = f"""
    Given the following project description, extract the key technical and soft skills demonstrated.
    Return a comma-separated list of skills only.
    Project Description: {project_description}
    """
    text, err = call_gemini_safe(prompt)
    if err:
        return f"Error: {err}"
    return text

def analyze_target_career(career_name):
    if not api_key: return "API key missing"
    
    prompt = f"""
    What are the top 10 core technical and soft skills required for a {career_name}?
    Return a comma-separated list of skills only.
    """
    text, err = call_gemini_safe(prompt)
    if err:
        return f"Error: {err}"
    return text

def perform_gap_analysis(current_skills, target_skills, career_name, username="the student"):
    if not api_key: return {"gap_analysis": "API key missing", "readiness_score": 0}
    
    prompt = f"""
    You are an expert career advisor.
    {username}'s current skills are: {current_skills}
    The target career is: {career_name}
    The required skills for this career are typically: {target_skills}
    
    Provide a brief, straightforward, and objective paragraph analyzing the gap between their current skills and the target career. Address them by their name ({username}) instead of saying "the student". Do not over-hype or overly praise their skills; keep the tone professional and direct.
    Also, provide a readiness score out of 100 based on how closely their current skills match the required skills.
    
    Respond STRICTLY in JSON format:
    {{
        "gap_analysis": "your paragraph here",
        "readiness_score": 65
    }}
    """
    text, err = call_gemini_safe(prompt)
    if err:
        return {"gap_analysis": f"Error: {err}", "readiness_score": 0}
        
    try:
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        return json.loads(text.strip())
    except Exception as e:
        return {"gap_analysis": f"Error parsing response: {str(e)}", "readiness_score": 0}

def analyze_resume_and_recommend_jobs(username, profile_data, skills_list, projects_list, resume_text):
    if not api_key:
        return {
            "error": True,
            "message": "API key missing. Please configure GEMINI_API_KEY in .env.",
            "summary": "",
            "recommendations": []
        }
    
    education = profile_data.get("education", "Not specified")
    experience = profile_data.get("experience", "Not specified")
    interests = profile_data.get("interests", "Not specified")
    
    if skills_list:
        skills_str = ", ".join([f"{s['skill_name']} ({s['proficiency']})" for s in skills_list])
    else:
        skills_str = "None specified in profile"
        
    if projects_list:
        projects_str = "\n".join([f"- {p['project_name']}: {p['description']} (Skills: {p.get('extracted_skills', '')})" for p in projects_list])
    else:
        projects_str = "None specified in profile"

    # Truncate resume text to ~4000 characters to keep tokens lean and avoid overloading
    capped_resume = resume_text[:4000] if len(resume_text) > 4000 else resume_text

    prompt = f"""
    You are an expert, objective career advisor and technical recruiter.
    Analyze {username}'s background based on both their profile information and uploaded resume.
    
    User: {username}
    Profile Information:
    - Education: {education}
    - Experience: {experience}
    - Interests: {interests}
    - Profile Skills: {skills_str}
    - Profile Projects:
    {projects_str}
    
    Uploaded Resume Text:
    \"\"\"
    {capped_resume}
    \"\"\"
    
    Instructions:
    1. Provide a direct, straightforward 2-3 sentence summary of {username}'s overall background, core competencies, and career trajectory. Do not over-hype or flatter; keep the tone professional, objective, and realistic. Address {username} by name.
    2. Recommend 3 to 5 realistic job roles that suit their qualifications and background.
    3. For EACH recommended role, analyze the specific gaps:
       - role_title: The specific job role
       - match_score: An integer between 0 and 100 representing realistic alignment
       - why_matched: Straightforward reason why their skills/experience fit this role
       - skill_gaps: A list of specific missing or weak technical skills/tools for this role
       - experience_gaps: A list of specific missing experiences/domain knowledge for this role
       - action_plan: A list of concrete, actionable steps to bridge these gaps
    
    Respond STRICTLY in valid JSON format with this structure:
    {{
        "summary": "Direct, professional summary of qualifications.",
        "recommendations": [
            {{
                "role_title": "Job Title",
                "match_score": 75,
                "why_matched": "Why this aligns...",
                "skill_gaps": ["Skill A", "Skill B"],
                "experience_gaps": ["Gap 1"],
                "action_plan": ["Action 1", "Action 2"]
            }}
        ]
    }}
    """
    text, err = call_gemini_safe(prompt)
    if err:
        return {
            "error": True,
            "message": f"API rate limit reached or request failed: {err}. Please wait a few seconds and try again.",
            "summary": "",
            "recommendations": []
        }
    
    try:
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        parsed = json.loads(text.strip())
        parsed["error"] = False
        return parsed
    except Exception as e:
        return {
            "error": True,
            "message": f"Error parsing response: {str(e)}",
            "summary": "",
            "recommendations": []
        }

def generate_roadmap(current_skills, target_skills, career_name, gap_analysis):
    if not api_key: return []
    
    prompt = f"""
    You are an expert career advisor.
    Target Career: {career_name}
    Current Skills: {current_skills}
    Required Skills: {target_skills}
    Gap Analysis: {gap_analysis}
    
    Generate a step-by-step personalized learning roadmap for this student to bridge the skill gap and achieve their career goal.
    Break it down into logical phases or steps.
    
    Respond STRICTLY in JSON format as a list of objects, like this:
    [
        {{
            "step": "1",
            "title": "Master Python Basics",
            "description": "Learn syntax, data structures, and OOP in Python.",
            "skills_covered": "Python",
            "project_idea": "Build a CLI calculator or to-do app."
        }}
    ]
    """
    text, err = call_gemini_safe(prompt)
    if err:
        return []
    try:
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        return json.loads(text.strip())
    except Exception as e:
        return []
